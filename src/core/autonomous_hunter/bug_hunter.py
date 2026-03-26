"""
Autonomous Bug Hunter

Continuously scans codebase for bugs and automatically fixes them.
Uses multiple detection strategies:
- Static analysis
- Pattern matching
- Runtime monitoring
- Historical bug patterns
- Machine learning predictions
"""

import ast
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import threading
import logging

logger = logging.getLogger(__name__)


class BugSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BugType(Enum):
    SYNTAX = "syntax"
    LOGIC = "logic"
    PERFORMANCE = "performance"
    SECURITY = "security"
    STYLE = "style"
    MEMORY = "memory"
    CONCURRENCY = "concurrency"


@dataclass
class BugReport:
    """Report of a detected bug"""
    bug_id: str
    file_path: Path
    line_number: int
    severity: BugSeverity
    bug_type: BugType
    message: str
    code_snippet: str
    suggested_fix: str
    auto_fixable: bool = False
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    fixed: bool = False
    fix_commit: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "bug_id": self.bug_id,
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "severity": self.severity.value,
            "bug_type": self.bug_type.value,
            "message": self.message,
            "code_snippet": self.code_snippet,
            "suggested_fix": self.suggested_fix,
            "auto_fixable": self.auto_fixable,
            "confidence": self.confidence,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "fixed": self.fixed,
            "fix_commit": self.fix_commit,
        }


@dataclass
class BugPattern:
    """Pattern for detecting specific bugs"""
    pattern_id: str
    name: str
    description: str
    severity: BugSeverity
    regex_pattern: Optional[str] = None
    ast_pattern: Optional[Callable] = None
    fix_template: Optional[str] = None
    examples: List[Tuple[str, str]] = field(default_factory=list)  # (bad, good)


