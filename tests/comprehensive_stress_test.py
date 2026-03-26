"""
Comprehensive Stress Test Suite

Tests all quantum-capacity systems under extreme load.
Includes chaos engineering to test regeneration capabilities.
"""

import asyncio
import random
import time
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, '/home/teacherchris37/sa-voices')

from src.core.quantum_resilience.quantum_ecc import QuantumECC, QuantumState
from src.core.autonomous_hunter.bug_hunter import AutonomousBugHunter
from src.core.skills_fountain.fountain import SkillsFountain, SkillLevel
from src.core.chaos_engineering.chaos_monkey import ChaosMonkey, FailureType
from src.core.error_correction.filesystem import ResilientFilesystem


@dataclass
class StressTestResult:
    test_name: str
    duration_seconds: float
    operations_completed: int
    errors_encountered: int
    recovery_time_ms: float
    success_rate: float
    notes: str


class ComprehensiveStressTest:
    """Comprehensive stress testing with chaos engineering"""
    
    def __init__(self):
        self.results: List[StressTestResult] = []
        self.chaos_monkey = ChaosMonkey(enabled=True, failure_probability=0.2)
    
    async def test_quantum_ecc_stress(self) -> StressTestResult:
        """Test quantum error correction under stress"""
        print("\n" + "="*70)
        print("QUANTUM ECC STRESS TEST")
        print("="*70)
        
        qecc = QuantumECC(num_physical_replicas=5)
        
        start_time = time.time()
        operations = 0
        errors = 0
        
        # Test 1: Encode many states
        print("  Encoding 1000 quantum states...")
        for i in range(1000):
            try:
                qecc.encode(
                    f"state_{i}",
                    {"data": f"test_data_{i}", "value": i * 2}
                )
                operations += 1
            except Exception as e:
                errors += 1
        
        # Test 2: Decode with chaos
        print("  Decoding with chaos injection...")
        self.chaos_monkey._inject_failure(
            type('obj', (object,), {
                'failure_type': FailureType.DISK_CORRUPTION,
                'duration_seconds': 5,
                'intensity': 0.3,
                'auto_recover': True
            })()
        )
        
        for i in range(500):
            try:
                value = qecc.decode(f"state_{i}")
                if value:
                    operations += 1
            except Exception as e:
                errors += 1
        
        # Test 3: Entanglement stress
        print("  Testing entanglement...")
        for i in range(0, 100, 2):
            qecc.entangle(f"state_{i}", f"state_{i+1}")
        
        stats = qecc.get_quantum_stats()
        print(f"  Stats: {stats}")
        
        duration = time.time() - start_time
        
        qecc.shutdown()
        
        return StressTestResult(
            test_name="Quantum ECC Stress",
            duration_seconds=duration,
            operations_completed=operations,
            errors_encountered=errors,
            recovery_time_ms=0,
            success_rate=(operations / (operations + errors)) * 100,
            notes=f"{stats['corrections_made']} corrections made"
        )
    
    async def test_bug_hunter_stress(self) -> StressTestResult:
        """Test autonomous bug hunter"""
        print("\n" + "="*70)
        print("BUG HUNTER STRESS TEST")
        print("="*70)
        
        # Create test files with bugs
        test_dir = Path("./data/stress_test_code")
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create files with various bugs
        for i in range(20):
            content = f'''
def function_{i}(items=[]):
    try:
        print("Debug message {i}")
        result = items[0]
    except:
        pass
    return result

def another_{i}():
    password = "secret123"
    return password
'''
            (test_dir / f"test_{i}.py").write_text(content)
        
        hunter = AutonomousBugHunter(
            codebase_path=test_dir,
            scan_interval=1.0,
            auto_fix=True
        )
        
        start_time = time.time()
        
        # Wait for scanning
        print("  Waiting for bug detection...")
        await asyncio.sleep(3)
        
        stats = hunter.get_bug_stats()
        print(f"  Stats: {stats}")
        
        duration = time.time() - start_time
        
        hunter.shutdown()
        
        # Cleanup
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
        
        return StressTestResult(
            test_name="Bug Hunter Stress",
            duration_seconds=duration,
            operations_completed=stats['scans_completed'],
            errors_encountered=stats['total_bugs_found'],
            recovery_time_ms=0,
            success_rate=stats.get('auto_fix_rate', 0),
            notes=f"{stats['open_bugs']} bugs found"
        )
    
    async def test_skills_fountain_stress(self) -> StressTestResult:
        """Test skills fountain under load"""
        print("\n" + "="*70)
        print("SKILLS FOUNTAIN STRESS TEST")
        print("="*70)
        
        fountain = SkillsFountain(assessment_interval=5.0)
        
        # Register test skills
        print("  Registering 50 test skills...")
        for i in range(50):
            fountain.register_skill(
                name=f"test_skill_{i}",
                skill_instance=object(),
                initial_level=SkillLevel(random.randint(1, 4))
            )
        
        # Simulate heavy usage
        print("  Simulating heavy usage...")
        start_time = time.time()
        operations = 0
        
        for _ in range(5):  # 5 seconds of heavy usage
            for i in range(50):
                success = random.random() > 0.1  # 90% success rate
                latency = random.uniform(10, 200)
                fountain.record_usage(
                    f"test_skill_{i}",
                    success=success,
                    latency_ms=latency
                )
                operations += 1
            await asyncio.sleep(1)
        
        # Wait for sharpening
        print("  Waiting for sharpening cycles...")
        await asyncio.sleep(6)
        
        stats = fountain.get_fountain_stats()
        print(f"  Stats: {stats}")
        
        duration = time.time() - start_time
        
        fountain.shutdown()
        
        return StressTestResult(
            test_name="Skills Fountain Stress",
            duration_seconds=duration,
            operations_completed=operations,
            errors_encountered=0,
            recovery_time_ms=0,
            success_rate=stats['avg_success_rate'] * 100,
            notes=f"{stats['sharpening_sessions']} sharpening sessions"
        )
    
    async def test_resilient_fs_with_chaos(self) -> StressTestResult:
        """Test filesystem resilience with chaos"""
        print("\n" + "="*70)
        print("RESILIENT FS + CHAOS TEST")
        print("="*70)
        
        fs = ResilientFilesystem(
            base_path="./data/chaos_fs_test",
            enable_versioning=True,
            auto_backup_interval=0
        )
        
        start_time = time.time()
        operations = 0
        errors = 0
        
        # Write files
        print("  Writing 500 files...")
        for i in range(500):
            try:
                fs.write_file(
                    f"test_{i}.txt",
                    f"Content for file {i}" * 100,
                    atomic=False
                )
                operations += 1
            except Exception as e:
                errors += 1
        
        # Inject chaos
        print("  Injecting file corruption chaos...")
        self.chaos_monkey._inject_failure(
            type('obj', (object,), {
                'failure_type': FailureType.DISK_CORRUPTION,
                'duration_seconds': 3,
                'intensity': 0.2,
                'auto_recover': True
            })()
        )
        
        # Read and verify
        print("  Reading files and verifying integrity...")
        for i in range(100):
            try:
                content = fs.read_file(f"test_{i}.txt", verify_checksum=True)
                if content:
                    operations += 1
            except Exception as e:
                errors += 1
        
        stats = fs.get_stats()
        print(f"  Stats: {stats}")
        
        duration = time.time() - start_time
        
        fs.shutdown()
        
        import shutil
        shutil.rmtree("./data/chaos_fs_test", ignore_errors=True)
        
        return StressTestResult(
            test_name="Resilient FS + Chaos",
            duration_seconds=duration,
            operations_completed=operations,
            errors_encountered=errors,
            recovery_time_ms=stats.get('recovery_time_ms', 0),
            success_rate=(operations / (operations + errors)) * 100,
            notes=f"{stats.get('total_files', 0)} files managed"
        )
    
    async def test_concurrent_load(self) -> StressTestResult:
        """Test concurrent load across all systems"""
        print("\n" + "="*70)
        print("CONCURRENT LOAD TEST")
        print("="*70)
        
        qecc = QuantumECC(num_physical_replicas=3)
        fountain = SkillsFountain(assessment_interval=60.0)
        fs = ResilientFilesystem(base_path="./data/concurrent_test")
        
        # Register skills
        for i in range(10):
            fountain.register_skill(f"concurrent_skill_{i}", object())
        
        async def quantum_task(task_id: int):
            qecc.encode(f"concurrent_{task_id}", {"task": task_id})
            await asyncio.sleep(0.01)
            return qecc.decode(f"concurrent_{task_id}")
        
        async def fountain_task(task_id: int):
            fountain.record_usage(
                f"concurrent_skill_{task_id % 10}",
                success=True,
                latency_ms=random.uniform(5, 50)
            )
            return True
        
        async def fs_task(task_id: int):
            fs.write_file(f"concurrent_{task_id}.txt", f"data{task_id}", atomic=False)
            return fs.read_file(f"concurrent_{task_id}.txt", verify_checksum=False)
        
        start_time = time.time()
        
        # Run 1000 concurrent operations
        print("  Running 1000 concurrent operations...")
        tasks = []
        for i in range(1000):
            tasks.append(quantum_task(i))
            tasks.append(fountain_task(i))
            tasks.append(fs_task(i))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = sum(1 for r in results if not isinstance(r, Exception))
        errors = sum(1 for r in results if isinstance(r, Exception))
        
        duration = time.time() - start_time
        
        qecc.shutdown()
        fountain.shutdown()
        fs.shutdown()
        
        import shutil
        shutil.rmtree("./data/concurrent_test", ignore_errors=True)
        
        return StressTestResult(
            test_name="Concurrent Load",
            duration_seconds=duration,
            operations_completed=len(tasks),
            errors_encountered=errors,
            recovery_time_ms=0,
            success_rate=(successes / len(tasks)) * 100,
            notes=f"{len(tasks)} concurrent operations"
        )
    
    def _print_result(self, result: StressTestResult):
        """Print test result"""
        print(f"\n  Results:")
        print(f"    Duration: {result.duration_seconds:.2f}s")
        print(f"    Operations: {result.operations_completed}")
        print(f"    Errors: {result.errors_encountered}")
        print(f"    Success Rate: {result.success_rate:.1f}%")
        print(f"    Notes: {result.notes}")
    
    async def run_all_tests(self):
        """Run all stress tests"""
        print("\n" + "="*70)
        print("COMPREHENSIVE STRESS TEST SUITE")
        print("Quantum-Capacity System Validation")
        print("="*70)
        
        tests = [
            self.test_quantum_ecc_stress,
            self.test_bug_hunter_stress,
            self.test_skills_fountain_stress,
            self.test_resilient_fs_with_chaos,
            self.test_concurrent_load,
        ]
        
        for test in tests:
            try:
                result = await test()
                self.results.append(result)
                self._print_result(result)
            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
        
        # Summary
        print("\n" + "="*70)
        print("STRESS TEST SUMMARY")
        print("="*70)
        
        total_ops = sum(r.operations_completed for r in self.results)
        total_errors = sum(r.errors_encountered for r in self.results)
        avg_success = sum(r.success_rate for r in self.results) / max(1, len(self.results))
        
        print(f"Total Tests: {len(self.results)}")
        print(f"Total Operations: {total_ops:,}")
        print(f"Total Errors: {total_errors}")
        print(f"Average Success Rate: {avg_success:.1f}%")
        print(f"\nDetailed Results:")
        
        for result in self.results:
            status = "✅" if result.success_rate > 95 else "⚠️" if result.success_rate > 80 else "❌"
            print(f"  {status} {result.test_name}: {result.success_rate:.1f}%")
        
        # Stop chaos monkey
        self.chaos_monkey.stop()
        
        return avg_success >= 95  # Pass if overall success rate >= 95%


if __name__ == "__main__":
    suite = ComprehensiveStressTest()
    passed = asyncio.run(suite.run_all_tests())
    
    if passed:
        print("\n🎉 ALL STRESS TESTS PASSED!")
        exit(0)
    else:
        print("\n⚠️ SOME TESTS NEED ATTENTION")
        exit(1)
