"""
Skills Fountain - Automated Skill Sharpening

Continuously improves skills through:
- Automated training
- Performance analysis
- Pattern learning
- Self-optimization
- Scheduled sharpening

Like a fountain, skills continuously flow and improve.
"""

from .fountain import SkillsFountain, SkillLevel
from .sharpening import SkillSharpener, SharpeningSchedule
from .auto_trainer import AutoTrainer, TrainingSession

__all__ = [
    "SkillsFountain",
    "SkillLevel",
    "SkillSharpener",
    "SharpeningSchedule",
    "AutoTrainer",
    "TrainingSession",
]