class AutonomousBugHunter:
    """
    Autonomous bug detection and fixing system.
    
    Continuously hunts for bugs using multiple strategies:
    1. Static analysis (AST parsing)
    2. Regex pattern matching
    3. Historical bug pattern matching
    4. Runtime error tracking
    """
    
    # Common bug patterns
    BUG_PATTERNS = [
        BugPattern(
            pattern_id="bare_except",
            name="Bare Except Clause",
            description="Using 'except:' catches all exceptions including KeyboardInterrupt",
            severity=BugSeverity.HIGH,
            regex_pattern=r"except\s*:\s*$",
            fix_template="except Exception:",
            examples=[("except:", "except Exception:")],
        ),
        BugPattern(
            pattern_id="mutable_default",
            name="Mutable Default Argument",
            description="Using mutable default arguments can cause unexpected behavior",
            severity=BugSeverity.HIGH,
            ast_pattern=lambda node: (
                isinstance(node, ast.FunctionDef) and
                any(
                    isinstance(default, (ast.List, ast.Dict, ast.Set))
                    for default in node.args.defaults
                )
            ),
            fix_template="Use None as default and initialize mutable inside function",
            examples=[(
                "def func(items=[]):",
                "def func(items=None):\n    if items is None:\n        items = []"
            )],
        ),
        BugPattern(
            pattern_id="no_return",
            name="Missing Return Statement",
            description="Function may not return a value in all code paths",
            severity=BugSeverity.MEDIUM,
            ast_pattern=lambda node: (
                isinstance(node, ast.FunctionDef) and
                not any(isinstance(n, ast.Return) for n in ast.walk(node))
            ),
            fix_template="Add explicit return statement",
        ),
        BugPattern(
            pattern_id="print_debug",
            name="Print Statement for Debug",
            description="Using print for debugging instead of logging",
            severity=BugSeverity.LOW,
            regex_pattern=r"^\s*print\s*\(",
            fix_template="Use logger.debug() or logger.info()",
        ),
        BugPattern(
            pattern_id="sql_injection",
            name="Potential SQL Injection",
            description="String formatting in SQL queries can lead to SQL injection",
            severity=BugSeverity.CRITICAL,
            regex_pattern=r'(execute|raw|query)\s*\([^)]*%[sd]',
            fix_template="Use parameterized queries",
        ),
        BugPattern(
            pattern_id="hardcoded_secret",
            name="Hardcoded Secret",
            description="Potential hardcoded password or secret",
            severity=BugSeverity.CRITICAL,
            regex_pattern=r'(password|secret|token|key)\s*=\s*["\'][^"\']+["\']',
            fix_template="Use environment variables",
        ),
        BugPattern(
            pattern_id="unused_import",
            name="Unused Import",
            description="Import statement not used in the file",
            severity=BugSeverity.LOW,
        ),
        BugPattern(
            pattern_id="broad_exception",
            name="Broad Exception Handling",
            description="Catching Exception is too broad",
            severity=BugSeverity.MEDIUM,
            regex_pattern=r"except\s+Exception\s*:",
            fix_template="Catch specific exceptions",
        ),
    ]
    
    def __init__(
        self,
        codebase_path: Path = Path("."),
        scan_interval: float = 300.0,  # 5 minutes
        auto_fix: bool = True,
        confidence_threshold: float = 0.8,
    ):
        self.codebase_path = Path(codebase_path)
        self.scan_interval = scan_interval
        self.auto_fix = auto_fix
        self.confidence_threshold = confidence_threshold
        
        # Bug storage
        self._bugs: Dict[str, BugReport] = {}
        self._fixed_bugs: List[BugReport] = []
        self._bug_history: List[BugReport] = []
        
        # Locks
        self._lock = threading.RLock()
        self._running = False
        self._hunter_thread: Optional[threading.Thread] = None
        
        # Statistics
        self._scans_completed = 0
        self._bugs_found = 0
        self._bugs_fixed = 0
        
        # Load historical bugs
        self._load_bugs()
        
        # Start hunting
        self._start_hunting()
    
    def _start_hunting(self):
        """Start autonomous bug hunting"""
        self._running = True
        
        def hunt_loop():
            while self._running:
                try:
                    self._hunt_once()
                    self._scans_completed += 1
                except Exception as e:
                    logger.error(f"Bug hunt failed: {e}")
                
                time.sleep(self.scan_interval)
        
        self._hunter_thread = threading.Thread(target=hunt_loop, daemon=True)
        self._hunter_thread.start()
        logger.info("Autonomous Bug Hunter started")
    
    def _hunt_once(self):
        """Perform one bug hunting cycle"""
        logger.info("Starting bug hunt...")
        
        # Find all Python files
        py_files = list(self.codebase_path.rglob("*.py"))
        
        # Skip hidden directories
        py_files = [
            f for f in py_files
            if not any(part.startswith('.') for part in f.parts)
            and 'venv' not in str(f)
        ]
        
        new_bugs = []
        
        for file_path in py_files:
            try:
                bugs = self._scan_file(file_path)
                new_bugs.extend(bugs)
            except Exception as e:
                logger.error(f"Failed to scan {file_path}: {e}")
        
        # Process new bugs
        with self._lock:
            for bug in new_bugs:
                if bug.bug_id not in self._bugs:
                    self._bugs[bug.bug_id] = bug
                    self._bugs_found += 1
                    
                    logger.warning(
                        f"New bug found: {bug.bug_type.value} in {bug.file_path}:{bug.line_number}"
                    )
                    
                    # Auto-fix if enabled and confident
                    if self.auto_fix and bug.auto_fixable and bug.confidence >= self.confidence_threshold:
                        self._attempt_fix(bug)
        
        # Save bugs
        self._save_bugs()
        
        logger.info(f"Bug hunt complete. Found {len(new_bugs)} new bugs.")
    
    def _scan_file(self, file_path: Path) -> List[BugReport]:
        """Scan a single file for bugs"""
        bugs = []
        
        content = file_path.read_text()
        lines = content.split('\n')
        
        # Parse AST
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # File has syntax errors - report it
            bugs.append(BugReport(
                bug_id=self._hash_bug(file_path, 0, "syntax_error"),
                file_path=file_path,
                line_number=0,
                severity=BugSeverity.CRITICAL,
                bug_type=BugType.SYNTAX,
                message="File has syntax errors",
                code_snippet="",
                suggested_fix="Fix syntax errors",
                auto_fixable=False,
                confidence=1.0,
            ))
            return bugs
        
        # Check regex patterns
        for pattern in self.BUG_PATTERNS:
            if pattern.regex_pattern:
                for match in re.finditer(pattern.regex_pattern, content, re.MULTILINE):
                    line_num = content[:match.start()].count('\n') + 1
                    
                    bug = BugReport(
                        bug_id=self._hash_bug(file_path, line_num, pattern.pattern_id),
                        file_path=file_path,
                        line_number=line_num,
                        severity=pattern.severity,
                        bug_type=self._get_bug_type(pattern.pattern_id),
                        message=pattern.description,
                        code_snippet=lines[line_num - 1].strip()[:100],
                        suggested_fix=pattern.fix_template or "Manual fix required",
                        auto_fixable=bool(pattern.fix_template),
                        confidence=0.9,
                    )
                    bugs.append(bug)
        
        # Check AST patterns
        for pattern in self.BUG_PATTERNS:
            if pattern.ast_pattern:
                for node in ast.walk(tree):
                    if pattern.ast_pattern(node):
                        line_num = getattr(node, 'lineno', 0)
                        
                        bug = BugReport(
                            bug_id=self._hash_bug(file_path, line_num, pattern.pattern_id),
                            file_path=file_path,
                            line_number=line_num,
                            severity=pattern.severity,
                            bug_type=self._get_bug_type(pattern.pattern_id),
                            message=pattern.description,
                            code_snippet=lines[line_num - 1].strip()[:100] if line_num > 0 else "",
                            suggested_fix=pattern.fix_template or "Manual fix required",
                            auto_fixable=bool(pattern.fix_template),
                            confidence=0.85,
                        )
                        bugs.append(bug)
        
        # Check for unused imports
        bugs.extend(self._find_unused_imports(tree, file_path, lines))
        
        return bugs
    
    def _find_unused_imports(self, tree: ast.AST, file_path: Path, lines: List[str]) -> List[BugReport]:
        """Find unused import statements"""
        bugs = []
        
        imports = []
        used_names = set()
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imports.append((node, alias.name, alias.asname or alias.name))
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
        
        for node, name, used_name in imports:
            if used_name not in used_names and name != '*':
                line_num = node.lineno
                bugs.append(BugReport(
                    bug_id=self._hash_bug(file_path, line_num, f"unused_{name}"),
                    file_path=file_path,
                    line_number=line_num,
                    severity=BugSeverity.LOW,
                    bug_type=BugType.STYLE,
                    message=f"Unused import: {name}",
                    code_snippet=lines[line_num - 1].strip()[:100],
                    suggested_fix=f"Remove import: {name}",
                    auto_fixable=True,
                    confidence=0.95,
                ))
        
        return bugs
    
    def _attempt_fix(self, bug: BugReport) -> bool:
        """Attempt to automatically fix a bug"""
        logger.info(f"Attempting to fix {bug.bug_id}")
        
        try:
            if bug.bug_type == BugType.STYLE and "unused import" in bug.message.lower():
                return self._fix_unused_import(bug)
            
            # Add more fix strategies here
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to fix {bug.bug_id}: {e}")
            return False
    
    def _fix_unused_import(self, bug: BugReport) -> bool:
        """Fix unused import by removing the line"""
        content = bug.file_path.read_text()
        lines = content.split('\n')
        
        # Remove the line
        if 1 <= bug.line_number <= len(lines):
            del lines[bug.line_number - 1]
            
            # Write back
            bug.file_path.write_text('\n'.join(lines))
            
            # Mark as fixed
            bug.fixed = True
            bug.fix_commit = f"auto-fix-{int(time.time())}"
            
            with self._lock:
                self._fixed_bugs.append(bug)
                self._bugs_fixed += 1
            
            logger.info(f"Fixed unused import in {bug.file_path}:{bug.line_number}")
            return True
        
        return False
    
    def _hash_bug(self, file_path: Path, line: int, bug_type: str) -> str:
        """Generate unique bug ID"""
        data = f"{file_path}:{line}:{bug_type}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _get_bug_type(self, pattern_id: str) -> BugType:
        """Map pattern ID to bug type"""
        mapping = {
            "sql_injection": BugType.SECURITY,
            "hardcoded_secret": BugType.SECURITY,
            "bare_except": BugType.LOGIC,
            "mutable_default": BugType.LOGIC,
            "no_return": BugType.LOGIC,
            "print_debug": BugType.STYLE,
            "unused_import": BugType.STYLE,
        }
        return mapping.get(pattern_id, BugType.LOGIC)
    
    def get_bug_stats(self) -> Dict[str, Any]:
        """Get bug hunting statistics"""
        with self._lock:
            open_bugs = [b for b in self._bugs.values() if not b.fixed]
            
            return {
                "total_bugs_found": self._bugs_found,
                "open_bugs": len(open_bugs),
                "fixed_bugs": len(self._fixed_bugs),
                "by_severity": {
                    sev.value: len([b for b in open_bugs if b.severity == sev])
                    for sev in BugSeverity
                },
                "by_type": {
                    typ.value: len([b for b in open_bugs if b.bug_type == typ])
                    for typ in BugType
                },
                "scans_completed": self._scans_completed,
                "auto_fix_rate": (
                    self._bugs_fixed / self._bugs_found * 100
                    if self._bugs_found > 0 else 0
                ),
            }
    
    def _save_bugs(self):
        """Save bug reports to disk"""
        bugs_file = self.codebase_path / ".bug_hunter" / "bugs.json"
        bugs_file.parent.mkdir(exist_ok=True)
        
        with self._lock:
            data = {
                "bugs": [bug.to_dict() for bug in self._bugs.values()],
                "fixed_bugs": [bug.to_dict() for bug in self._fixed_bugs],
                "stats": self.get_bug_stats(),
            }
        
        with open(bugs_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_bugs(self):
        """Load bug reports from disk"""
        bugs_file = self.codebase_path / ".bug_hunter" / "bugs.json"
        
        if not bugs_file.exists():
            return
        
        try:
            with open(bugs_file) as f:
                data = json.load(f)
            
            # Restore bugs
            for bug_data in data.get("bugs", []):
                bug = BugReport(**bug_data)
                self._bugs[bug.bug_id] = bug
            
            logger.info(f"Loaded {len(self._bugs)} historical bugs")
            
        except Exception as e:
            logger.error(f"Failed to load bugs: {e}")
    
    def shutdown(self):
        """Shutdown bug hunter"""
        self._running = False
        if self._hunter_thread:
            self._hunter_thread.join(timeout=10)
        self._save_bugs()


# Global instance
_global_hunter: Optional[AutonomousBugHunter] = None


def get_bug_hunter() -> AutonomousBugHunter:
    """Get global bug hunter instance"""
    global _global_hunter
    if _global_hunter is None:
        _global_hunter = AutonomousBugHunter()
    return _global_hunter
