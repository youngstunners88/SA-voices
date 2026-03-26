"""
Autonomous Bug Hunter System

Continuous, autonomous scanning and fixing of:
- Bugs
- Security vulnerabilities
- Performance issues
- Code smells
- Anti-patterns

Operates 24/7 without human intervention.
"""

from .bug_hunter import AutonomousBugHunter, BugReport
from .vulnerability_scanner import VulnerabilityScanner, SecurityFix
from .performance_hunter import PerformanceHunter, Optimization
from .fix_engine import AutonomousFixEngine, FixStrategy

__all__ = [
    "AutonomousBugHunter",
    "BugReport",
    "VulnerabilityScanner",
    "SecurityFix",
    "PerformanceHunter",
    "Optimization",
    "AutonomousFixEngine",
    "FixStrategy",
]
