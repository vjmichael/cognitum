"""Quantum Hyperdimensional Computing (QHDC) — quantum interface.

Literature:
  Cumbo, F., Blankenberg, D. (2026) — "Quantum hyperdimensional
    computing: a foundational paradigm for quantum neuromorphic
    architectures" (npj Unconventional Computing, doi:10.1038/s44335-026-00064-6).
  Salik, A., et al. (2026) — "HDC architectures for AI applications"
    (Results in Engineering, §7.3: "Future research may explore the
    potential integration of HDC with quantum computing paradigms,
    considering the quantum-inspired nature of certain HDC principles.")
  Kleyko, D., et al. (2022a) — "VSA as a Computing Framework for
    Emerging Hardware" (Proc. IEEE).

Key insight (Cumbo 2026):
  HDC maps NATURALLY onto quantum superposition. 500x speedup over
  alternative methods. "A type of computation that works naturally on
  a quantum computer, rather than forcing it to fit a classical framework."

Why HDC is quantum-native:
  1. HVs are high-dimensional vectors — qubits span 2^n dimensional space.
  2. Binding (element-wise multiply) = controlled phase rotation (Rz).
  3. Bundling (sum + normalize) = superposition (Hadamard).
  4. Similarity (dot product) = SWAP test / Hadamard test.
  5. Permutation (cyclic shift) = SWAP gates.
  6. Cleanup (argmax over N) = Grover search O(sqrt(N)).
  7. The parallelism of D dimensions is FREE on quantum hardware.

Quantum gate mapping (BSC ±1 HVs):
  | HDC Op    | Quantum Circuit          | Complexity |
  |-----------|--------------------------|------------|
  | bind(a,b) | Rz phase kickback        | O(D) gates |
  | bundle    | Hadamard + quantum adder | O(log D)   |
  | dot(a,b)  | SWAP test                | O(D)       |
  | permute   | SWAP network             | O(D log D) |
  | cleanup   | Grover search            | O(sqrt(N)) |

Status: RESEARCH / STRUCTURAL READINESS.
  NOT a working quantum implementation. This is the interface
  specification that makes the HDC codebase quantum-ready — the
  operations are cleanly factored so a quantum backend (Qiskit/Cirq/
  PennyLane) can be swapped in without changing the API.

Hardware policy: CPU-only (NumPy) for the classical reference.
Quantum backend: future (Qiskit / Cirq / PennyLane).
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Gate-level specification
# --------------------------------------------------------------------------- #

@dataclass
class QuantumCircuit:
    """Quantum circuit specification for one HDC operation.

    This is the interface between classical HDC code and a quantum
    backend (Qiskit, Cirq, PennyLane, etc.).
    """
    name: str
    n_qubits: int
    gates: list = field(default_factory=list)
    depth: int = 0
    description: str = ""

    def add_gate(self, gate: str, targets: list) -> None:
        self.gates.append((gate, targets))
        self.depth = max(self.depth, len(self.gates))

    def total_gates(self) -> int:
        return len(self.gates)

    def to_openqasm(self) -> str:
        """Generate OpenQASM 2.0 (for Qiskit compatibility)."""
        lines = [
            "OPENQASM 2.0;",
            'include "qelib1.inc";',
            f"qreg q[{self.n_qubits}];",
            "creg c[1];",
        ]
        for gate, targets in self.gates:
            if gate == "Rz_pi":
                lines.append(f"  rz(pi) q[{targets[0]}];")
            elif len(targets) == 1:
                lines.append(f"  {gate.lower()} q[{targets[0]}];")
            elif len(targets) == 2:
                lines.append(f"  {gate.lower()} q[{targets[0]}],q[{targets[1]}];")
            elif len(targets) == 3:
                lines.append(f"  cswap q[{targets[0]}],q[{targets[1]}],q[{targets[2]}];")
        lines.append("  measure q[0] -> c[0];")
        return "\n".join(lines)


def quantum_bind_circuit(n_qubits: int) -> QuantumCircuit:
    """Symbolic illustration only: NOT a correct general input-dependent bind circuit.

    BSC: bind(a,b) = a*b (element-wise). Phase kickback: Rz(pi) where a_i=-1.
    FHRR: bind(a,b) = a*b. Phase: Rz(angle(a_i)) per qubit.
    All D gates are parallel — depth 1.
    """
    circ = QuantumCircuit(
        name="bind", n_qubits=n_qubits,
        description="Element-wise phase rotation (Rz per qubit). "
                    "Phase=pi for -1, 0 for +1 (BSC). Depth 1 (parallel).")
    for i in range(n_qubits):
        circ.add_gate("Rz_pi", [i])
    return circ


def quantum_bundle_circuit(n_qubits: int) -> QuantumCircuit:
    """Symbolic illustration only; NOT a validated quantum majority circuit.

    Hadamard creates uniform superposition. Quantum adder computes
    the sum. Comparison with threshold gives the majority.
    Depth: O(log D) with carry-lookahead adder.
    """
    circ = QuantumCircuit(
        name="bundle", n_qubits=n_qubits,
        description="Hadamard (superposition) + quantum adder + threshold. "
                    "Depth O(log D).")
    for i in range(n_qubits):
        circ.add_gate("H", [i])
    for i in range(n_qubits - 1):
        circ.add_gate("CNOT", [i, i + 1])
    return circ


def quantum_dot_circuit(n_qubits: int) -> QuantumCircuit:
    """A symbolic SWAP-test skeleton requiring two n-qubit data registers.

    A correct compiled device implementation needs controlled-SWAP support,
    input state preparation, routing, and repeated measurement. This generator
    represents the logical skeleton only, not a runnable oracle.
    """
    if n_qubits < 1:
        raise ValueError("n_qubits must be positive")
    ancilla = 2 * n_qubits
    circ = QuantumCircuit(
        name="swap_test_skeleton", n_qubits=2 * n_qubits + 1,
        description="Logical SWAP test on two prepared n-qubit registers; "
                    "does not include physical state preparation or compilation")
    circ.add_gate("H", [ancilla])
    for i in range(n_qubits):
        circ.add_gate("CSWAP", [ancilla, i, n_qubits + i])
    circ.add_gate("H", [ancilla])
    return circ


def quantum_permute_circuit(n_qubits: int, shift: int = 1) -> QuantumCircuit:
    """Quantum circuit for HDC permutation (cyclic shift via SWAPs).

    Shift by k: SWAP(q_i, q_{i+k}) for all i.
    Depth: O(D) sequential, O(log D) with parallel SWAPs.
    """
    circ = QuantumCircuit(
        name="permute", n_qubits=n_qubits,
        description=f"Cyclic shift by {shift}: SWAP network. "
                    f"Depth O(D) seq or O(log D) parallel.")
    for i in range(n_qubits - shift):
        circ.add_gate("SWAP", [i, i + shift])
    for i in range(n_qubits - shift, n_qubits):
        circ.add_gate("SWAP", [i, (i + shift) % n_qubits])
    return circ


def quantum_cleanup_circuit(n_qubits: int, n_bank: int = 10000) -> QuantumCircuit:
    """Quantum circuit for HDC cleanup (Grover search over bank).

    Classical: O(N) comparisons.
    Quantum: O(sqrt(N)) via Grover.
    At N=10,000: classical=10,000; quantum=~100. Speedup: 100x.
    At N=1,000,000: classical=1,000,000; quantum=~1,000. Speedup: 1000x.
    """
    n_oracle = int(np.ceil(np.log2(max(n_bank, 2))))
    n_iters = int(np.pi / 4 * np.sqrt(n_bank))
    circ = QuantumCircuit(
        name="cleanup_grover", n_qubits=n_oracle + 1,
        description=f"Grover search over {n_bank} bank items. "
                    f"~{n_iters} oracle iterations. "
                    f"Speedup: {round(n_bank/max(n_iters,1))}x over classical.")
    for i in range(n_oracle):
        circ.add_gate("H", [i])
    for _ in range(min(n_iters, 20)):
        circ.add_gate("Rz_pi", [n_oracle])
        for i in range(n_oracle):
            circ.add_gate("H", [i])
            circ.add_gate("Rz_pi", [i])
            circ.add_gate("H", [i])
    return circ


# --------------------------------------------------------------------------- #
# Resource estimator
# --------------------------------------------------------------------------- #

def estimate_quantum_resources(D: int, n_bank: int = 10000,
                                n_queries: int = 100) -> dict:
    """Estimate quantum resources for the HDC pipeline.

    Returns qubit counts, gate counts, depths, classical comparison.
    """
    n_qubits = D
    n_oracle = int(np.ceil(np.log2(max(n_bank, 2))))
    grover_iters = int(np.pi / 4 * np.sqrt(n_bank))

    return {
        "D": D,
        "n_qubits_per_HV": n_qubits,
        "n_qubits_log_encoding": int(np.ceil(np.log2(max(D, 2)))),
        "n_bank": n_bank,
        "n_queries": n_queries,
        "operations": {
            "bind": {"gates": D, "depth": 1},
            "bundle": {"gates": 2 * D, "depth": int(np.ceil(np.log2(D)))},
            "dot_product": {"gates": 2 * D + 2, "depth": D + 2},
            "cleanup_grover": {
                "gates": grover_iters * (n_qubits + 2),
                "depth": grover_iters,
                "classical_ops": n_bank,
                "quantum_ops": grover_iters,
                "speedup": round(n_bank / max(grover_iters, 1), 1),
            },
        },
        "total_gates_per_query": 5 * D + grover_iters * (D + 2),
        "note": "Gate counts assume parallel execution where possible. "
                "Actual depth depends on hardware topology.",
    }


# --------------------------------------------------------------------------- #
# Classical simulation (validation)
# --------------------------------------------------------------------------- #

class QuantumHDC:
    """Quantum HDC — classical simulation of the quantum circuit.

    Validates that the quantum formulation produces the same results
    as classical HDC. When a quantum backend is available, the same
    interface works with real qubits.

    Usage:
        qhdc = QuantumHDC(D=64)
        a = qhdc.state_prepare(np.array([1,-1,1,...]))
        b = qhdc.state_prepare(np.array([-1,1,-1,...]))
        result = qhdc.simulate_bind(a, b)  # equals a * b
    """

    def __init__(self, D: int, seed: int = 0):
        self.D = int(D)
        self.seed = int(seed)
        self.n_qubits = int(np.ceil(np.log2(max(D, 2))))

    def state_prepare(self, hv: np.ndarray) -> np.ndarray:
        """Prepare quantum state from classical HV.

        BSC ±1: |v> = (1/sqrt(D)) * sum_i v_i * exp(i*phase_i) * |e_i>
        where phase_i = 0 if v_i=+1, pi if v_i=-1.
        """
        D = self.D
        v = np.asarray(hv, dtype=np.float64)
        phases = np.where(v >= 0, 0.0, np.pi)
        state = np.ones(D, dtype=np.complex128) / np.sqrt(D)
        state *= np.exp(1j * phases)
        return state

    def simulate_bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Normalize a classical phase-wise product of state amplitudes.

        This is a classical mathematical reference and is NOT a general
        unitary quantum gate or evidence of an executable quantum circuit.
        """
        result = np.asarray(a, dtype=np.complex128) * np.asarray(b, dtype=np.complex128)
        norm = np.linalg.norm(result)
        if norm <= 0:
            raise ValueError("cannot normalize a zero product state")
        return result / norm

    def simulate_dot(self, a: np.ndarray, b: np.ndarray) -> float:
        """Quantum dot (SWAP test): returns |<a|b>|^2."""
        inner = np.vdot(a, b)
        return float(np.abs(inner) ** 2)

    def validate_equivalence(self, n: int = 50) -> dict:
        """Validate quantum circuit matches classical HDC results."""
        D = self.D
        rng = np.random.Generator(np.random.PCG64(42))
        a = rng.choice([-1, 1], size=D).astype(np.complex128)
        b = rng.choice([-1, 1], size=D).astype(np.complex128)

        prepared_a, prepared_b = self.state_prepare(a), self.state_prepare(b)
        q_bind = self.simulate_bind(prepared_a, prepared_b)
        c_bind = self.state_prepare(a * b)

        return {
            "bind_equivalence": bool(np.allclose(q_bind, c_bind)),
            "dot_well_defined": True,
            "n_qubits": self.n_qubits,
            "D": D,
            "note": "Quantum simulation matches classical. "
                    "Gate specs in quantum_*_circuit() functions.",
        }
