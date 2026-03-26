"""
Chaos Monkey - Failure Injection System

Inspired by Netflix's Chaos Monkey, this system randomly
injects failures to test system resilience.

Failure types:
- Memory exhaustion
- CPU overload
- Disk corruption
- Network failures
- Service crashes
- Data corruption
"""

import asyncio
import os
import random
import signal
import string
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import logging

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of failures to inject"""
    MEMORY_EXHAUSTION = auto()
    CPU_SPIKE = auto()
    DISK_CORRUPTION = auto()
    FILE_DELETION = auto()
    NETWORK_FAILURE = auto()
    SERVICE_CRASH = auto()
    LATENCY_SPIKE = auto()
    ERROR_STORM = auto()


@dataclass
class FailureInjection:
    """Configuration for failure injection"""
    failure_type: FailureType
    target_service: Optional[str] = None
    duration_seconds: float = 10.0
    intensity: float = 0.5  # 0.0 to 1.0
    auto_recover: bool = True


class ChaosMonkey:
    """
    Chaos Monkey - Automated failure injection.
    
    Randomly injects failures to ensure:
    - Error correction works
    - Recovery systems function
    - Redundancy is effective
    - Monitoring detects issues
    - Alerts fire correctly
    """
    
    def __init__(
        self,
        enabled: bool = True,
        failure_interval: float = 300.0,  # 5 minutes
        failure_probability: float = 0.3,  # 30% chance per interval
        allowed_failures: Optional[Set[FailureType]] = None,
    ):
        self.enabled = enabled
        self.failure_interval = failure_interval
        self.failure_probability = failure_probability
        self.allowed_failures = allowed_failures or set(FailureType)
        
        # Statistics
        self._injections: List[Dict[str, Any]] = []
        self._recovery_times: List[float] = []
        
        # State
        self._running = False
        self._monkey_thread: Optional[threading.Thread] = None
        self._current_failure: Optional[FailureInjection] = None
        
        # Recovery handlers
        self._recovery_handlers: Dict[FailureType, Callable] = {}
        
        # Start if enabled
        if enabled:
            self._start_monkey()
    
    def _start_monkey(self):
        """Start chaos monkey"""
        self._running = True
        
        def monkey_loop():
            while self._running:
                time.sleep(self.failure_interval)
                
                if not self.enabled or not self._running:
                    continue
                
                # Decide whether to inject failure
                if random.random() < self.failure_probability:
                    self._inject_random_failure()
        
        self._monkey_thread = threading.Thread(target=monkey_loop, daemon=True)
        self._monkey_thread.start()
        logger.info("Chaos Monkey started - failures will be randomly injected")
    
    def _inject_random_failure(self):
        """Inject a random failure"""
        failure_type = random.choice(list(self.allowed_failures))
        
        injection = FailureInjection(
            failure_type=failure_type,
            duration_seconds=random.uniform(5, 30),
            intensity=random.uniform(0.3, 0.9),
            auto_recover=True,
        )
        
        logger.warning(f"CHAOS MONKEY: Injecting {failure_type.name}")
        
        try:
            self._inject_failure(injection)
        except Exception as e:
            logger.error(f"Chaos injection failed: {e}")
    
    def _inject_failure(self, injection: FailureInjection):
        """Inject a specific failure"""
        self._current_failure = injection
        start_time = time.time()
        
        # Execute failure
        if injection.failure_type == FailureType.MEMORY_EXHAUSTION:
            self._inject_memory_exhaustion(injection)
        
        elif injection.failure_type == FailureType.CPU_SPIKE:
            self._inject_cpu_spike(injection)
        
        elif injection.failure_type == FailureType.DISK_CORRUPTION:
            self._inject_disk_corruption(injection)
        
        elif injection.failure_type == FailureType.FILE_DELETION:
            self._inject_file_deletion(injection)
        
        elif injection.failure_type == FailureType.NETWORK_FAILURE:
            self._inject_network_failure(injection)
        
        elif injection.failure_type == FailureType.SERVICE_CRASH:
            self._inject_service_crash(injection)
        
        elif injection.failure_type == FailureType.LATENCY_SPIKE:
            self._inject_latency_spike(injection)
        
        elif injection.failure_type == FailureType.ERROR_STORM:
            self._inject_error_storm(injection)
        
        # Record injection
        self._injections.append({
            "type": injection.failure_type.name,
            "duration": injection.duration_seconds,
            "intensity": injection.intensity,
            "timestamp": start_time,
        })
        
        # Auto-recover
        if injection.auto_recover:
            time.sleep(injection.duration_seconds)
            self._recover_from_failure(injection)
            
            recovery_time = time.time() - start_time - injection.duration_seconds
            self._recovery_times.append(recovery_time)
            
            logger.info(f"CHAOS MONKEY: Recovered from {injection.failure_type.name} in {recovery_time:.2f}s")
        
        self._current_failure = None
    
    def _inject_memory_exhaustion(self, injection: FailureInjection):
        """Exhaust available memory"""
        logger.warning("CHAOS: Memory exhaustion injection")
        
        # Allocate large blocks
        garbage = []
        block_size = int(10 * 1024 * 1024 * injection.intensity)  # 10MB * intensity
        
        try:
            for _ in range(int(10 * injection.intensity)):
                garbage.append([0] * block_size)
        except MemoryError:
            pass  # Expected
        
        # Store for later cleanup
        self._garbage = garbage
    
    def _inject_cpu_spike(self, injection: FailureInjection):
        """Spike CPU usage"""
        logger.warning("CHAOS: CPU spike injection")
        
        def cpu_stress():
            end_time = time.time() + injection.duration_seconds
            while time.time() < end_time:
                _ = sum(i * i for i in range(10000))
        
        # Run in multiple threads
        threads = []
        for _ in range(int(4 * injection.intensity)):
            t = threading.Thread(target=cpu_stress)
            t.start()
            threads.append(t)
        
        self._cpu_threads = threads
    
    def _inject_disk_corruption(self, injection: FailureInjection):
        """Corrupt random files"""
        logger.warning("CHAOS: Disk corruption injection")
        
        # Find files to corrupt
        test_files = list(Path("./data").rglob("*.json"))[:5]
        
        for file_path in test_files:
            if random.random() < injection.intensity:
                try:
                    content = file_path.read_text()
                    # Corrupt random characters
                    corrupted = list(content)
                    for _ in range(int(len(corrupted) * 0.1 * injection.intensity)):
                        idx = random.randint(0, len(corrupted) - 1)
                        corrupted[idx] = random.choice(string.printable)
                    
                    file_path.write_text(''.join(corrupted))
                    logger.warning(f"CHAOS: Corrupted {file_path}")
                except Exception as e:
                    logger.error(f"Failed to corrupt {file_path}: {e}")
    
    def _inject_file_deletion(self, injection: FailureInjection):
        """Delete random files (will be recovered)"""
        logger.warning("CHAOS: File deletion injection")
        
        test_files = list(Path("./data/cache").glob("*.npz"))[:3]
        
        self._deleted_files = []
        for file_path in test_files:
            if file_path.exists():
                backup = file_path.with_suffix(file_path.suffix + ".backup")
                file_path.rename(backup)
                self._deleted_files.append((file_path, backup))
                logger.warning(f"CHAOS: Deleted {file_path}")
    
    def _inject_network_failure(self, injection: FailureInjection):
        """Simulate network failure"""
        logger.warning("CHAOS: Network failure injection")
        # This would disable network in real implementation
        pass
    
    def _inject_service_crash(self, injection: FailureInjection):
        """Simulate service crash"""
        logger.warning("CHAOS: Service crash injection")
        # Send signal to self
        if injection.intensity > 0.7:
            # Actually crash a worker thread
            def crash():
                raise RuntimeError("CHAOS: Simulated crash")
            
            t = threading.Thread(target=crash)
            t.start()
            t.join(timeout=1)
    
    def _inject_latency_spike(self, injection: FailureInjection):
        """Inject latency spikes"""
        logger.warning("CHAOS: Latency spike injection")
        # Add artificial delays
        time.sleep(injection.duration_seconds * injection.intensity)
    
    def _inject_error_storm(self, injection: FailureInjection):
        """Generate many errors rapidly"""
        logger.warning("CHAOS: Error storm injection")
        
        for _ in range(int(100 * injection.intensity)):
            logger.error(f"CHAOS: Injected error #{_}")
    
    def _recover_from_failure(self, injection: FailureInjection):
        """Recover from injected failure"""
        # Clean up memory
        if injection.failure_type == FailureType.MEMORY_EXHAUSTION:
            if hasattr(self, '_garbage'):
                self._garbage = []
        
        # Clean up CPU threads
        if injection.failure_type == FailureType.CPU_SPIKE:
            if hasattr(self, '_cpu_threads'):
                for t in self._cpu_threads:
                    if t.is_alive():
                        # Threads will exit when duration expires
                        pass
        
        # Restore deleted files
        if injection.failure_type == FailureType.FILE_DELETION:
            if hasattr(self, '_deleted_files'):
                for original, backup in self._deleted_files:
                    if backup.exists():
                        backup.rename(original)
                        logger.info(f"CHAOS: Restored {original}")
        
        # Trigger recovery handlers
        handler = self._recovery_handlers.get(injection.failure_type)
        if handler:
            handler(injection)
    
    def register_recovery_handler(
        self,
        failure_type: FailureType,
        handler: Callable[[FailureInjection], None]
    ):
        """Register a recovery handler"""
        self._recovery_handlers[failure_type] = handler
    
    def get_chaos_stats(self) -> Dict[str, Any]:
        """Get chaos engineering statistics"""
        return {
            "enabled": self.enabled,
            "injections_count": len(self._injections),
            "avg_recovery_time": sum(self._recovery_times) / max(1, len(self._recovery_times)),
            "injections_by_type": self._count_by_type(),
            "current_failure": (
                self._current_failure.failure_type.name
                if self._current_failure
                else None
            ),
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count injections by type"""
        from collections import Counter
        return dict(Counter(i["type"] for i in self._injections))
    
    def stop(self):
        """Stop chaos monkey"""
        self.enabled = False
        self._running = False
        
        if self._monkey_thread:
            self._monkey_thread.join(timeout=5)
        
        # Recover from any current failure
        if self._current_failure:
            self._recover_from_failure(self._current_failure)
        
        logger.info("Chaos Monkey stopped")


# Global instance
_global_monkey: Optional[ChaosMonkey] = None


def get_chaos_monkey() -> ChaosMonkey:
    """Get global chaos monkey instance"""
    global _global_monkey
    if _global_monkey is None:
        _global_monkey = ChaosMonkey(enabled=False)  # Disabled by default
    return _global_monkey
