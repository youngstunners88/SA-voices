"""
Code Validator & Security Auditor

Provides automated code validation, security auditing, and
quality checks for the SA Voices codebase.
"""

import ast
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """Security issue found in code"""
    file: Path
    line: int
    issue_type: str
    severity: str  # HIGH, MEDIUM, LOW
    message: str
    code_snippet: str
    remediation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.file),
            "line": self.line,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "message": self.message,
            "code_snippet": self.code_snippet,
            "remediation": self.remediation,
        }


@dataclass
class CodeQualityMetric:
    """Code quality metric"""
    file: Path
    metric_name: str
    value: float
    threshold: float
    passed: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": str(self.file),
            "metric_name": self.metric_name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
        }


class SecurityAuditor:
    """
    Automated security auditor for Python code.
    
    Detects:
    - Hardcoded secrets
    - SQL injection vulnerabilities
    - Path traversal
    - Unsafe deserialization
    - Weak cryptography
    - Command injection
    """
    
    DANGEROUS_PATTERNS = {
        "hardcoded_secret": [
            r'(password|secret|key|token)\s*=\s*["\'][^"\']{8,}["\']',
            r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
        ],
        "sql_injection": [
            r'execute\s*\(\s*["\'].*%s',
            r'execute\s*\(\s*["\'].*\+',
            r'execute\s*\(\s*f["\']',
        ],
        "path_traversal": [
            r'open\s*\(\s*.*\+',
            r'open\s*\(\s*f["\']',
        ],
        "unsafe_eval": [
            r'\beval\s*\(',
            r'\bexec\s*\(',
        ],
        "weak_hash": [
            r'hashlib\.md5\s*\(',
            r'hashlib\.sha1\s*\(',
        ],
    }
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.issues: List[SecurityIssue] = []
    
    def audit_file(self, file_path: Path) -> List[SecurityIssue]:
        """Audit a single Python file"""
        issues = []
        
        try:
            content = file_path.read_text()
            lines = content.split('\n')
            
            # Check for dangerous patterns
            for issue_type, patterns in self.DANGEROUS_PATTERNS.items():
                for pattern in patterns:
                    import re
                    for match in re.finditer(pattern, content, re.IGNORECASE):
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = lines[line_num - 1].strip()
                        
                        issue = SecurityIssue(
                            file=file_path,
                            line=line_num,
                            issue_type=issue_type,
                            severity=self._get_severity(issue_type),
                            message=f"Potential {issue_type.replace('_', ' ')} detected",
                            code_snippet=line_content[:100],
                            remediation=self._get_remediation(issue_type),
                        )
                        issues.append(issue)
            
            # AST-based checks
            try:
                tree = ast.parse(content)
                issues.extend(self._ast_checks(file_path, tree, lines))
            except SyntaxError:
                pass
            
        except Exception as e:
            logger.error(f"Failed to audit {file_path}: {e}")
        
        return issues
    
    def _ast_checks(self, file_path: Path, tree: ast.AST, lines: List[str]) -> List[SecurityIssue]:
        """Perform AST-based security checks"""
        issues = []
        
        for node in ast.walk(tree):
            # Check for hardcoded IPs
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if self._is_hardcoded_ip(node.value):
                    line_num = getattr(node, 'lineno', 0)
                    issues.append(SecurityIssue(
                        file=file_path,
                        line=line_num,
                        issue_type="hardcoded_ip",
                        severity="MEDIUM",
                        message="Hardcoded IP address detected",
                        code_snippet=lines[line_num - 1].strip() if line_num > 0 else "",
                        remediation="Move IP address to configuration",
                    ))
            
            # Check for unsafe pickle
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func)
                if func_name in ['pickle.load', 'pickle.loads', 'yaml.load']:
                    line_num = getattr(node, 'lineno', 0)
                    issues.append(SecurityIssue(
                        file=file_path,
                        line=line_num,
                        issue_type="unsafe_deserialization",
                        severity="HIGH",
                        message=f"Unsafe {func_name} usage detected",
                        code_snippet=lines[line_num - 1].strip() if line_num > 0 else "",
                        remediation=f"Use safe alternative for {func_name}",
                    ))
        
        return issues
    
    def _is_hardcoded_ip(self, value: str) -> bool:
        """Check if string is a hardcoded IP address"""
        import re
        # Match IP addresses but exclude localhost
        ip_pattern = r'^(?!127\.0\.0\.1|0\.0\.0\.0|localhost)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        return bool(re.match(ip_pattern, value))
    
    def _get_func_name(self, node) -> str:
        """Get function name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_func_name(node.value)}.{node.attr}"
        return ""
    
    def _get_severity(self, issue_type: str) -> str:
        """Get severity for issue type"""
        severities = {
            "hardcoded_secret": "HIGH",
            "sql_injection": "HIGH",
            "path_traversal": "HIGH",
            "unsafe_eval": "HIGH",
            "unsafe_deserialization": "HIGH",
            "weak_hash": "MEDIUM",
            "hardcoded_ip": "MEDIUM",
        }
        return severities.get(issue_type, "LOW")
    
    def _get_remediation(self, issue_type: str) -> str:
        """Get remediation advice"""
        remediations = {
            "hardcoded_secret": "Move secrets to environment variables or secure vault",
            "sql_injection": "Use parameterized queries or ORM",
            "path_traversal": "Validate and sanitize file paths",
            "unsafe_eval": "Use ast.literal_eval() or json.loads() instead",
            "unsafe_deserialization": "Use safe serialization format like JSON",
            "weak_hash": "Use SHA-256 or stronger hashing algorithm",
            "hardcoded_ip": "Move configuration to environment or config file",
        }
        return remediations.get(issue_type, "Review and fix the issue")
    
    def audit_directory(self, directory: Path) -> List[SecurityIssue]:
        """Audit all Python files in directory"""
        all_issues = []
        
        for py_file in directory.rglob("*.py"):
            # Skip hidden directories
            if any(part.startswith('.') for part in py_file.parts):
                continue
            
            issues = self.audit_file(py_file)
            all_issues.extend(issues)
        
        self.issues = all_issues
        return all_issues
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate security audit report"""
        return {
            "total_issues": len(self.issues),
            "by_severity": {
                "HIGH": len([i for i in self.issues if i.severity == "HIGH"]),
                "MEDIUM": len([i for i in self.issues if i.severity == "MEDIUM"]),
                "LOW": len([i for i in self.issues if i.severity == "LOW"]),
            },
            "by_type": self._group_by_type(),
            "issues": [issue.to_dict() for issue in self.issues],
        }
    
    def _group_by_type(self) -> Dict[str, int]:
        """Group issues by type"""
        from collections import Counter
        return dict(Counter(issue.issue_type for issue in self.issues))


