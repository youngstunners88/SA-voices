"""
Self-Learning System

Enables the agent to learn from experience, recognize patterns,
and improve performance over time without explicit prompting.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class LearningContext:
    """Context for a learning event"""
    event_type: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    performance_metrics: Dict[str, float]
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "performance_metrics": self.performance_metrics,
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "success": self.success,
            "metadata": self.metadata,
        }


@dataclass
class Pattern:
    """Recognized pattern"""
    pattern_id: str
    pattern_type: str
    signature: Dict[str, Any]
    frequency: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    success_rate: float = 0.0
    avg_performance: float = 0.0
    contexts: List[str] = field(default_factory=list)
    
    def update(self, context: LearningContext):
        """Update pattern with new context"""
        self.frequency += 1
        self.last_seen = time.time()
        
        # Update success rate
        total_success = self.success_rate * (self.frequency - 1) + (1.0 if context.success else 0.0)
        self.success_rate = total_success / self.frequency
        
        # Update average performance
        if self.performance_metric in context.performance_metrics:
            perf = context.performance_metrics[self.performance_metric]
            self.avg_performance = (
                self.avg_performance * (self.frequency - 1) + perf
            ) / self.frequency
        
        self.contexts.append(context.event_type)
        if len(self.contexts) > 100:
            self.contexts = self.contexts[-100:]


class SelfLearner:
    """
    Autonomous learning system.
    
    Learns from:
    - Task execution patterns
    - Performance metrics
    - Error conditions
    - User feedback
    - System behavior
    """
    
    def __init__(
        self,
        knowledge_dir: Path = Path("./data/knowledge"),
        learning_interval: float = 3600,  # 1 hour
        min_samples: int = 10,
    ):
        self.knowledge_dir = Path(knowledge_dir)
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        
        self.learning_interval = learning_interval
        self.min_samples = min_samples
        
        # Data storage
        self._experiences: List[LearningContext] = []
        self._patterns: Dict[str, Pattern] = {}
        self._improvements: List[Dict[str, Any]] = []
        
        # Learning state
        self._lock = threading.Lock()
        self._running = False
        self._learner_thread: Optional[threading.Thread] = None
        
        # Load existing knowledge
        self._load_knowledge()
        
        # Start background learning
        self._start_learning()
    
    def record_experience(self, context: LearningContext):
        """Record a learning experience"""
        with self._lock:
            self._experiences.append(context)
            
            # Keep only recent experiences
            if len(self._experiences) > 10000:
                self._experiences = self._experiences[-5000:]
        
        # Try to recognize pattern immediately
        self._recognize_pattern(context)
    
    def _recognize_pattern(self, context: LearningContext):
        """Recognize and record patterns"""
        # Create pattern signature
        signature = self._create_signature(context)
        pattern_id = self._hash_signature(signature)
        
        with self._lock:
            if pattern_id in self._patterns:
                self._patterns[pattern_id].update(context)
            else:
                self._patterns[pattern_id] = Pattern(
                    pattern_id=pattern_id,
                    pattern_type=context.event_type,
                    signature=signature,
                    frequency=1,
                    success_rate=1.0 if context.success else 0.0,
                )
    
    def _create_signature(self, context: LearningContext) -> Dict[str, Any]:
        """Create pattern signature from context"""
        # Simplified signature based on input/output types and key metrics
        return {
            "event_type": context.event_type,
            "input_keys": sorted(context.input_data.keys()),
            "output_keys": sorted(context.output_data.keys()),
            "success": context.success,
        }
    
    def _hash_signature(self, signature: Dict[str, Any]) -> str:
        """Hash signature to pattern ID"""
        import hashlib
        sig_str = json.dumps(signature, sort_keys=True)
        return hashlib.sha256(sig_str.encode()).hexdigest()[:16]
    
    def learn(self) -> List[Dict[str, Any]]:
        """
        Perform learning from accumulated experiences.
        
        Returns:
            List of improvements made
        """
        improvements = []
        
        with self._lock:
            if len(self._experiences) < self.min_samples:
                return improvements
            
            # Analyze patterns
            for pattern in self._patterns.values():
                if pattern.frequency >= self.min_samples:
                    improvement = self._derive_improvement(pattern)
                    if improvement:
                        improvements.append(improvement)
                        self._improvements.append(improvement)
            
            # Clear processed experiences
            self._experiences = []
        
        # Save knowledge
        self._save_knowledge()
        
        return improvements
    
    def _derive_improvement(self, pattern: Pattern) -> Optional[Dict[str, Any]]:
        """Derive improvement from pattern"""
        # Check for optimization opportunities
        if pattern.success_rate < 0.8:
            return {
                "type": "reliability_improvement",
                "pattern_id": pattern.pattern_id,
                "target": pattern.pattern_type,
                "issue": f"Low success rate: {pattern.success_rate:.2%}",
                "recommendation": "Review error handling and input validation",
                "timestamp": time.time(),
            }
        
        if pattern.avg_performance > 0:  # If we have performance metrics
            return {
                "type": "performance_optimization",
                "pattern_id": pattern.pattern_id,
                "target": pattern.pattern_type,
                "metric": "performance",
                "avg_value": pattern.avg_performance,
                "recommendation": "Consider caching or parallelization",
                "timestamp": time.time(),
            }
        
        return None
    
    def get_recommendations(self, context_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get learning-based recommendations"""
        recommendations = []
        
        with self._lock:
            for pattern in self._patterns.values():
                if context_type and pattern.pattern_type != context_type:
                    continue
                
                if pattern.frequency >= self.min_samples:
                    if pattern.success_rate > 0.9:
                        recommendations.append({
                            "type": "best_practice",
                            "context": pattern.pattern_type,
                            "confidence": pattern.success_rate,
                            "recommendation": f"This approach works well ({pattern.frequency} successes)",
                        })
                    elif pattern.success_rate < 0.5:
                        recommendations.append({
                            "type": "avoid",
                            "context": pattern.pattern_type,
                            "confidence": 1 - pattern.success_rate,
                            "recommendation": "This approach has high failure rate",
                        })
        
        return recommendations
    
    def predict_performance(
        self,
        event_type: str,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict performance based on learned patterns.
        
        Returns:
            Prediction with confidence
        """
        # Create temporary context
        temp_context = LearningContext(
            event_type=event_type,
            input_data=input_data,
            output_data={},
            performance_metrics={},
        )
        
        signature = self._create_signature(temp_context)
        pattern_id = self._hash_signature(signature)
        
        with self._lock:
            if pattern_id in self._patterns:
                pattern = self._patterns[pattern_id]
                return {
                    "predicted_success_rate": pattern.success_rate,
                    "predicted_performance": pattern.avg_performance,
                    "confidence": min(1.0, pattern.frequency / 100),
                    "based_on_samples": pattern.frequency,
                }
        
        return {
            "predicted_success_rate": 0.5,
            "predicted_performance": 0.0,
            "confidence": 0.0,
            "based_on_samples": 0,
        }
    
    def _start_learning(self):
        """Start background learning thread"""
        self._running = True
        
        def learn_loop():
            while self._running:
                time.sleep(self.learning_interval)
                if self._running:
                    try:
                        improvements = self.learn()
                        if improvements:
                            logger.info(f"Learning cycle completed: {len(improvements)} improvements")
                    except Exception as e:
                        logger.error(f"Learning error: {e}")
        
        self._learner_thread = threading.Thread(target=learn_loop, daemon=True)
        self._learner_thread.start()
    
    def _save_knowledge(self):
        """Save learned knowledge to disk"""
        knowledge_file = self.knowledge_dir / "learner_knowledge.json"
        
        with self._lock:
            data = {
                "patterns": {
                    pid: {
                        "pattern_id": p.pattern_id,
                        "pattern_type": p.pattern_type,
                        "signature": p.signature,
                        "frequency": p.frequency,
                        "success_rate": p.success_rate,
                        "avg_performance": p.avg_performance,
                        "first_seen": p.first_seen,
                        "last_seen": p.last_seen,
                    }
                    for pid, p in self._patterns.items()
                },
                "improvements": self._improvements,
            }
        
        with open(knowledge_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_knowledge(self):
        """Load knowledge from disk"""
        knowledge_file = self.knowledge_dir / "learner_knowledge.json"
        
        if not knowledge_file.exists():
            return
        
        try:
            with open(knowledge_file) as f:
                data = json.load(f)
            
            # Load patterns
            for pid, pdata in data.get("patterns", {}).items():
                self._patterns[pid] = Pattern(
                    pattern_id=pdata["pattern_id"],
                    pattern_type=pdata["pattern_type"],
                    signature=pdata["signature"],
                    frequency=pdata["frequency"],
                    success_rate=pdata["success_rate"],
                    avg_performance=pdata["avg_performance"],
                    first_seen=pdata["first_seen"],
                    last_seen=pdata["last_seen"],
                )
            
            # Load improvements
            self._improvements = data.get("improvements", [])
            
            logger.info(f"Loaded {len(self._patterns)} patterns and {len(self._improvements)} improvements")
            
        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learner statistics"""
        with self._lock:
            return {
                "total_experiences": len(self._experiences),
                "total_patterns": len(self._patterns),
                "total_improvements": len(self._improvements),
                "avg_success_rate": sum(p.success_rate for p in self._patterns.values()) / max(1, len(self._patterns)),
                "learning_interval": self.learning_interval,
            }
    
    def shutdown(self):
        """Shutdown learner"""
        self._running = False
        
        if self._learner_thread:
            self._learner_thread.join(timeout=10)
        
        self._save_knowledge()


# Global instance
_global_learner: Optional[SelfLearner] = None


def get_self_learner() -> SelfLearner:
    """Get global self-learner instance"""
    global _global_learner
    if _global_learner is None:
        _global_learner = SelfLearner()
    return _global_learner
