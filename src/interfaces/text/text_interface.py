"""
Text-as-Interface System

Provides natural language interface to all system capabilities.
Users can interact using plain text commands.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class TextCommand:
    """Parsed text command"""
    action: str
    target: str
    parameters: Dict[str, Any]
    raw_text: str
    confidence: float


class TextInterface:
    """
    Natural language interface to the system.
    
    Examples:
    - "Synthesize 'Hello' in Zulu"
    - "Check system health"
    - "Run stress test"
    - "Show bug statistics"
    - "Optimize file structure"
    """
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._patterns: List[Tuple[str, str]] = []  # (pattern, action)
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Setup natural language patterns"""
        # TTS patterns
        self._patterns.extend([
            (r"synthesize\s+['\"](.+?)['\"]\s+in\s+(\w+)", "tts_synthesize"),
            (r"speak\s+['\"](.+?)['\"]\s+in\s+(\w+)", "tts_synthesize"),
            (r"say\s+['\"](.+?)['\"]\s+in\s+(\w+)", "tts_synthesize"),
            (r"convert\s+['\"](.+?)['\"]\s+to\s+speech", "tts_synthesize"),
        ])
        
        # System patterns
        self._patterns.extend([
            (r"check\s+(system\s+)?health", "system_health"),
            (r"show\s+status", "system_health"),
            (r"get\s+stats", "system_stats"),
            (r"show\s+metrics", "system_stats"),
        ])
        
        # Testing patterns
        self._patterns.extend([
            (r"run\s+stress\s+test", "run_stress_test"),
            (r"test\s+system", "run_stress_test"),
            (r"run\s+audit", "run_audit"),
            (r"security\s+audit", "run_audit"),
        ])
        
        # Bug hunting patterns
        self._patterns.extend([
            (r"show\s+bugs", "show_bugs"),
            (r"bug\s+statistics", "show_bugs"),
            (r"find\s+bugs", "hunt_bugs"),
            (r"scan\s+for\s+bugs", "hunt_bugs"),
        ])
        
        # Optimization patterns
        self._patterns.extend([
            (r"optimize\s+file\s+structure", "optimize_structure"),
            (r"organize\s+files", "optimize_structure"),
            (r"clean\s+up\s+codebase", "optimize_structure"),
        ])
        
        # Quantum systems
        self._patterns.extend([
            (r"show\s+quantum\s+stats", "quantum_stats"),
            (r"quantum\s+ecc\s+status", "quantum_stats"),
            (r"check\s+resilience", "quantum_stats"),
        ])
        
        # Skills
        self._patterns.extend([
            (r"show\s+skills", "show_skills"),
            (r"skill\s+status", "show_skills"),
            (r"sharpen\s+skills", "sharpen_skills"),
        ])
    
    def register_handler(self, action: str, handler: Callable) -> None:
        """Register a handler for an action"""
        self._handlers[action] = handler
    
    async def process(self, text: str) -> Dict[str, Any]:
        """
        Process natural language text.
        
        Returns:
            Dict with 'success', 'action', 'result', and 'message'
        """
        # Parse command
        command = self._parse(text)
        
        if command is None:
            return {
                "success": False,
                "action": "unknown",
                "result": None,
                "message": f"I didn't understand: '{text}'. Try commands like 'synthesize Hello in Zulu' or 'check system health'."
            }
        
        # Execute handler
        handler = self._handlers.get(command.action)
        if handler is None:
            return {
                "success": False,
                "action": command.action,
                "result": None,
                "message": f"Action '{command.action}' not implemented yet."
            }
        
        try:
            result = await handler(command)
            return {
                "success": True,
                "action": command.action,
                "result": result,
                "message": self._format_result(command.action, result)
            }
        except Exception as e:
            logger.error(f"Error executing {command.action}: {e}")
            return {
                "success": False,
                "action": command.action,
                "result": None,
                "message": f"Error: {str(e)}"
            }
    
    def _parse(self, text: str) -> Optional[TextCommand]:
        """Parse text into command"""
        text = text.lower().strip()
        
        for pattern, action in self._patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Build parameters
                params = {}
                if action == "tts_synthesize" and len(groups) >= 2:
                    params["text"] = groups[0]
                    params["language"] = groups[1]
                
                return TextCommand(
                    action=action,
                    target=groups[0] if groups else "",
                    parameters=params,
                    raw_text=text,
                    confidence=0.9
                )
        
        return None
    
    def _format_result(self, action: str, result: Any) -> str:
        """Format result as human-readable text"""
        if action == "tts_synthesize":
            return f"✓ Synthesized speech: {result.get('text', '')}"
        
        elif action == "system_health":
            return f"✓ System is {result.get('status', 'unknown')}"
        
        elif action == "system_stats":
            stats = result
            return f"""System Statistics:
- Routes: {stats.get('total_routes', 0)}
- Store Entries: {stats.get('l1_size', 0)}
- Hit Rate: {stats.get('hit_rate', 0):.1%}
- Total Operations: {stats.get('total_routed', 0)}
"""
        
        elif action == "run_stress_test":
            return f"✓ Stress test completed: {result.get('passed', False)} ({result.get('success_rate', 0):.1f}% success)"
        
        elif action == "run_audit":
            return f"✓ Audit completed: {result.get('issues_found', 0)} issues found"
        
        elif action == "show_bugs":
            bugs = result
            return f"Bug Statistics:\n- Total Found: {bugs.get('total_bugs_found', 0)}\n- Open: {bugs.get('open_bugs', 0)}\n- Fixed: {bugs.get('fixed_bugs', 0)}"
        
        elif action == "optimize_structure":
            return f"✓ Structure optimized: {result.get('files_moved', 0)} files moved"
        
        elif action == "quantum_stats":
            return f"""Quantum System Status:
- States: {result.get('logical_states', 0)}
- Replicas: {result.get('physical_replicas_total', 0)}
- Corrections: {result.get('corrections_made', 0)}
- Entangled Pairs: {result.get('entangled_pairs', 0)}
"""
        
        elif action == "show_skills":
            return f"Skills Status:\n- Registered: {result.get('registered_skills', 0)}\n- Sharpening Sessions: {result.get('sharpening_sessions', 0)}"
        
        return json.dumps(result, indent=2)
    
    def get_help(self) -> str:
        """Get help text"""
        return """
Available Commands:

TTS (Text-to-Speech):
  - "Synthesize 'Hello' in Zulu"
  - "Say 'How are you?' in Afrikaans"

System:
  - "Check system health"
  - "Show status"
  - "Get stats"

Testing:
  - "Run stress test"
  - "Run audit"
  - "Security audit"

Bugs:
  - "Show bugs"
  - "Find bugs"
  - "Bug statistics"

Optimization:
  - "Optimize file structure"
  - "Organize files"
  - "Clean up codebase"

Quantum Systems:
  - "Show quantum stats"
  - "Check resilience"

Skills:
  - "Show skills"
  - "Sharpen skills"

Examples:
  - synthesize "Sawubona" in zu
  - check system health
  - run stress test
  - show quantum stats
"""


# Global instance
_global_text_interface: Optional[TextInterface] = None


def get_text_interface() -> TextInterface:
    """Get global text interface"""
    global _global_text_interface
    if _global_text_interface is None:
        _global_text_interface = TextInterface()
    return _global_text_interface