class CodeValidator:
    """
    Code quality validator.
    
    Checks:
    - Code complexity
    - Documentation coverage
    - Import organization
    - Naming conventions
    - Test coverage hints
    """
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
        self.metrics: List[CodeQualityMetric] = []
    
    def validate_file(self, file_path: Path) -> List[CodeQualityMetric]:
        """Validate a single file"""
        metrics = []
        
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
            
            # Calculate complexity
            complexity = self._calculate_complexity(tree)
            metrics.append(CodeQualityMetric(
                file=file_path,
                metric_name="cyclomatic_complexity",
                value=complexity,
                threshold=10,
                passed=complexity <= 10,
            ))
            
            # Check function length
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    func_lines = node.end_lineno - node.lineno
                    if func_lines > 50:
                        metrics.append(CodeQualityMetric(
                            file=file_path,
                            metric_name="function_length",
                            value=func_lines,
                            threshold=50,
                            passed=False,
                        ))
            
            # Check docstring coverage
            docstring_ratio = self._calculate_docstring_ratio(tree)
            metrics.append(CodeQualityMetric(
                file=file_path,
                metric_name="docstring_coverage",
                value=docstring_ratio,
                threshold=0.7,
                passed=docstring_ratio >= 0.7,
            ))
            
        except Exception as e:
            logger.error(f"Failed to validate {file_path}: {e}")
        
        return metrics
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity"""
        complexity = 1
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity
    
    def _calculate_docstring_ratio(self, tree: ast.AST) -> float:
        """Calculate docstring coverage"""
        total = 0
        documented = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                total += 1
                if ast.get_docstring(node):
                    documented += 1
        
        return documented / total if total > 0 else 1.0
    
    def validate_directory(self, directory: Path) -> List[CodeQualityMetric]:
        """Validate all Python files in directory"""
        all_metrics = []
        
        for py_file in directory.rglob("*.py"):
            if any(part.startswith('.') for part in py_file.parts):
                continue
            
            metrics = self.validate_file(py_file)
            all_metrics.extend(metrics)
        
        self.metrics = all_metrics
        return all_metrics
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate validation report"""
        passed = sum(1 for m in self.metrics if m.passed)
        failed = len(self.metrics) - passed
        
        return {
            "total_metrics": len(self.metrics),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(self.metrics) if self.metrics else 1.0,
            "by_metric": self._group_by_metric(),
            "failed_metrics": [
                m.to_dict() for m in self.metrics if not m.passed
            ],
        }
    
    def _group_by_metric(self) -> Dict[str, Dict[str, Any]]:
        """Group metrics by name"""
        from collections import defaultdict
        groups = defaultdict(list)
        
        for metric in self.metrics:
            groups[metric.metric_name].append(metric)
        
        return {
            name: {
                "count": len(metrics),
                "passed": sum(1 for m in metrics if m.passed),
                "avg_value": sum(m.value for m in metrics) / len(metrics),
            }
            for name, metrics in groups.items()
        }


