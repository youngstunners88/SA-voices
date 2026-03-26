"""
System Monitoring & Health Checks

Provides comprehensive monitoring, health checks, and alerting
for the SA Voices system.
"""

import asyncio
import json
import platform
import resource
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import threading
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    response_time_ms: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class SystemMetrics:
    """System performance metrics"""
    timestamp: datetime
    cpu_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_used_gb: float
    disk_total_gb: float
    open_files: int
    thread_count: int
    uptime_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "memory_percent": (self.memory_used_mb / self.memory_total_mb) * 100,
            "disk_used_gb": self.disk_used_gb,
            "disk_total_gb": self.disk_total_gb,
            "disk_percent": (self.disk_used_gb / self.disk_total_gb) * 100,
            "open_files": self.open_files,
            "thread_count": self.thread_count,
            "uptime_seconds": self.uptime_seconds,
        }


class SystemMonitor:
    """
    Comprehensive system monitor.
    
    Features:
    - Health checks for all components
    - Performance metrics collection
    - Alerting on threshold breaches
    - Automatic remediation
    - Historical data storage
    """
    
    def __init__(
        self,
        data_dir: Path = Path("./data/monitoring"),
        check_interval: float = 30.0,
        metrics_history_hours: int = 24,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.check_interval = check_interval
        self.metrics_history_hours = metrics_history_hours
        
        # Health checks registry
        self._health_checks: Dict[str, Callable[[], asyncio.Future[HealthCheck]]] = {}
        
        # Thresholds
        self._thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "response_time_ms": 5000.0,
        }
        
        # Alert handlers
        self._alert_handlers: List[Callable[[str, Dict], None]] = []
        
        # Metrics storage
        self._metrics: List[SystemMetrics] = []
        self._metrics_lock = threading.Lock()
        
        # Health history
        self._health_history: List[Dict[str, HealthCheck]] = []
        
        # State
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._start_time = time.time()
        
        # Load historical data
        self._load_data()
    
    def register_health_check(
        self,
        name: str,
        check_func: Callable[[], asyncio.Future[HealthCheck]]
    ):
        """Register a health check"""
        self._health_checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    def set_threshold(self, metric: str, value: float):
        """Set alert threshold"""
        self._thresholds[metric] = value
    
    def add_alert_handler(self, handler: Callable[[str, Dict], None]):
        """Add alert handler"""
        self._alert_handlers.append(handler)
    
    async def run_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        for name, check_func in self._health_checks.items():
            start_time = time.time()
            try:
                result = await check_func()
                result.response_time_ms = (time.time() - start_time) * 1000
                results[name] = result
            except Exception as e:
                results[name] = HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(e)}",
                    timestamp=datetime.now(),
                    response_time_ms=(time.time() - start_time) * 1000,
                )
        
        # Store in history
        self._health_history.append(results)
        if len(self._health_history) > 1000:
            self._health_history = self._health_history[-1000:]
        
        return results
    
    def collect_metrics(self) -> SystemMetrics:
        """Collect system metrics"""
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_total_mb = memory.total / (1024 * 1024)
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        
        # Process info
        process = psutil.Process()
        open_files = len(process.open_files())
        thread_count = process.num_threads()
        
        # Uptime
        uptime_seconds = time.time() - self._start_time
        
        metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            open_files=open_files,
            thread_count=thread_count,
            uptime_seconds=uptime_seconds,
        )
        
        # Store metrics
        with self._metrics_lock:
            self._metrics.append(metrics)
            
            # Trim old metrics
            cutoff = datetime.now().timestamp() - (self.metrics_history_hours * 3600)
            self._metrics = [
                m for m in self._metrics
                if m.timestamp.timestamp() > cutoff
            ]
        
        # Check thresholds
        self._check_thresholds(metrics)
        
        return metrics
    
    def _check_thresholds(self, metrics: SystemMetrics):
        """Check metrics against thresholds"""
        alerts = []
        
        if metrics.cpu_percent > self._thresholds["cpu_percent"]:
            alerts.append({
                "metric": "cpu_percent",
                "value": metrics.cpu_percent,
                "threshold": self._thresholds["cpu_percent"],
            })
        
        memory_percent = (metrics.memory_used_mb / metrics.memory_total_mb) * 100
        if memory_percent > self._thresholds["memory_percent"]:
            alerts.append({
                "metric": "memory_percent",
                "value": memory_percent,
                "threshold": self._thresholds["memory_percent"],
            })
        
        disk_percent = (metrics.disk_used_gb / metrics.disk_total_gb) * 100
        if disk_percent > self._thresholds["disk_percent"]:
            alerts.append({
                "metric": "disk_percent",
                "value": disk_percent,
                "threshold": self._thresholds["disk_percent"],
            })
        
        # Trigger alerts
        for alert in alerts:
            self._trigger_alert("threshold_breach", alert)
    
    def _trigger_alert(self, alert_type: str, data: Dict):
        """Trigger alert handlers"""
        for handler in self._alert_handlers:
            try:
                handler(alert_type, data)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")
    
    def get_overall_health(self, checks: Dict[str, HealthCheck]) -> HealthStatus:
        """Calculate overall health status"""
        if not checks:
            return HealthStatus.UNKNOWN
        
        statuses = [c.status for c in checks.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        
        if any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        
        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        # Run checks if we have recent results
        if self._health_history:
            latest_checks = self._health_history[-1]
        else:
            latest_checks = {}
        
        return {
            "overall_status": self.get_overall_health(latest_checks).value,
            "checks": {name: check.to_dict() for name, check in latest_checks.items()},
            "total_checks": len(self._health_checks),
            "healthy_checks": sum(1 for c in latest_checks.values() if c.status == HealthStatus.HEALTHY),
        }
    
    def get_metrics_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get metrics summary for recent period"""
        cutoff = datetime.now().timestamp() - (minutes * 60)
        
        with self._metrics_lock:
            recent_metrics = [
                m for m in self._metrics
                if m.timestamp.timestamp() > cutoff
            ]
        
        if not recent_metrics:
            return {"error": "No metrics available"}
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [(m.memory_used_mb / m.memory_total_mb) * 100 for m in recent_metrics]
        
        return {
            "period_minutes": minutes,
            "sample_count": len(recent_metrics),
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "min": min(cpu_values),
                "max": max(cpu_values),
            },
            "memory": {
                "avg_percent": sum(memory_values) / len(memory_values),
                "min_percent": min(memory_values),
                "max_percent": max(memory_values),
                "current_mb": recent_metrics[-1].memory_used_mb,
            },
            "uptime_hours": recent_metrics[-1].uptime_seconds / 3600,
        }
    
    def _save_data(self):
        """Save monitoring data to disk"""
        # Save metrics
        metrics_file = self.data_dir / "metrics.json"
        with self._metrics_lock:
            with open(metrics_file, 'w') as f:
                json.dump([m.to_dict() for m in self._metrics], f)
        
        # Save health history
        health_file = self.data_dir / "health.json"
        with open(health_file, 'w') as f:
            json.dump([
                {name: check.to_dict() for name, check in checks.items()}
                for checks in self._health_history
            ], f)
    
    def _load_data(self):
        """Load monitoring data from disk"""
        # Load metrics
        metrics_file = self.data_dir / "metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file) as f:
                    data = json.load(f)
                    self._metrics = [
                        SystemMetrics(
                            timestamp=datetime.fromisoformat(m["timestamp"]),
                            cpu_percent=m["cpu_percent"],
                            memory_used_mb=m["memory_used_mb"],
                            memory_total_mb=m["memory_total_mb"],
                            disk_used_gb=m["disk_used_gb"],
                            disk_total_gb=m["disk_total_gb"],
                            open_files=m["open_files"],
                            thread_count=m["thread_count"],
                            uptime_seconds=m["uptime_seconds"],
                        )
                        for m in data
                    ]
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")
    
    def start_monitoring(self):
        """Start background monitoring"""
        if self._running:
            return
        
        self._running = True
        
        def monitor_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            while self._running:
                try:
                    # Collect metrics
                    self.collect_metrics()
                    
                    # Run health checks
                    loop.run_until_complete(self.run_health_checks())
                    
                    # Save data periodically
                    if len(self._metrics) % 10 == 0:
                        self._save_data()
                    
                    time.sleep(self.check_interval)
                    
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    time.sleep(self.check_interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        
        self._save_data()
        
        logger.info("System monitoring stopped")


# Predefined health checks
async def check_filesystem_health() -> HealthCheck:
    """Check filesystem health"""
    try:
        # Check if data directory is writable
        test_file = Path("./data/health_check_test")
        test_file.write_text("test")
        test_file.unlink()
        
        return HealthCheck(
            name="filesystem",
            status=HealthStatus.HEALTHY,
            message="Filesystem is accessible and writable",
            timestamp=datetime.now(),
            response_time_ms=0,
        )
    except Exception as e:
        return HealthCheck(
            name="filesystem",
            status=HealthStatus.UNHEALTHY,
            message=f"Filesystem check failed: {str(e)}",
            timestamp=datetime.now(),
            response_time_ms=0,
        )


async def check_memory_health() -> HealthCheck:
    """Check memory health"""
    try:
        import psutil
        
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        if memory_percent > 90:
            status = HealthStatus.UNHEALTHY
            message = f"Critical memory usage: {memory_percent:.1f}%"
        elif memory_percent > 75:
            status = HealthStatus.DEGRADED
            message = f"High memory usage: {memory_percent:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Memory usage normal: {memory_percent:.1f}%"
        
        return HealthCheck(
            name="memory",
            status=status,
            message=message,
            timestamp=datetime.now(),
            response_time_ms=0,
            metadata={
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent": memory_percent,
            }
        )
    except Exception as e:
        return HealthCheck(
            name="memory",
            status=HealthStatus.UNKNOWN,
            message=f"Memory check failed: {str(e)}",
            timestamp=datetime.now(),
            response_time_ms=0,
        )


async def check_disk_health() -> HealthCheck:
    """Check disk health"""
    try:
        import psutil
        
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        
        if disk_percent > 95:
            status = HealthStatus.UNHEALTHY
            message = f"Critical disk usage: {disk_percent:.1f}%"
        elif disk_percent > 85:
            status = HealthStatus.DEGRADED
            message = f"High disk usage: {disk_percent:.1f}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Disk usage normal: {disk_percent:.1f}%"
        
        return HealthCheck(
            name="disk",
            status=status,
            message=message,
            timestamp=datetime.now(),
            response_time_ms=0,
            metadata={
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent": disk_percent,
            }
        )
    except Exception as e:
        return HealthCheck(
            name="disk",
            status=HealthStatus.UNKNOWN,
            message=f"Disk check failed: {str(e)}",
            timestamp=datetime.now(),
            response_time_ms=0,
        )


# Global monitor instance
_global_monitor: Optional[SystemMonitor] = None


def get_system_monitor() -> SystemMonitor:
    """Get or create global system monitor"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = SystemMonitor()
        
        # Register default health checks
        _global_monitor.register_health_check("filesystem", check_filesystem_health)
        _global_monitor.register_health_check("memory", check_memory_health)
        _global_monitor.register_health_check("disk", check_disk_health)
    
    return _global_monitor
