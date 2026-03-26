"""
Resilient Filesystem with Error Correction

Provides:
- Checksums for file integrity
- Automatic backup and recovery
- Atomic operations
- Version control for critical files
- Corruption detection and repair
"""

import hashlib
import json
import shutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import threading
import logging

logger = logging.getLogger(__name__)


class FileOperationType(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    COPY = "copy"
    MOVE = "move"


class OperationStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RECOVERED = "recovered"
    ROLLED_BACK = "rolled_back"


@dataclass
class FileOperation:
    """Record of a file operation"""
    operation_id: str
    operation_type: FileOperationType
    source_path: Path
    target_path: Optional[Path] = None
    checksum_before: Optional[str] = None
    checksum_after: Optional[str] = None
    timestamp: float = 0.0
    status: OperationStatus = OperationStatus.PENDING
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "operation_type": self.operation_type.value,
            "source_path": str(self.source_path),
            "target_path": str(self.target_path) if self.target_path else None,
            "checksum_before": self.checksum_before,
            "checksum_after": self.checksum_after,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


class ChecksumType(Enum):
    MD5 = "md5"  # For non-security use
    SHA256 = "sha256"  # For security-critical
    BLAKE3 = "blake3"  # Fast and secure


class ResilientFilesystem:
    """
    Filesystem with built-in error correction and resilience.
    
    Features:
    - Automatic checksums for all files
    - Backup and versioning
    - Atomic operations
    - Automatic recovery from corruption
    - Operation journaling
    """
    
    def __init__(
        self,
        base_path: Union[str, Path] = "./data/resilient_fs",
        backup_path: Union[str, Path] = "./data/backups",
        checksum_type: ChecksumType = ChecksumType.SHA256,
        enable_versioning: bool = True,
        max_versions: int = 10,
        auto_backup_interval: int = 3600,  # 1 hour
        integrity_check_interval: int = 86400,  # 24 hours
    ):
        self.base_path = Path(base_path)
        self.backup_path = Path(backup_path)
        self.checksum_type = checksum_type
        self.enable_versioning = enable_versioning
        self.max_versions = max_versions
        
        # Create directories
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.backup_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / ".checksums").mkdir(exist_ok=True)
        (self.base_path / ".journal").mkdir(exist_ok=True)
        
        # Operation journal
        self._journal: List[FileOperation] = []
        self._journal_lock = threading.Lock()
        self._load_journal()
        
        # File checksums cache
        self._checksums: Dict[Path, str] = {}
        self._checksums_lock = threading.Lock()
        self._load_checksums()
        
        # Background tasks
        self._stop_event = threading.Event()
        self._backup_thread: Optional[threading.Thread] = None
        self._integrity_thread: Optional[threading.Thread] = None
        
        if auto_backup_interval > 0:
            self._start_auto_backup(auto_backup_interval)
        
        if integrity_check_interval > 0:
            self._start_integrity_checks(integrity_check_interval)
    
    def _get_checksum(self, data: Union[str, bytes, Path], algorithm: ChecksumType = None) -> str:
        """Calculate checksum of data"""
        algorithm = algorithm or self.checksum_type
        
        if isinstance(data, Path):
            data = data.read_bytes()
        elif isinstance(data, str):
            data = data.encode()
        
        if algorithm == ChecksumType.MD5:
            return hashlib.md5(data, usedforsecurity=False).hexdigest()
        elif algorithm == ChecksumType.SHA256:
            return hashlib.sha256(data).hexdigest()
        elif algorithm == ChecksumType.BLAKE3:
            try:
                import blake3
                return blake3.blake3(data).hexdigest()
            except ImportError:
                return hashlib.sha256(data).hexdigest()
        
        return hashlib.sha256(data).hexdigest()
    
    def _load_checksums(self):
        """Load checksum database"""
        checksums_file = self.base_path / ".checksums" / "checksums.json"
        if checksums_file.exists():
            try:
                with open(checksums_file) as f:
                    data = json.load(f)
                    self._checksums = {Path(k): v for k, v in data.items()}
            except Exception as e:
                logger.error(f"Failed to load checksums: {e}")
    
    def _save_checksums(self):
        """Save checksum database"""
        checksums_file = self.base_path / ".checksums" / "checksums.json"
        with self._checksums_lock:
            with open(checksums_file, 'w') as f:
                json.dump({str(k): v for k, v in self._checksums.items()}, f, indent=2)
    
    def _load_journal(self):
        """Load operation journal"""
        journal_file = self.base_path / ".journal" / "operations.json"
        if journal_file.exists():
            try:
                with open(journal_file) as f:
                    data = json.load(f)
                    self._journal = [
                        FileOperation(
                            operation_id=op["operation_id"],
                            operation_type=FileOperationType(op["operation_type"]),
                            source_path=Path(op["source_path"]),
                            target_path=Path(op["target_path"]) if op["target_path"] else None,
                            checksum_before=op["checksum_before"],
                            checksum_after=op["checksum_after"],
                            timestamp=op["timestamp"],
                            status=OperationStatus(op["status"]),
                            error_message=op["error_message"],
                            retry_count=op["retry_count"],
                            max_retries=op["max_retries"],
                        )
                        for op in data
                    ]
            except Exception as e:
                logger.error(f"Failed to load journal: {e}")
    
    def _save_journal(self):
        """Save operation journal"""
        journal_file = self.base_path / ".journal" / "operations.json"
        with self._journal_lock:
            with open(journal_file, 'w') as f:
                json.dump([op.to_dict() for op in self._journal], f, indent=2)
    
    def _add_to_journal(self, operation: FileOperation):
        """Add operation to journal"""
        with self._journal_lock:
            self._journal.append(operation)
            # Keep only last 1000 operations
            if len(self._journal) > 1000:
                self._journal = self._journal[-1000:]
        self._save_journal()
    
    def read_file(
        self,
        path: Union[str, Path],
        binary: bool = False,
        verify_checksum: bool = True
    ) -> Union[str, bytes]:
        """
        Read file with integrity verification.
        
        Args:
            path: File path
            binary: Read as binary
            verify_checksum: Verify file integrity
        
        Returns:
            File contents
        
        Raises:
            FileNotFoundError: If file doesn't exist
            CorruptionError: If file is corrupted
        """
        path = self.base_path / Path(path)
        
        operation = FileOperation(
            operation_id=self._generate_id(),
            operation_type=FileOperationType.READ,
            source_path=path,
        )
        
        try:
            mode = 'rb' if binary else 'r'
            with open(path, mode) as f:
                content = f.read()
            
            # Verify checksum
            if verify_checksum and path in self._checksums:
                current_checksum = self._get_checksum(content)
                expected_checksum = self._checksums[path]
                
                if current_checksum != expected_checksum:
                    # Try to recover from backup
                    recovered = self._attempt_recovery(path)
                    if recovered:
                        operation.status = OperationStatus.RECOVERED
                        self._add_to_journal(operation)
                        return recovered
                    
                    raise CorruptionError(
                        f"File {path} is corrupted. "
                        f"Expected: {expected_checksum}, Got: {current_checksum}"
                    )
            
            operation.status = OperationStatus.SUCCESS
            self._add_to_journal(operation)
            
            return content
            
        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            self._add_to_journal(operation)
            raise
    
    def write_file(
        self,
        path: Union[str, Path],
        content: Union[str, bytes],
        binary: bool = False,
        atomic: bool = True,
        create_backup: bool = True
    ) -> FileOperation:
        """
        Write file with atomic operations and checksums.
        
        Args:
            path: File path
            content: Content to write
            binary: Write as binary
            atomic: Use atomic write (write to temp, then move)
            create_backup: Create backup before overwriting
        
        Returns:
            FileOperation record
        """
        path = self.base_path / Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        operation = FileOperation(
            operation_id=self._generate_id(),
            operation_type=FileOperationType.WRITE,
            source_path=path,
        )
        
        try:
            # Store old checksum if file exists
            if path.exists():
                operation.checksum_before = self._checksums.get(path)
                
                if create_backup:
                    self._create_backup(path)
                
                if self.enable_versioning:
                    self._create_version(path)
            
            # Prepare content
            if binary and isinstance(content, str):
                content = content.encode()
            elif not binary and isinstance(content, bytes):
                content = content.decode()
            
            # Atomic write
            if atomic:
                temp_path = path.with_suffix(path.suffix + ".tmp")
                mode = 'wb' if binary else 'w'
                
                if binary:
                    temp_path.write_bytes(content)
                else:
                    temp_path.write_text(content)
                
                # Verify temp file
                temp_checksum = self._get_checksum(temp_path)
                
                # Atomic move
                temp_path.replace(path)
                
                operation.checksum_after = temp_checksum
            else:
                mode = 'wb' if binary else 'w'
                with open(path, mode) as f:
                    f.write(content)
                
                operation.checksum_after = self._get_checksum(content)
            
            # Update checksum database
            with self._checksums_lock:
                self._checksums[path] = operation.checksum_after
            self._save_checksums()
            
            operation.status = OperationStatus.SUCCESS
            self._add_to_journal(operation)
            
            return operation
            
        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            self._add_to_journal(operation)
            
            # Attempt rollback
            self._rollback_write(path, operation.checksum_before)
            
            raise
    
    def delete_file(
        self,
        path: Union[str, Path],
        safe_delete: bool = True,
        create_backup: bool = True
    ) -> FileOperation:
        """
        Delete file with safety measures.
        
        Args:
            path: File path
            safe_delete: Move to trash instead of permanent delete
            create_backup: Create backup before deletion
        
        Returns:
            FileOperation record
        """
        path = self.base_path / Path(path)
        
        operation = FileOperation(
            operation_id=self._generate_id(),
            operation_type=FileOperationType.DELETE,
            source_path=path,
        )
        
        try:
            if not path.exists():
                operation.status = OperationStatus.SUCCESS
                self._add_to_journal(operation)
                return operation
            
            # Store checksum
            operation.checksum_before = self._checksums.get(path)
            
            # Create backup
            if create_backup:
                self._create_backup(path)
            
            if safe_delete:
                # Move to trash
                trash_path = self.base_path / ".trash" / path.name
                trash_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(trash_path))
            else:
                path.unlink()
            
            # Remove from checksums
            with self._checksums_lock:
                if path in self._checksums:
                    del self._checksums[path]
            self._save_checksums()
            
            operation.status = OperationStatus.SUCCESS
            self._add_to_journal(operation)
            
            return operation
            
        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            self._add_to_journal(operation)
            raise
    
    def copy_file(
        self,
        source: Union[str, Path],
        target: Union[str, Path],
        preserve_checksum: bool = True
    ) -> FileOperation:
        """Copy file with checksum preservation"""
        source = self.base_path / Path(source)
        target = self.base_path / Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        operation = FileOperation(
            operation_id=self._generate_id(),
            operation_type=FileOperationType.COPY,
            source_path=source,
            target_path=target,
        )
        
        try:
            shutil.copy2(str(source), str(target))
            
            # Copy checksum
            if preserve_checksum and source in self._checksums:
                with self._checksums_lock:
                    self._checksums[target] = self._checksums[source]
                self._save_checksums()
            
            operation.checksum_after = self._checksums.get(target)
            operation.status = OperationStatus.SUCCESS
            self._add_to_journal(operation)
            
            return operation
            
        except Exception as e:
            operation.status = OperationStatus.FAILED
            operation.error_message = str(e)
            self._add_to_journal(operation)
            raise
    
    def verify_integrity(self, path: Optional[Path] = None) -> Dict[Path, bool]:
        """
        Verify integrity of files.
        
        Args:
            path: Specific file or directory to check, or None for all
        
        Returns:
            Dictionary mapping paths to integrity status
        """
        results = {}
        
        if path:
            path = self.base_path / Path(path)
            paths = [path] if path.is_file() else list(path.rglob("*"))
        else:
            paths = [
                p for p in self.base_path.rglob("*")
                if p.is_file() and not p.parts[-2].startswith(".")
            ]
        
        for file_path in paths:
            if file_path in self._checksums:
                try:
                    current_checksum = self._get_checksum(file_path)
                    expected_checksum = self._checksums[file_path]
                    results[file_path] = (current_checksum == expected_checksum)
                except Exception:
                    results[file_path] = False
            else:
                results[file_path] = True  # No checksum to verify against
        
        return results
    
    def repair_file(self, path: Union[str, Path]) -> bool:
        """
        Attempt to repair corrupted file from backup.
        
        Args:
            path: Path to corrupted file
        
        Returns:
            True if repaired, False otherwise
        """
        path = self.base_path / Path(path)
        
        # Find latest backup
        backup_dir = self.backup_path / path.relative_to(self.base_path).parent
        if not backup_dir.exists():
            return False
        
        backups = sorted(backup_dir.glob(f"{path.name}.*.bak"), reverse=True)
        
        for backup in backups:
            try:
                # Verify backup integrity
                backup_checksum = self._get_checksum(backup)
                
                # Copy backup to original location
                shutil.copy2(str(backup), str(path))
                
                # Update checksum
                with self._checksums_lock:
                    self._checksums[path] = backup_checksum
                self._save_checksums()
                
                logger.info(f"Repaired {path} from backup {backup}")
                return True
                
            except Exception as e:
                logger.warning(f"Failed to restore from {backup}: {e}")
                continue
        
        return False
    
    def _create_backup(self, path: Path):
        """Create backup of file"""
        backup_dir = self.backup_path / path.relative_to(self.base_path).parent
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{path.name}.{timestamp}.bak"
        
        shutil.copy2(str(path), str(backup_path))
        
        # Clean old backups
        self._clean_old_backups(backup_dir, path.name)
    
    def _create_version(self, path: Path):
        """Create versioned copy"""
        versions_dir = self.base_path / ".versions" / path.relative_to(self.base_path).parent
        versions_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_path = versions_dir / f"{path.name}.{timestamp}"
        
        shutil.copy2(str(path), str(version_path))
        
        # Clean old versions
        self._clean_old_versions(versions_dir, path.name)
    
    def _clean_old_backups(self, backup_dir: Path, filename: str):
        """Remove old backups keeping only recent ones"""
        backups = sorted(backup_dir.glob(f"{filename}.*.bak"))
        if len(backups) > self.max_versions:
            for old_backup in backups[:-self.max_versions]:
                old_backup.unlink()
    
    def _clean_old_versions(self, versions_dir: Path, filename: str):
        """Remove old versions"""
        versions = sorted(versions_dir.glob(f"{filename}.*"))
        if len(versions) > self.max_versions:
            for old_version in versions[:-self.max_versions]:
                old_version.unlink()
    
    def _attempt_recovery(self, path: Path) -> Optional[bytes]:
        """Attempt to recover file from backup"""
        if self.repair_file(path):
            return self.read_file(path, binary=True, verify_checksum=False)
        return None
    
    def _rollback_write(self, path: Path, original_checksum: Optional[str]):
        """Rollback failed write operation"""
        if original_checksum:
            self.repair_file(path)
    
    def _generate_id(self) -> str:
        """Generate unique operation ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _start_auto_backup(self, interval: int):
        """Start automatic backup thread"""
        def backup_task():
            while not self._stop_event.is_set():
                self._stop_event.wait(interval)
                if not self._stop_event.is_set():
                    self._perform_full_backup()
        
        self._backup_thread = threading.Thread(target=backup_task, daemon=True)
        self._backup_thread.start()
    
    def _start_integrity_checks(self, interval: int):
        """Start integrity check thread"""
        def integrity_task():
            while not self._stop_event.is_set():
                self._stop_event.wait(interval)
                if not self._stop_event.is_set():
                    self._perform_integrity_check()
        
        self._integrity_thread = threading.Thread(target=integrity_task, daemon=True)
        self._integrity_thread.start()
    
    def _perform_full_backup(self):
        """Perform full filesystem backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        full_backup_dir = self.backup_path / f"full_backup_{timestamp}"
        
        try:
            shutil.copytree(
                str(self.base_path),
                str(full_backup_dir),
                ignore=shutil.ignore_patterns(".checksums", ".journal", ".versions", ".trash")
            )
            logger.info(f"Full backup completed: {full_backup_dir}")
        except Exception as e:
            logger.error(f"Full backup failed: {e}")
    
    def _perform_integrity_check(self):
        """Perform integrity check on all files"""
        results = self.verify_integrity()
        corrupted = [p for p, ok in results.items() if not ok]
        
        if corrupted:
            logger.warning(f"Found {len(corrupted)} corrupted files")
            for path in corrupted:
                if self.repair_file(path):
                    logger.info(f"Repaired: {path}")
                else:
                    logger.error(f"Failed to repair: {path}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filesystem statistics"""
        return {
            "base_path": str(self.base_path),
            "total_files": len(self._checksums),
            "total_operations": len(self._journal),
            "failed_operations": len([op for op in self._journal if op.status == OperationStatus.FAILED]),
            "checksum_type": self.checksum_type.value,
            "versioning_enabled": self.enable_versioning,
        }
    
    def shutdown(self):
        """Shutdown filesystem and cleanup"""
        self._stop_event.set()
        
        if self._backup_thread:
            self._backup_thread.join(timeout=5)
        
        if self._integrity_thread:
            self._integrity_thread.join(timeout=5)
        
        self._save_checksums()
        self._save_journal()


class CorruptionError(Exception):
    """Raised when file corruption is detected"""
    pass
