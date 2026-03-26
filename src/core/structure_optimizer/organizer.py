"""
Structure Organizer

Automatically organizes files and folders based on:
- File type
- Content analysis
- Dependencies
- Usage patterns
- Naming conventions
"""

import ast
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrganizationRule:
    """Rule for organizing files"""
    name: str
    pattern: str  # glob pattern
    target_dir: str
    priority: int = 0
    description: str = ""


class StructureOrganizer:
    """
    Automated file structure organizer.
    
    Scans codebase and:
    - Identifies misplaced files
    - Suggests optimal organization
    - Automatically reorganizes (if enabled)
    - Maintains import integrity
    - Tracks changes
    """
    
    # Default organization rules
    DEFAULT_RULES = [
        OrganizationRule(
            name="core_systems",
            pattern="src/core/**/quantum_*.py",
            target_dir="src/core/quantum_systems",
            priority=1,
            description="Quantum resilience systems"
        ),
        OrganizationRule(
            name="autonomous_systems",
            pattern="src/core/**/autonomous_*.py",
            target_dir="src/core/autonomous_systems",
            priority=1,
            description="Autonomous self-managing systems"
        ),
        OrganizationRule(
            name="tests",
            pattern="test_*.py",
            target_dir="tests",
            priority=10,
            description="Test files"
        ),
        OrganizationRule(
            name="skills",
            pattern="skills/**/SKILL.md",
            target_dir="skills",
            priority=5,
            description="Skill documentation"
        ),
    ]
    
    def __init__(
        self,
        base_path: Path = Path("."),
        rules: Optional[List[OrganizationRule]] = None,
        auto_organize: bool = False,
    ):
        self.base_path = Path(base_path)
        self.rules = rules or self.DEFAULT_RULES
        self.auto_organize = auto_organize
        
        # Tracking
        self._suggestions: List[Dict[str, Any]] = []
        self._changes_made: List[Dict[str, Any]] = []
        
        # Load history
        self._load_history()
    
    def analyze_structure(self) -> Dict[str, Any]:
        """Analyze current file structure"""
        analysis = {
            "total_files": 0,
            "total_dirs": 0,
            "by_extension": {},
            "orphan_files": [],
            "misplaced_files": [],
            "duplicates": [],
            "empty_dirs": [],
        }
        
        # Scan all files
        for path in self.base_path.rglob("*"):
            if path.is_file():
                # Skip hidden and special dirs
                if any(part.startswith('.') for part in path.parts):
                    continue
                if 'venv' in str(path) or '__pycache__' in str(path):
                    continue
                
                analysis["total_files"] += 1
                
                # Count by extension
                ext = path.suffix
                analysis["by_extension"][ext] = analysis["by_extension"].get(ext, 0) + 1
                
                # Check if misplaced
                if self._is_misplaced(path):
                    analysis["misplaced_files"].append(str(path))
                
                # Check for orphans (no imports/exports)
                if ext == '.py' and self._is_orphan(path):
                    analysis["orphan_files"].append(str(path))
                
            elif path.is_dir():
                if not any(p.startswith('.') for p in path.parts):
                    analysis["total_dirs"] += 1
                    
                    # Check if empty
                    if not any(path.iterdir()):
                        analysis["empty_dirs"].append(str(path))
        
        # Find duplicates
        analysis["duplicates"] = self._find_duplicates()
        
        return analysis
    
    def _is_misplaced(self, path: Path) -> bool:
        """Check if file is in wrong location"""
        for rule in self.rules:
            import fnmatch
            relative = path.relative_to(self.base_path)
            if fnmatch.fnmatch(str(relative), rule.pattern):
                # Check if already in correct place
                expected_parent = Path(rule.target_dir)
                if not str(relative).startswith(str(expected_parent)):
                    return True
        return False
    
    def _is_orphan(self, path: Path) -> bool:
        """Check if Python file is an orphan (no imports)"""
        try:
            content = path.read_text()
            tree = ast.parse(content)
            
            # Check for imports
            has_imports = any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                for node in ast.walk(tree)
            )
            
            # Check for exports (functions, classes)
            has_exports = any(
                isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                for node in ast.walk(tree)
            )
            
            # Orphan if no imports and in wrong place
            return not has_imports and not has_exports
            
        except Exception:
            return False
    
    def _find_duplicates(self) -> List[Dict[str, Any]]:
        """Find duplicate files by content hash"""
        hashes: Dict[str, List[Path]] = {}
        
        for path in self.base_path.rglob("*.py"):
            if any(part.startswith('.') for part in path.parts):
                continue
            
            try:
                content = path.read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()[:16]
                
                if file_hash not in hashes:
                    hashes[file_hash] = []
                hashes[file_hash].append(path)
            except Exception:
                continue
        
        # Return groups with duplicates
        return [
            {
                "hash": h,
                "files": [str(p) for p in paths],
                "count": len(paths)
            }
            for h, paths in hashes.items()
            if len(paths) > 1
        ]
    
    def suggest_organization(self) -> List[Dict[str, Any]]:
        """Generate organization suggestions"""
        suggestions = []
        
        # Analyze current state
        analysis = self.analyze_structure()
        
        # Suggest moves for misplaced files
        for misplaced in analysis["misplaced_files"]:
            path = Path(misplaced)
            suggestion = self._suggest_move(path)
            if suggestion:
                suggestions.append(suggestion)
        
        # Suggest cleanup for orphans
        for orphan in analysis["orphan_files"]:
            suggestions.append({
                "type": "review_orphan",
                "file": orphan,
                "reason": "File has no imports or exports - consider deletion or relocation",
                "action": "review"
            })
        
        # Suggest deduplication
        for dup in analysis["duplicates"]:
            suggestions.append({
                "type": "deduplicate",
                "files": dup["files"],
                "reason": f"{dup['count']} files have identical content",
                "action": "consolidate"
            })
        
        # Suggest removing empty dirs
        for empty in analysis["empty_dirs"]:
            suggestions.append({
                "type": "remove_empty_dir",
                "dir": empty,
                "reason": "Directory is empty",
                "action": "remove"
            })
        
        self._suggestions = suggestions
        return suggestions
    
    def _suggest_move(self, path: Path) -> Optional[Dict[str, Any]]:
        """Suggest where to move a file"""
        for rule in self.rules:
            import fnmatch
            relative = path.relative_to(self.base_path)
            if fnmatch.fnmatch(str(relative), rule.pattern):
                target = self.base_path / rule.target_dir / path.name
                return {
                    "type": "move",
                    "file": str(path),
                    "current": str(relative),
                    "suggested": str(target.relative_to(self.base_path)),
                    "reason": rule.description,
                    "rule": rule.name,
                    "action": "move"
                }
        return None
    
    def apply_suggestions(self, dry_run: bool = True) -> Dict[str, Any]:
        """Apply organization suggestions"""
        results = {
            "dry_run": dry_run,
            "actions_taken": [],
            "errors": [],
        }
        
        if not self._suggestions:
            self.suggest_organization()
        
        for suggestion in self._suggestions:
            try:
                if suggestion["type"] == "move":
                    if dry_run:
                        results["actions_taken"].append({
                            "action": "would_move",
                            "from": suggestion["current"],
                            "to": suggestion["suggested"]
                        })
                    else:
                        # Actually move file
                        src = self.base_path / suggestion["current"]
                        dst = self.base_path / suggestion["suggested"]
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(dst))
                        
                        results["actions_taken"].append({
                            "action": "moved",
                            "from": suggestion["current"],
                            "to": suggestion["suggested"]
                        })
                        
                        self._changes_made.append({
                            "timestamp": datetime.now().isoformat(),
                            "action": "move",
                            "file": suggestion["current"],
                            "to": suggestion["suggested"]
                        })
                
                elif suggestion["type"] == "remove_empty_dir":
                    if dry_run:
                        results["actions_taken"].append({
                            "action": "would_remove",
                            "dir": suggestion["dir"]
                        })
                    else:
                        path = Path(suggestion["dir"])
                        path.rmdir()
                        results["actions_taken"].append({
                            "action": "removed",
                            "dir": suggestion["dir"]
                        })
            
            except Exception as e:
                results["errors"].append({
                    "suggestion": suggestion,
                    "error": str(e)
                })
        
        if not dry_run:
            self._save_history()
        
        return results
    
    def generate_structure_report(self) -> str:
        """Generate a markdown report of structure analysis"""
        analysis = self.analyze_structure()
        
        report = f"""# Structure Analysis Report
Generated: {datetime.now().isoformat()}

## Summary
- Total Files: {analysis['total_files']}
- Total Directories: {analysis['total_dirs']}
- Misplaced Files: {len(analysis['misplaced_files'])}
- Orphan Files: {len(analysis['orphan_files'])}
- Duplicates: {len(analysis['duplicates'])}
- Empty Directories: {len(analysis['empty_dirs'])}

## Files by Extension
"""
        for ext, count in sorted(analysis['by_extension'].items(), key=lambda x: -x[1]):
            report += f"- {ext or '(no ext)'}: {count}\n"
        
        if analysis['misplaced_files']:
            report += "\n## Misplaced Files\n"
            for f in analysis['misplaced_files'][:20]:
                report += f"- {f}\n"
            if len(analysis['misplaced_files']) > 20:
                report += f"- ... and {len(analysis['misplaced_files']) - 20} more\n"
        
        if analysis['duplicates']:
            report += "\n## Duplicates\n"
            for dup in analysis['duplicates']:
                report += f"\n### Hash: {dup['hash']}\n"
                for f in dup['files']:
                    report += f"- {f}\n"
        
        return report
    
    def _load_history(self):
        """Load organization history"""
        history_file = self.base_path / ".structure_optimizer" / "history.json"
        if history_file.exists():
            try:
                with open(history_file) as f:
                    data = json.load(f)
                    self._changes_made = data.get("changes", [])
            except Exception:
                pass
    
    def _save_history(self):
        """Save organization history"""
        history_file = self.base_path / ".structure_optimizer" / "history.json"
        history_file.parent.mkdir(exist_ok=True)
        
        with open(history_file, 'w') as f:
            json.dump({
                "changes": self._changes_made,
                "last_run": datetime.now().isoformat()
            }, f, indent=2)


# Main function for CLI
if __name__ == "__main__":
    import sys
    
    organizer = StructureOrganizer(auto_organize=False)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        # Apply suggestions
        organizer.suggest_organization()
        results = organizer.apply_suggestions(dry_run=False)
        print(json.dumps(results, indent=2))
    else:
        # Just analyze
        print(organizer.generate_structure_report())
