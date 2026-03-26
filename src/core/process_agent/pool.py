"""
Worker Pool for Task Execution

Manages a pool of workers for parallel task execution.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, TypeVar, Generic
import time
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task definition"""
    task_id: str
    func: Callable[..., T]
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    retry_count: int = 0
    max_retries: int = 0


@dataclass
class TaskResult:
    """Task execution result"""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries: int = 0


class WorkerPool:
    """
    Worker pool for parallel task execution.
    
    Supports both thread and process workers.
    """
    
    def __init__(
        self,
        max_workers: int = 4,
        use_processes: bool = False,
        queue_size: int = 100,
    ):
        self.max_workers = max_workers
        self.use_processes = use_processes
        self.queue_size = queue_size
        
        # Executor
        if use_processes:
            self._executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Task tracking
        self._tasks: Dict[str, Task] = {}
        self._futures: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        
        # Metrics
        self._completed = 0
        self._failed = 0
        self._total_time = 0.0
    
    async def submit(
        self,
        func: Callable[..., T],
        *args,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        **kwargs
    ) -> str:
        """
        Submit a task to the pool.
        
        Returns:
            Task ID
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        async with self._lock:
            if len(self._tasks) >= self.queue_size:
                raise RuntimeError("Task queue is full")
            
            self._tasks[task_id] = task
        
        # Execute
        asyncio.create_task(self._execute_task(task))
        
        return task_id
    
    async def _execute_task(self, task: Task):
        """Execute a task"""
        task.started_at = time.time()
        task.status = TaskStatus.RUNNING
        
        try:
            # Run in executor
            loop = asyncio.get_event_loop()
            
            if asyncio.iscoroutinefunction(task.func):
                # Async function
                if task.timeout:
                    result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs),
                        timeout=task.timeout
                    )
                else:
                    result = await task.func(*task.args, **task.kwargs)
            else:
                # Sync function - run in executor
                future = loop.run_in_executor(
                    self._executor,
                    lambda: task.func(*task.args, **task.kwargs)
                )
                
                if task.timeout:
                    result = await asyncio.wait_for(future, timeout=task.timeout)
                else:
                    result = await future
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            
            async with self._lock:
                self._completed += 1
            
        except Exception as e:
            task.error = e
            task.status = TaskStatus.FAILED
            
            # Retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.warning(f"Retrying task {task.task_id} (attempt {task.retry_count})")
                await asyncio.sleep(2 ** task.retry_count)  # Exponential backoff
                asyncio.create_task(self._execute_task(task))
                return
            
            async with self._lock:
                self._failed += 1
        
        finally:
            task.completed_at = time.time()
            if task.started_at:
                duration = task.completed_at - task.started_at
                async with self._lock:
                    self._total_time += duration
    
    async def get_result(self, task_id: str, timeout: Optional[float] = None) -> TaskResult:
        """Get task result, waiting if necessary"""
        start_time = time.time()
        
        while True:
            async with self._lock:
                task = self._tasks.get(task_id)
            
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                duration = (task.completed_at or time.time()) - (task.started_at or task.created_at)
                return TaskResult(
                    task_id=task_id,
                    success=task.status == TaskStatus.COMPLETED,
                    result=task.result,
                    error=task.error,
                    duration_seconds=duration,
                    retries=task.retry_count,
                )
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Timeout waiting for task {task_id}")
            
            await asyncio.sleep(0.1)
    
    async def map(
        self,
        func: Callable[[T], R],
        items: List[T],
        max_concurrent: Optional[int] = None
    ) -> List[R]:
        """
        Map function over items in parallel.
        
        Args:
            func: Function to apply
            items: Items to process
            max_concurrent: Max concurrent tasks
        
        Returns:
            Results in same order as input
        """
        if max_concurrent is None:
            max_concurrent = self.max_workers
        
        # Create tasks
        tasks = []
        for item in items:
            task_id = await self.submit(func, item)
            tasks.append(task_id)
        
        # Collect results
        results = []
        for task_id in tasks:
            result = await self.get_result(task_id)
            if result.success:
                results.append(result.result)
            else:
                raise result.error or RuntimeError("Task failed")
        
        return results
    
    async def shutdown(self, wait: bool = True, cancel_futures: bool = False):
        """Shutdown the worker pool"""
        if cancel_futures:
            async with self._lock:
                for task in self._tasks.values():
                    if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                        task.status = TaskStatus.CANCELLED
        
        if wait:
            # Wait for all tasks to complete
            while True:
                async with self._lock:
                    active = sum(
                        1 for t in self._tasks.values()
                        if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
                    )
                
                if active == 0:
                    break
                
                await asyncio.sleep(0.1)
        
        self._executor.shutdown(wait=wait)
        logger.info("Worker pool shutdown")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        async with self._lock:
            active = sum(
                1 for t in self._tasks.values()
                if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
            )
            
            avg_time = self._total_time / max(1, self._completed + self._failed)
            
            return {
                "max_workers": self.max_workers,
                "active_tasks": active,
                "total_tasks": len(self._tasks),
                "completed": self._completed,
                "failed": self._failed,
                "avg_task_time": avg_time,
                "use_processes": self.use_processes,
            }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()


# Type variable for map function
R = TypeVar('R')
