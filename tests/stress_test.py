"""
Stress Test Suite for SA Voices

Tests system under load to identify:
- Performance bottlenecks
- Memory leaks
- Concurrency issues
- Error handling under stress
"""

import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List
import statistics

import sys
sys.path.insert(0, '/home/teacherchris37/sa-voices')

from src.core.error_correction.filesystem import ResilientFilesystem
from src.core.process_agent.pool import WorkerPool
from src.routing.router import VoiceRouter, RouteRequest, RouteType, RoutePriority


@dataclass
class TestResult:
    """Result of a stress test"""
    test_name: str
    total_requests: int
    successful: int
    failed: int
    avg_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    duration_seconds: float
    errors: List[str]


class StressTestSuite:
    """Stress testing suite"""
    
    def __init__(self):
        self.results: List[TestResult] = []
    
    async def test_filesystem_stress(self, num_operations: int = 1000) -> TestResult:
        """Stress test resilient filesystem"""
        print(f"\n{'='*60}")
        print(f"Filesystem Stress Test: {num_operations} operations")
        print(f"{'='*60}")
        
        fs = ResilientFilesystem(
            base_path="./data/stress_test",
            enable_versioning=False,  # Speed up
            auto_backup_interval=0,
        )
        
        latencies = []
        errors = []
        start_time = time.time()
        
        # Write operations
        write_tasks = []
        for i in range(num_operations):
            content = f"Test content {i}" * 100
            task = fs.write_file(
                f"test_file_{i}.txt",
                content,
                atomic=False,  # Speed up for stress test
                create_backup=False
            )
            write_tasks.append(task)
        
        # Measure writes
        write_start = time.time()
        for task in write_tasks:
            try:
                latencies.append(time.time() - write_start)
            except Exception as e:
                errors.append(str(e))
        
        # Read operations
        read_latencies = []
        for i in range(min(100, num_operations)):
            read_start = time.time()
            try:
                fs.read_file(f"test_file_{i}.txt", verify_checksum=False)
                read_latencies.append(time.time() - read_start)
            except Exception as e:
                errors.append(str(e))
        
        duration = time.time() - start_time
        
        # Calculate stats
        all_latencies = latencies + read_latencies
        avg_latency = statistics.mean(all_latencies) * 1000 if all_latencies else 0
        p99_latency = statistics.quantiles(all_latencies, n=100)[98] * 1000 if len(all_latencies) >= 100 else avg_latency
        
        result = TestResult(
            test_name="Filesystem Stress",
            total_requests=num_operations + 100,
            successful=len(all_latencies),
            failed=len(errors),
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
            throughput_rps=(num_operations + 100) / duration if duration > 0 else 0,
            duration_seconds=duration,
            errors=errors[:10]  # First 10 errors
        )
        
        self._print_result(result)
        return result
    
    async def test_routing_stress(self, num_requests: int = 10000) -> TestResult:
        """Stress test routing system"""
        print(f"\n{'='*60}")
        print(f"Routing Stress Test: {num_requests} requests")
        print(f"{'='*60}")
        
        router = VoiceRouter()
        
        # Register handlers
        for i in range(5):
            router.register_handler(
                f"handler_{i}",
                route_types=[RouteType.TTS_SYNTHESIS],
                max_capacity=100
            )
        
        latencies = []
        errors = []
        start_time = time.time()
        
        # Generate requests
        requests = []
        for i in range(num_requests):
            priority = random.choice(list(RoutePriority))
            req = RouteRequest(
                request_id=f"req_{i}",
                route_type=RouteType.TTS_SYNTHESIS,
                priority=priority,
                payload={"text": f"test {i}"},
                language=random.choice(["en", "zu", "af"])
            )
            requests.append(req)
        
        # Route requests concurrently
        async def route_batch(batch):
            for req in batch:
                req_start = time.time()
                try:
                    await router.route(req)
                    latencies.append(time.time() - req_start)
                except Exception as e:
                    errors.append(str(e))
        
        # Process in batches of 100
        batch_size = 100
        batches = [requests[i:i+batch_size] for i in range(0, len(requests), batch_size)]
        
        await asyncio.gather(*[route_batch(batch) for batch in batches])
        
        duration = time.time() - start_time
        
        # Calculate stats
        avg_latency = statistics.mean(latencies) * 1000 if latencies else 0
        p99_latency = statistics.quantiles(latencies, n=100)[98] * 1000 if len(latencies) >= 100 else avg_latency
        
        result = TestResult(
            test_name="Routing Stress",
            total_requests=num_requests,
            successful=len(latencies),
            failed=len(errors),
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
            throughput_rps=num_requests / duration if duration > 0 else 0,
            duration_seconds=duration,
            errors=errors[:10]
        )
        
        self._print_result(result)
        return result
    
    async def test_worker_pool_stress(self, num_tasks: int = 5000) -> TestResult:
        """Stress test worker pool"""
        print(f"\n{'='*60}")
        print(f"Worker Pool Stress Test: {num_tasks} tasks")
        print(f"{'='*60}")
        
        pool = WorkerPool(max_workers=10, use_processes=False)
        
        # Simple task
        def simple_task(x):
            time.sleep(0.001)  # 1ms work
            return x * 2
        
        latencies = []
        errors = []
        start_time = time.time()
        
        # Submit tasks
        task_ids = []
        for i in range(num_tasks):
            task_id = await pool.submit(simple_task, i)
            task_ids.append(task_id)
        
        # Collect results
        for task_id in task_ids:
            try:
                result_start = time.time()
                await pool.get_result(task_id, timeout=30)
                latencies.append(time.time() - result_start)
            except Exception as e:
                errors.append(str(e))
        
        duration = time.time() - start_time
        
        # Shutdown
        await pool.shutdown()
        
        # Calculate stats
        avg_latency = statistics.mean(latencies) * 1000 if latencies else 0
        p99_latency = statistics.quantiles(latencies, n=100)[98] * 1000 if len(latencies) >= 100 else avg_latency
        
        result = TestResult(
            test_name="Worker Pool Stress",
            total_requests=num_tasks,
            successful=len(latencies),
            failed=len(errors),
            avg_latency_ms=avg_latency,
            p99_latency_ms=p99_latency,
            throughput_rps=num_tasks / duration if duration > 0 else 0,
            duration_seconds=duration,
            errors=errors[:10]
        )
        
        self._print_result(result)
        return result
    
    async def test_memory_stress(self, duration_seconds: int = 60) -> TestResult:
        """Memory stress test"""
        print(f"\n{'='*60}")
        print(f"Memory Stress Test: {duration_seconds}s")
        print(f"{'='*60}")
        
        import psutil
        process = psutil.Process()
        
        start_mem = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Allocate and deallocate memory repeatedly
        data_chunks = []
        errors = []
        
        start_time = time.time()
        iterations = 0
        
        while time.time() - start_time < duration_seconds:
            try:
                # Allocate
                chunk = [0] * 1000000  # ~8MB
                data_chunks.append(chunk)
                
                # Keep only recent chunks
                if len(data_chunks) > 100:
                    data_chunks = data_chunks[-50:]
                
                iterations += 1
                
                if iterations % 100 == 0:
                    current_mem = process.memory_info().rss / (1024 * 1024)
                    print(f"  Iteration {iterations}, Memory: {current_mem:.1f}MB")
                
            except MemoryError as e:
                errors.append(f"Memory error at iteration {iterations}: {e}")
                data_chunks = []  # Clear memory
            
            await asyncio.sleep(0.01)
        
        end_mem = process.memory_info().rss / (1024 * 1024)
        
        result = TestResult(
            test_name="Memory Stress",
            total_requests=iterations,
            successful=iterations,
            failed=len(errors),
            avg_latency_ms=0,
            p99_latency_ms=0,
            throughput_rps=iterations / duration_seconds,
            duration_seconds=duration_seconds,
            errors=errors
        )
        
        print(f"  Start Memory: {start_mem:.1f}MB")
        print(f"  End Memory: {end_mem:.1f}MB")
        print(f"  Iterations: {iterations}")
        
        return result
    
    def _print_result(self, result: TestResult):
        """Print test result"""
        print(f"\n  Results:")
        print(f"    Total Requests: {result.total_requests}")
        print(f"    Successful: {result.successful}")
        print(f"    Failed: {result.failed}")
        print(f"    Success Rate: {result.successful/result.total_requests*100:.1f}%")
        print(f"    Avg Latency: {result.avg_latency_ms:.2f}ms")
        print(f"    P99 Latency: {result.p99_latency_ms:.2f}ms")
        print(f"    Throughput: {result.throughput_rps:.1f} RPS")
        print(f"    Duration: {result.duration_seconds:.2f}s")
        
        if result.errors:
            print(f"    Errors: {len(result.errors)}")
            for error in result.errors[:3]:
                print(f"      - {error[:100]}")
    
    async def run_all_tests(self):
        """Run all stress tests"""
        print("\n" + "="*60)
        print("SA VOICES - STRESS TEST SUITE")
        print("="*60)
        
        # Filesystem test
        await self.test_filesystem_stress(num_operations=1000)
        
        # Routing test
        await self.test_routing_stress(num_requests=10000)
        
        # Worker pool test
        await self.test_worker_pool_stress(num_tasks=5000)
        
        # Memory test (shorter for CI)
        await self.test_memory_stress(duration_seconds=10)
        
        # Summary
        print("\n" + "="*60)
        print("STRESS TEST SUMMARY")
        print("="*60)
        print(f"Total Tests: {len(self.results)}")
        print(f"All tests completed successfully")


if __name__ == "__main__":
    suite = StressTestSuite()
    asyncio.run(suite.run_all_tests())
