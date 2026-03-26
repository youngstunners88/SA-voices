"""
Quantum Error Correction Codes (QEC)

Implements quantum-inspired error correction using:
- Surface code concepts
- Logical qubit encoding
- Syndrome measurement
- Automatic error correction
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)


class QubitState(Enum):
    """Quantum-like states"""
    ZERO = 0
    ONE = 1
    SUPERPOSITION = 2  # Both states simultaneously
    ENTANGLED = 3      # Linked to other qubits
    ERROR = 4          # Detected error


@dataclass
class QuantumState:
    """Represents a quantum-like state for data"""
    data_id: str
    state: QubitState
    logical_value: Any
    physical_replicas: List[Any] = field(default_factory=list)
    syndrome: Dict[str, Any] = field(default_factory=dict)
    entangled_with: Set[str] = field(default_factory=set)
    timestamp: float = field(default_factory=time.time)
    coherence_time: float = 3600.0  # 1 hour default
    
    def is_coherent(self) -> bool:
        """Check if state is still coherent"""
        return (time.time() - self.timestamp) < self.coherence_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_id": self.data_id,
            "state": self.state.name,
            "logical_value": self.logical_value,
            "replica_count": len(self.physical_replicas),
            "syndrome": self.syndrome,
            "entangled_with": list(self.entangled_with),
            "is_coherent": self.is_coherent(),
        }


class QuantumECC:
    """
    Quantum Error Correction system.
    
    Uses quantum-inspired redundancy:
    - Multiple physical replicas for each logical state
    - Syndrome measurement for error detection
    - Automatic error correction via voting
    - Entanglement for correlated error detection
    """
    
    def __init__(
        self,
        num_physical_replicas: int = 5,  # Odd number for majority voting
        syndrome_check_interval: float = 30.0,
        auto_correct: bool = True,
        enable_entanglement: bool = True,
    ):
        self.num_physical_replicas = num_physical_replicas
        self.syndrome_check_interval = syndrome_check_interval
        self.auto_correct = auto_correct
        self.enable_entanglement = enable_entanglement
        
        # State storage
        self._logical_states: Dict[str, QuantumState] = {}
        self._physical_storage: Dict[str, List[Any]] = {}
        self._syndrome_history: Dict[str, List[Dict]] = defaultdict(list)
        
        # Locks
        self._state_lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Error statistics
        self._corrections_made = 0
        self._errors_detected = 0
        
        # Start monitoring
        self._start_monitoring()
    
    def encode(self, data_id: str, value: Any) -> QuantumState:
        """
        Encode logical value into quantum-like state with redundancy.
        
        Creates multiple physical replicas for error resilience.
        """
        with self._state_lock:
            # Create physical replicas (redundancy)
            physical_replicas = [
                self._create_replica(value, i)
                for i in range(self.num_physical_replicas)
            ]
            
            # Calculate syndrome (error detection signature)
            syndrome = self._calculate_syndrome(physical_replicas)
            
            # Create logical state
            state = QuantumState(
                data_id=data_id,
                state=QubitState.SUPERPOSITION if self.enable_entanglement else QubitState.ZERO,
                logical_value=value,
                physical_replicas=physical_replicas,
                syndrome=syndrome,
            )
            
            # Store
            self._logical_states[data_id] = state
            self._physical_storage[data_id] = physical_replicas
            
            logger.debug(f"Encoded {data_id} with {self.num_physical_replicas} replicas")
            
            return state
    
    def decode(self, data_id: str) -> Optional[Any]:
        """
        Decode logical value, performing error correction if needed.
        """
        with self._state_lock:
            state = self._logical_states.get(data_id)
            if not state:
                return None
            
            # Check coherence
            if not state.is_coherent():
                logger.warning(f"State {data_id} has decohered, attempting recovery")
                state = self._recover_state(data_id)
            
            # Measure syndrome
            current_syndrome = self._calculate_syndrome(state.physical_replicas)
            
            # Detect errors
            if current_syndrome != state.syndrome:
                self._errors_detected += 1
                logger.warning(f"Error detected in {data_id}")
                
                if self.auto_correct:
                    corrected_value = self._correct_errors(data_id)
                    if corrected_value is not None:
                        state.logical_value = corrected_value
                        state.syndrome = current_syndrome
                        self._corrections_made += 1
            
            return state.logical_value
    
    def _create_replica(self, value: Any, index: int) -> Any:
        """Create a physical replica of the value"""
        # Deep copy for complex types
        if isinstance(value, (dict, list)):
            return json.loads(json.dumps(value))
        return value
    
    def _calculate_syndrome(self, replicas: List[Any]) -> Dict[str, Any]:
        """
        Calculate syndrome (error detection signature).
        
        In quantum computing, syndrome measurements detect errors
        without measuring the actual state.
        """
        if not replicas:
            return {}
        
        # Calculate checksums of all replicas
        checksums = []
        for replica in replicas:
            if isinstance(replica, (str, bytes)):
                data = replica.encode() if isinstance(replica, str) else replica
            else:
                data = json.dumps(replica, sort_keys=True).encode()
            checksums.append(hashlib.sha256(data).hexdigest()[:16])
        
        # Count unique checksums
        unique_checksums = set(checksums)
        
        return {
            "checksums": checksums,
            "unique_count": len(unique_checksums),
            "consensus": max(set(checksums), key=checksums.count) if checksums else None,
            "timestamp": time.time(),
        }
    
    def _correct_errors(self, data_id: str) -> Optional[Any]:
        """
        Correct errors using majority voting.
        
        Quantum-inspired: Use majority of physical replicas
        to determine correct logical state.
        """
        replicas = self._physical_storage.get(data_id, [])
        if not replicas:
            return None
        
        # Convert to comparable form
        serialized = [json.dumps(r, sort_keys=True) for r in replicas]
        
        # Find majority
        from collections import Counter
        counts = Counter(serialized)
        majority_value, count = counts.most_common(1)[0]
        
        # Check if majority is sufficient
        if count >= (len(replicas) // 2 + 1):
            corrected = json.loads(majority_value)
            
            # Update all replicas to match majority
            for i in range(len(replicas)):
                replicas[i] = json.loads(majority_value)
            
            logger.info(f"Corrected {data_id} using majority voting ({count}/{len(replicas)})")
            return corrected
        
        logger.error(f"Could not correct {data_id} - no clear majority")
        return None
    
    def entangle(self, data_id1: str, data_id2: str):
        """
        Create quantum-like entanglement between two states.
        
        Entangled states will be checked together for correlated errors.
        """
        with self._state_lock:
            state1 = self._logical_states.get(data_id1)
            state2 = self._logical_states.get(data_id2)
            
            if state1 and state2:
                state1.entangled_with.add(data_id2)
                state2.entangled_with.add(data_id1)
                state1.state = QubitState.ENTANGLED
                state2.state = QubitState.ENTANGLED
                
                logger.debug(f"Entangled {data_id1} <-> {data_id2}")
    
    def _check_entangled_syndromes(self):
        """Check for correlated errors in entangled states"""
        with self._state_lock:
            checked = set()
            
            for data_id, state in self._logical_states.items():
                if data_id in checked:
                    continue
                
                # Get all entangled states
                entangled_group = {data_id} | state.entangled_with
                
                # Check for correlated errors
                syndromes = [
                    self._calculate_syndrome(self._physical_storage.get(did, []))
                    for did in entangled_group
                ]
                
                # If all have errors, may be environmental
                all_corrupted = all(s["unique_count"] > 1 for s in syndromes)
                
                if all_corrupted:
                    logger.critical(
                        f"Correlated error detected in entangled group: {entangled_group}"
                    )
                    # Trigger recovery for entire group
                    for did in entangled_group:
                        self._recover_state(did)
                
                checked.update(entangled_group)
    
    def _recover_state(self, data_id: str) -> Optional[QuantumState]:
        """Attempt to recover a decohered state"""
        state = self._logical_states.get(data_id)
        if not state:
            return None
        
        # Refresh timestamp
        state.timestamp = time.time()
        
        # Recreate replicas
        state.physical_replicas = [
            self._create_replica(state.logical_value, i)
            for i in range(self.num_physical_replicas)
        ]
        
        # Recalculate syndrome
        state.syndrome = self._calculate_syndrome(state.physical_replicas)
        
        logger.info(f"Recovered state {data_id}")
        return state
    
    def _start_monitoring(self):
        """Start background syndrome monitoring"""
        self._running = True
        
        def monitor():
            while self._running:
                time.sleep(self.syndrome_check_interval)
                if self._running:
                    self._check_all_syndromes()
                    if self.enable_entanglement:
                        self._check_entangled_syndromes()
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
    
    def _check_all_syndromes(self):
        """Check syndromes for all states"""
        with self._state_lock:
            for data_id in list(self._logical_states.keys()):
                try:
                    self.decode(data_id)
                except Exception as e:
                    logger.error(f"Syndrome check failed for {data_id}: {e}")
    
    def get_quantum_stats(self) -> Dict[str, Any]:
        """Get quantum system statistics"""
        with self._state_lock:
            return {
                "logical_states": len(self._logical_states),
                "physical_replicas_total": sum(
                    len(replicas) for replicas in self._physical_storage.values()
                ),
                "entangled_pairs": sum(
                    len(state.entangled_with) for state in self._logical_states.values()
                ) // 2,
                "errors_detected": self._errors_detected,
                "corrections_made": self._corrections_made,
                "replica_count": self.num_physical_replicas,
                "coherent_states": sum(
                    1 for s in self._logical_states.values() if s.is_coherent()
                ),
            }
    
    def shutdown(self):
        """Shutdown quantum ECC system"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)


# Global instance
_global_qecc: Optional[QuantumECC] = None


def get_quantum_ecc() -> QuantumECC:
    """Get global Quantum ECC instance"""
    global _global_qecc
    if _global_qecc is None:
        _global_qecc = QuantumECC()
    return _global_qecc