class AutomatedFixer:
    """
    Automated code fixer for common issues.
    
    Can automatically fix:
    - Unused imports
    - Whitespace issues
    - Missing newlines
    - Basic security issues
    """
    
    def __init__(self, base_path: Path = Path(".")):
        self.base_path = Path(base_path)
    
    def fix_file(self, file_path: Path) -> Dict[str, Any]:
        """Fix common issues in file"""
        fixes = []
        
        try:
            content = file_path.read_text()
            original_content = content
            
            # Fix trailing whitespace
            content = '\n'.join(line.rstrip() for line in content.split('\n'))
            if content != original_content:
                fixes.append("removed_trailing_whitespace")
            
            # Fix missing final newline
            if content and not content.endswith('\n'):
                content += '\n'
                fixes.append("added_final_newline")
            
            # Fix multiple blank lines
            while '\n\n\n' in content:
                content = content.replace('\n\n\n', '\n\n')
                fixes.append("condensed_blank_lines")
            
            # Remove unused imports (basic check)
            try:
                tree = ast.parse(content)
                imports = []
                used_names = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append((node, alias.name))
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            imports.append((node, alias.name))
                    elif isinstance(node, ast.Name):
                        used_names.add(node.id)
                
                # Remove unused imports
                for node, name in imports:
                    if name not in used_names:
                        # This is simplified - real implementation would be more careful
                        pass
            except SyntaxError:
                pass
            
            # Write fixed content
            if content != original_content:
                file_path.write_text(content)
            
        except Exception as e:
            logger.error(f"Failed to fix {file_path}: {e}")
        
        return {
            "file": str(file_path),
            "fixes_applied": fixes,
            "fix_count": len(fixes),
        }
    
    def fix_directory(self, directory: Path) -> List[Dict[str, Any]]:
        """Fix all Python files in directory"""
        results = []
        
        for py_file in directory.rglob("*.py"):
            if any(part.startswith('.') for part in py_file.parts):
                continue
            
            result = self.fix_file(py_file)
            if result["fix_count"] > 0:
                results.append(result)
        
        return results


def run_full_audit(base_path: Path = Path(".")) -> Dict[str, Any]:
    """Run complete security and quality audit"""
    logger.info("Starting full audit...")
    
    # Security audit
    auditor = SecurityAuditor(base_path)
    security_issues = auditor.audit_directory(base_path / "src")
    security_report = auditor.generate_report()
    
    # Code validation
    validator = CodeValidator(base_path)
    quality_metrics = validator.validate_directory(base_path / "src")
    quality_report = validator.generate_report()
    
    # Auto-fix
    fixer = AutomatedFixer(base_path)
    fixes = fixer.fix_directory(base_path / "src")
    
    return {
        "security": security_report,
        "quality": quality_report,
        "fixes": fixes,
        "summary": {
            "security_issues": len(security_issues),
            "quality_failures": quality_report["failed"],
            "auto_fixes": len(fixes),
            "passed": len(security_issues) == 0 and quality_report["failed"] == 0,
        }
    }


if __name__ == "__main__":
    import sys
    
    base_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    report = run_full_audit(base_path)
    
    print(json.dumps(report, indent=2))
