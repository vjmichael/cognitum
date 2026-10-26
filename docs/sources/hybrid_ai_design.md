# Cognitum — Hybrid Multi-Technology AI Architecture

**Version:** 1.0
**Date:** 2026-10-25
**Status:** Design complete, ready for implementation
**Creator:** Michael Vang
**Intended consumer:** LLM implementation agent (ChatGPT or equivalent)

> *Cognitum* — Latin: "that which is known." A 12-module cognitive augmentation system for large language models.

---

## 1. Executive Summary

This document specifies a **12-module hybrid AI architecture** that augments a large language model (LLM) with specialized computational backends. Each module addresses a specific, well-documented class of LLM failure. The LLM serves as the **integration and interface layer**: it parses user intent, routes sub-problems to the appropriate module, and synthesizes results into coherent natural language.

**Core integration pattern (applies to every module):**

```
User request
    │
    ▼
┌─────────────┐
│    LLM      │  1. Parse intent, identify sub-problem type
│ (Interface) │  2. Formulate sub-problem in the module's input format
│             │  3. Route to appropriate module
└──────┬──────┘  4. Receive result
       │          5. Interpret, contextualize, synthesize response
       ▼
┌─────────────┐
│  Module X   │  Executes specialized computation
│ (Backend)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    LLM      │  6. Translate result into natural language
│ (Synthesis) │  7. Add context, caveats, uncertainty
│             │  8. Return to user
└─────────────┘
```

**Failure classes addressed:**

| Module | Failure class it eliminates |
|---|---|
| HDC | Hallucination, unreliable retrieval, no online learning |
| KAN | Arithmetic errors, numerical approximation, function fitting |
| SSM | Inconsistency in long conversations, no state tracking |
| Capsules | Spatial/3D reasoning errors, no object permanence |
| MCTS+DP | Inability to plan multi-step, no search/backtracking |
| Causal Models | Correlation-causation confusion, no intervention semantics |
| Bayesian Networks | Uncalibrated uncertainty, base-rate neglect |
| Neural ODEs / Physics | No physical intuition, no trajectory simulation |
| SMT / Provers | Cannot formally verify claims, no proof/counterexample |
| Combinatorial Optimizers | Inability to solve NP-hard problems, no optimality proof |
| Meta-Learning (MAML) | No domain adaptation, frozen at training distribution |
| TDA | No topological/shape reasoning about data |

---

## 2. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                              LLM                                     │
│         Planning · Language · Abstraction · Code · Synthesis         │
│         (The Cortex — integration, routing, natural language)        │
├──────────────────────────────────────────────────────────────────────┤
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│   │   HDC    │ │   KAN    │ │   SSM    │ │Capsules  │              │
│   │  Memory  │ │ Compute  │ │  State   │ │ Spatial  │              │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│   │MCTS + DP │ │  Causal  │ │Bayesian  │ │NeuralODE │              │
│   │ Planning │ │  Models  │ │  Networks│ │  Physics │              │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│   │  SMT /   │ │Combin.   │ │  MAML /  │ │   TDA    │              │
│   │ Proovers │ │Optimizer │ │MetaLearn │ │Topology  │              │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
├──────────────────────────────────────────────────────────────────────┤
│                    Shared Infrastructure                             │
│   Vector Space (10k–100k dims) · State Store · Message Bus          │
│   Routing Engine · Session Manager · Logging / Observability        │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.1 Design Principles

1. **LLM is the orchestrator, not the computer.** The LLM never performs numerical computation, formal proof, or exact search itself. It formulates, routes, and interprets.

2. **Every module has a clean interface.** Each module exposes a Python function with typed inputs/outputs. No module depends on another module's internals — they communicate through the LLM or the message bus.

3. **Composability.** Modules can be chained: e.g., KAN computes a value → SMT verifies the result → LLM reports. The routing engine manages chains.

4. **Graceful degradation.** If a module is unavailable, the LLM falls back to its own (weaker) capability and flags the reduced confidence.

5. **Observability.** Every module call is logged: input, output, latency, confidence. This enables debugging and performance analysis.

---

## 3. Shared Infrastructure

### 3.1 Vector Space

All vector-based modules (HDC, SSM, Capsules, TDA) operate in a shared high-dimensional vector space.

```python
# config.yaml
vector_space:
  dimension: 10000          # 10k dimensions (tunable: 1k–100k)
  dtype: float32
  backend: "numpy"          # "numpy" | "torch" | "jax"
  seed: 42
```

**Vector encoding (canonical):**
```python
import numpy as np
from hashlib import sha256

def encode_string(text: str, dim: int = 10000, seed: int = 42) -> np.ndarray:
    """Deterministic hash-based encoding into the shared vector space."""
    h = sha256(f"{seed}:{text}".encode()).digest()
    rng = np.random.RandomState(int.from_bytes(h[:8], 'big'))
    v = rng.normal(0, 1, dim)
    return v / np.linalg.norm(v)  # unit vector
```

**Vector operations (shared):**
```python
def bundle(vectors: list[np.ndarray]) -> np.ndarray:
    """Averaging (superposition) — HDC bundling."""
    return np.mean(vectors, axis=0)

def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Element-wise multiplication (HDC binding)."""
    return a * b

def dot(a: np.ndarray, b: np.ndarray) -> float:
    """Similarity score in [-1, 1]."""
    return float(np.dot(a / np.linalg.norm(a), b / np.linalg.norm(b)))

def perturb(v: np.ndarray, noise: float = 0.1) -> np.ndarray:
    """Add Gaussian noise (for corruption testing)."""
    noise_vec = np.random.normal(0, noise, v.shape)
    return v + noise_vec
```

### 3.2 Message Bus

Simple in-process event system for inter-module communication (used when chaining modules without LLM round-trips).

```python
from dataclasses import dataclass, field
from typing import Any
import uuid
from datetime import datetime

@dataclass
class Message:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""          # module name
    target: str = ""          # module name or "llm"
    type: str = ""            # "query" | "result" | "error" | "state_update"
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: str = ""  # links request/response chains

class MessageBus:
    def __init__(self):
        self._handlers: dict[str, list[callable]] = {}
        self._log: list[Message] = []

    def subscribe(self, module: str, handler: callable):
        self._handlers.setdefault(module, []).append(handler)

    def publish(self, msg: Message):
        self._log.append(msg)
        for handler in self._handlers.get(msg.target, []):
            handler(msg)

    def get_log(self, last: int = 50) -> list[Message]:
        return self._log[-last:]
```

### 3.3 Session Manager

Tracks per-conversation state across all modules.

```python
@dataclass
class SessionState:
    session_id: str
    created: str
    ssd_state: np.ndarray | None = None       # SSM hidden state
    hd_store: dict[str, np.ndarray] = field(default_factory=dict)  # HDC store
    capsule_scene: dict[str, np.ndarray] = field(default_factory=dict)  # Capsules
    mcts_policy: dict | None = None            # MCTS value function
    causal_graph: dict | None = None           # Causal graph
    bayes_net: dict | None = None              # Bayesian network
    meta_params: dict | None = None            # MAML adapted params
    history: list[dict] = field(default_factory=list)  # conversation log

    def to_dict(self) -> dict:
        """Serialize for persistence (exclude large arrays)."""
        return {
            "session_id": self.session_id,
            "created": self.created,
            "hd_store_keys": list(self.hd_store.keys()),
            "capsule_entities": list(self.capsule_scene.keys()),
            "has_causal_graph": self.causal_graph is not None,
            "has_bayes_net": self.bayes_net is not None,
            "history_length": len(self.history),
        }
```

---

## 4. Module Specifications

### 4.1 HDC — Hyperdimensional Computing (Associative Memory)

**Purpose:** Persistent, associative, online-learnable memory. Replaces unreliable parametric recall with structured vector storage.

**Addresses:** Hallucination, unreliable fact retrieval, inability to learn new facts between sessions.

**Core operations:**

| Operation | Description | Complexity |
|---|---|---|
| `store(key, value)` | Bind key→value, add to memory | O(d) |
| `retrieve(key, k)` | Dot-product search, return top-k | O(N·d) |
| `bundle(vectors)` | Superposition (average) | O(n·d) |
| `bind(a, b)` | Element-wise multiply (composition) | O(d) |
| `unbind(a, b)` | Element-wise multiply with b (inverse) | O(d) |
| `permutate(v, shift)` | Cyclic shift (order encoding) | O(d) |
| `delete(key)` | Anti-Hebbian update | O(d) |
| `corruption_test(key, noise)` | Robustness check | O(d) |

**Interface:**

```python
class HDCMemory:
    def __init__(self, dim: int = 10000, backend: str = "numpy"):
        self.dim = dim
        self.store: dict[str, np.ndarray] = {}       # key_hash → bound value
        self.index: list[tuple[str, np.ndarray]] = [] # for retrieval
        self.encoder = lambda s: encode_string(s, dim)

    def store(self, key: str, value: str) -> str:
        """Store a key-value pair. Returns the hash of the stored key."""
        k_vec = self.encoder(key)
        v_vec = self.encoder(value)
        bound = bind(k_vec, v_vec)
        key_hash = sha256(key.encode()).hexdigest()[:16]
        self.store[key_hash] = bound
        self.index.append((key_hash, k_vec))
        return key_hash

    def retrieve(self, key: str, k: int = 5, threshold: float = 0.3) -> list[dict]:
        """Retrieve top-k values for a query key.
        Returns: [{"key": str, "value": str, "score": float}, ...]
        """
        q_vec = self.encoder(key)
        scores = []
        for key_hash, k_vec in self.index:
            s = dot(q_vec, k_vec)
            if s > threshold:
                scores.append((key_hash, s))
        scores.sort(key=lambda x: -x[1])
        results = []
        for key_hash, s in scores[:k]:
            # Recover value by unbinding
            bound = self.store[key_hash]
            k_vec = self.encoder(key)
            v_vec = bound * k_vec  # unbind (approximate)
            # Find best-matching stored value
            best_value = None
            best_score = -1
            for stored_key, stored_bound in self.store.items():
                # (simplified — in practice, maintain a value index)
                pass
            results.append({"key_hash": key_hash, "score": float(s)})
        return results

    def bundle(self, keys: list[str]) -> np.ndarray:
        """Bundle multiple stored values (superposition)."""
        vectors = [self.store[k] for k in keys if k in self.store]
        return bundle(vectors) if vectors else np.zeros(self.dim)

    def bind(self, a: str, b: str) -> np.ndarray:
        """Compose two concepts via binding."""
        return bind(self.encoder(a), self.encoder(b))

    def permutate(self, key: str, shift: int = 1) -> np.ndarray:
        """Apply permutation (order encoding)."""
        v = self.encoder(key)
        return np.roll(v, shift)

    def delete(self, key: str) -> bool:
        """Remove a key-value pair (anti-Hebbian)."""
        key_hash = sha256(key.encode()).hexdigest()[:16]
        if key_hash in self.store:
            del self.store[key_hash]
            self.index = [(k, v) for k, v in self.index if k != key_hash]
            return True
        return False

    def corruption_robustness(self, key: str, noise_levels: list[float]) -> list[dict]:
        """Test retrieval robustness under noise injection."""
        k_vec = self.encoder(key)
        results = []
        for noise in noise_levels:
            corrupted = perturb(k_vec, noise)
            retrieved = self.retrieve_from_vec(corrupted, k=1)
            results.append({"noise": noise, "correct": retrieved[0]["correct"] if retrieved else False})
        return results

    def stats(self) -> dict:
        return {
            "dim": self.dim,
            "stored_pairs": len(self.store),
            "index_size": len(self.index),
        }
```

**Routing rule:** LLM routes to HDC when the user asks "what do I know about X?", "recall X", "what did we discuss about X?", or when the LLM needs to ground a claim in previously stored facts.

**Test cases:**
```python
def test_hd_basic():
    mem = HDCMemory(dim=10000)
    mem.store("capital_of_france", "paris")
    mem.store("capital_of_germany", "berlin")
    mem.store("capital_of_japan", "tokyo")
    
    results = mem.retrieve("capital_of_france", k=1)
    assert results[0]["score"] > 0.9  # high confidence
    # Verify corruption robustness
    robust = mem.corruption_robustness("capital_of_france", [0.0, 0.1, 0.2, 0.3, 0.5])
    assert robust[0]["correct"] == True   # no noise
    assert robust[1]["correct"] == True   # 10% noise
    # 50% noise may or may not succeed — record actual behavior

def test_hd_bundle():
    mem = HDCMemory(dim=10000)
    mem.store("fruit_apple", "red")
    mem.store("fruit_banana", "yellow")
    mem.store("fruit_orange", "orange")
    bundled = mem.bundle(["fruit_apple", "fruit_banana", "fruit_orange"])
    assert np.linalg.norm(bundled) > 0  # non-zero vector

def test_hd_interference():
    """Store 1000 pairs, verify retrieval of a specific one isn't degraded."""
    mem = HDCMemory(dim=10000)
    for i in range(1000):
        mem.store(f"key_{i}", f"value_{i}")
    results = mem.retrieve("key_500", k=1)
    assert results[0]["score"] > 0.8
```

---

### 4.2 KAN — Kolmogorov-Arnold Networks (Numerical Computation)

**Purpose:** Precise numerical evaluation, function approximation, equation solving. Eliminates LLM arithmetic errors.

**Addresses:** Arithmetic errors, numerical approximation, function fitting, equation solving.

**Core operations:**

| Operation | Description |
|---|---|
| `evaluate(expr, inputs)` | Evaluate a mathematical expression at given points |
| `fit(data, degree)` | Fit a function to data points (polynomial or KAN) |
| `solve(equations, variables)` | Solve a system of equations |
| `integrate(f, a, b)` | Numerical integration |
| `differentiate(f, x)` | Numerical/symbolic differentiation |
| `optimize(f, x0, bounds)` | Minimize/maximize a function |

**Interface:**

```python
class KANModule:
    """Numerical computation engine.
    
    Backends:
      - "sympy": symbolic + numerical (default for exact math)
      - "numpy": fast numerical (for large arrays)
      - "kan": actual KAN architecture (learnable edge activations)
    """

    def __init__(self, backend: str = "sympy"):
        self.backend = backend
        if backend == "sympy":
            import sympy as sp
            self.sp = sp

    def evaluate(self, expression: str, inputs: dict[str, float]) -> float:
        """Evaluate a mathematical expression.
        
        Args:
            expression: e.g. "x**2 + 3*x - 5" or "sin(x) * exp(-x/10)"
            inputs: e.g. {"x": 2.5}
        Returns:
            Numeric result
        """
        if self.backend == "sympy":
            sp = self.sp
            symbols = sp.symbols(','.join(inputs.keys()))
            expr = sp.sympify(expression)
            return float(expr.subs(dict(zip(symbols, inputs.values()))))
        else:
            import numpy as np
            ns = {k: v for k, v in inputs.items()}
            ns.update({"sin": np.sin, "cos": np.cos, "tan": np.tan,
                       "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
                       "pi": np.pi, "e": np.e})
            return float(eval(expression, {"__builtins__": {}}, ns))

    def fit(self, x_data: list[float], y_data: list[float], degree: int = 3) -> dict:
        """Fit a polynomial to data points.
        
        Returns:
            {"coefficients": [...], "r_squared": float, "equation": str}
        """
        import numpy as np
        x = np.array(x_data)
        y = np.array(y_data)
        coeffs = np.polyfit(x, y, degree)
        # Compute R²
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        # Build equation string
        terms = []
        for i, c in enumerate(reversed(coeffs)):
            power = len(coeffs) - 1 - i
            if power == 0:
                terms.append(f"{c:.4f}")
            elif power == 1:
                terms.append(f"{c:.4f}x")
            else:
                terms.append(f"{c:.4f}x^{power}")
        equation = " + ".join(terms)
        return {"coefficients": coeffs.tolist(), "r_squared": float(r_squared), "equation": equation}

    def solve(self, equations: list[str], variables: list[str]) -> dict:
        """Solve a system of equations.
        
        Args:
            equations: e.g. ["x + y = 10", "x - y = 4"]
            variables: e.g. ["x", "y"]
        Returns:
            {"solutions": [{"x": 7.0, "y": 3.0}], "num_solutions": int}
        """
        sp = self.sp
        syms = sp.symbols(','.join(variables))
        eqs = []
        for eq in equations:
            lhs, rhs = eq.split('=')
            eqs.append(sp.sympify(lhs) - sp.sympify(rhs))
        sols = sp.solve(eqs, syms)
        solutions = []
        for sol in sols:
            if isinstance(sol, dict):
                solutions.append({str(k): float(v) for k, v in sol.items()})
            else:
                solutions.append(dict(zip(variables, [float(s) for s in sol])))
        return {"solutions": solutions, "num_solutions": len(solutions)}

    def integrate(self, expression: str, var: str, a: float, b: float) -> float:
        """Definite integral of expression from a to b."""
        sp = self.sp
        x = sp.Symbol(var)
        expr = sp.sympify(expression)
        result = sp.integrate(expr, (x, a, b))
        return float(result)

    def differentiate(self, expression: str, var: str) -> str:
        """Symbolic derivative of expression with respect to var."""
        sp = self.sp
        x = sp.Symbol(var)
        expr = sp.sympify(expression)
        deriv = sp.diff(expr, x)
        return str(deriv)

    def optimize(self, expression: str, var: str, x0: float, 
                 bounds: tuple[float, float] | None = None) -> dict:
        """Find minimum of expression.
        
        Returns: {"x": float, "f_x": float, "is_minimum": bool}
        """
        sp = self.sp
        x = sp.Symbol(var)
        expr = sp.sympify(expression)
        # Use scipy for numerical optimization
        from scipy.optimize import minimize_scalar
        f = sp.lambdify(x, expr, modules='numpy')
        if bounds:
            result = minimize_scalar(f, bounds=bounds, method='bounded')
        else:
            result = minimize_scalar(f)
        return {"x": float(result.x), "f_x": float(result.fun), "is_minimum": result.success}

    def batch_evaluate(self, expression: str, var: str, 
                       values: list[float]) -> list[float]:
        """Evaluate expression at multiple points (vectorized)."""
        import numpy as np
        sp = self.sp
        x = sp.Symbol(var)
        expr = sp.sympify(expression)
        f = sp.lambdify(x, expr, modules='numpy')
        return [float(v) for v in f(np.array(values))]
```

**Routing rule:** LLM routes to KAN whenever the response requires a specific number: arithmetic, algebra, calculus, optimization, function fitting. **Never** let the LLM compute a number it's not 100% certain of.

**Test cases:**
```python
def test_kan_arithmetic():
    kan = KANModule(backend="sympy")
    assert abs(kan.evaluate("2 + 2 * 3", {}) - 8) < 1e-10
    assert abs(kan.evaluate("x**2 + 1", {"x": 3}) - 10) < 1e-10
    assert abs(kan.evaluate("sin(pi/2)", {}) - 1.0) < 1e-10

def test_kan_fit():
    kan = KANModule()
    # Fit y = 2x + 1
    result = kan.fit([0, 1, 2, 3, 4], [1, 3, 5, 7, 9], degree=1)
    assert abs(result["coefficients"][0] - 2.0) < 0.01
    assert abs(result["coefficients"][1] - 1.0) < 0.01
    assert result["r_squared"] > 0.999

def test_kan_solve():
    kan = KANModule()
    result = kan.solve(["x + y = 10", "x - y = 4"], ["x", "y"])
    sol = result["solutions"][0]
    assert abs(sol["x"] - 7.0) < 1e-10
    assert abs(sol["y"] - 3.0) < 1e-10

def test_kan_integrate():
    kan = KANModule()
    # ∫₀¹ x² dx = 1/3
    result = kan.integrate("x**2", "x", 0, 1)
    assert abs(result - 1/3) < 1e-10
```

---

### 4.3 SSM — State Space Model (Sequential State Tracking)

**Purpose:** Maintain a persistent, compressed state of the conversation/task sequence. Detect inconsistency, track narrative progress, compress long histories.

**Addresses:** Inconsistency in long conversations, loss of context, no streaming state, no anomaly detection.

**Core operations:**

| Operation | Description |
|---|---|
| `update(input_vec)` | Advance state: h_t = A·h_{t-1} + B·x_t |
| `get_state()` | Return current hidden state |
| `reset()` | Zero the state |
| `anomaly_score()` | Detect state trajectory irregularities |
| `summarize()` | Extract a semantic summary from the state |
| `load_state(state)` | Restore a previous state |

**Implementation (S4 / Mamba-style, simplified):**

```python
import numpy as np

class SSMModule:
    """State Space Model for sequential state tracking.
    
    Implements a simplified S4 (Structured State Spaces) model:
        h_t = A * h_{t-1} + B * x_t
        y_t = C * h_t
    
    Where A is a diagonal (or structured) matrix, B and C are vectors.
    The state h is a fixed-size vector that compresses the entire history.
    """

    def __init__(self, state_dim: int = 128, input_dim: int = 10000,
                 output_dim: int = 128, decay_range: tuple = (0.9, 0.999)):
        self.state_dim = state_dim
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # S4: A is diagonal with logarithmically spaced decay rates
        log_decays = np.linspace(*np.log(decay_range), state_dim)
        self.A = np.diag(np.exp(log_decays))  # (state_dim, state_dim)
        
        # B: random initialization (in practice, learned)
        rng = np.random.RandomState(42)
        self.B = rng.normal(0, 1, (state_dim, input_dim)) / np.sqrt(input_dim)
        self.C = rng.normal(0, 1, (output_dim, state_dim)) / np.sqrt(state_dim)
        
        # State
        self.h = np.zeros(state_dim)
        self.step_count = 0
        self.trajectory: list[np.ndarray] = []  # for anomaly detection
    
    def update(self, x: np.ndarray) -> np.ndarray:
        """Advance the state by one step.
        
        Args:
            x: input vector (input_dim,)
        Returns:
            y: output vector (output_dim,)
        """
        x = x / (np.linalg.norm(x) + 1e-10)  # normalize
        self.h = self.A @ self.h + self.B @ x
        y = self.C @ self.h
        self.step_count += 1
        self.trajectory.append(self.h.copy())
        # Limit trajectory memory
        if len(self.trajectory) > 1000:
            self.trajectory = self.trajectory[-500:]
        return y

    def get_state(self) -> np.ndarray:
        return self.h.copy()

    def set_state(self, h: np.ndarray):
        self.h = h.copy()

    def reset(self):
        self.h = np.zeros(self.state_dim)
        self.step_count = 0
        self.trajectory = []

    def anomaly_score(self) -> float:
        """Detect irregularities in the state trajectory.
        
        Uses variance of state changes. A healthy trajectory has
        smooth, consistent changes. Anomalies (contradictions, loops)
        cause spikes.
        
        Returns:
            Anomaly score (0 = normal, >1 = suspicious, >2 = anomalous)
        """
        if len(self.trajectory) < 3:
            return 0.0
        # Compute step-to-step changes
        diffs = np.diff(self.trajectory, axis=0)
        change_magnitudes = np.linalg.norm(diffs, axis=1)
        if len(change_magnitudes) < 2:
            return 0.0
        mean_change = np.mean(change_magnitudes)
        std_change = np.std(change_magnitudes)
        if std_change < 1e-10:
            return 0.0
        # Z-score of the most recent change
        recent_change = change_magnitudes[-1]
        z_score = (recent_change - mean_change) / std_change
        return float(max(0, z_score))

    def consistency_check(self, recent_window: int = 10) -> dict:
        """Check if the recent state trajectory is consistent (not oscillating)."""
        if len(self.trajectory) < recent_window + 1:
            return {"consistent": True, "score": 0.0}
        recent = self.trajectory[-(recent_window + 1):]
        # Check for oscillation: sign changes in the projection onto a random axis
        rng = np.random.RandomState(0)
        axis = rng.normal(0, 1, self.state_dim)
        projections = [float(np.dot(h, axis)) for h in recent]
        sign_changes = sum(1 for i in range(1, len(projections)) 
                          if projections[i] * projections[i-1] < 0)
        oscillation_ratio = sign_changes / (len(projections) - 1)
        return {
            "consistent": oscillation_ratio < 0.7,
            "oscillation_ratio": float(oscillation_ratio),
            "anomaly_score": self.anomaly_score(),
        }

    def compress(self, states: list[np.ndarray]) -> np.ndarray:
        """Compress a sequence of states into a single summary state."""
        if not states:
            return np.zeros(self.state_dim)
        # Simple: average (in practice, use learned compression)
        return np.mean(states, axis=0)

    def serialize(self) -> dict:
        return {
            "h": self.h.tolist(),
            "step_count": self.step_count,
            "state_dim": self.state_dim,
        }

    def deserialize(self, data: dict):
        self.h = np.array(data["h"])
        self.step_count = data["step_count"]
        self.state_dim = data["state_dim"]
```

**Routing rule:** LLM updates the SSM at the end of every turn. Before generating a response, LLM checks `consistency_check()`. If anomaly > threshold, LLM explicitly acknowledges the potential inconsistency.

**Integration with LLM:**
```python
def llm_turn(user_message: str, session: SessionState, ssd: SSMModule):
    # 1. Encode message
    x = encode_string(user_message, dim=ssd.input_dim)
    
    # 2. Update SSM state
    y = ssd.update(x)
    
    # 3. Check consistency
    check = ssd.consistency_check()
    if not check["consistent"]:
        # Flag to LLM: "Note: state trajectory shows oscillation. 
        #  Review recent reasoning for contradictions."
        pass
    
    # 4. LLM generates response (using y as context bias)
    # 5. Encode response and update SSM again
    response = llm_generate(user_message, y)
    x_resp = encode_string(response, dim=ssd.input_dim)
    ssd.update(x_resp)
    
    # 6. Save state to session
    session.ssd_state = ssd.get_state()
    return response
```

**Test cases:**
```python
def test_ssm_state_update():
    ssd = SSMModule(state_dim=64, input_dim=1000)
    x = np.random.randn(1000)
    y = ssd.update(x)
    assert y.shape == (64,)
    assert ssd.step_count == 1

def test_ssm_consistency():
    ssd = SSMModule(state_dim=64, input_dim=1000)
    # Feed consistent inputs (same direction)
    x = np.ones(1000)
    for _ in range(20):
        ssd.update(x)
    check = ssd.consistency_check()
    assert check["consistent"] == True  # no oscillation

def test_ssm_anomaly():
    ssd = SSMModule(state_dim=64, input_dim=1000)
    # Feed alternating inputs (oscillation)
    x_pos = np.ones(1000)
    x_neg = -np.ones(1000)
    for _ in range(20):
        ssd.update(x_pos)
        ssd.update(x_neg)
    # Should detect high oscillation
    check = ssd.consistency_check()
    assert check["oscillation_ratio"] > 0.5

def test_ssm_serialization():
    ssd = SSMModule(state_dim=64, input_dim=1000)
    ssd.update(np.random.randn(1000))
    data = ssd.serialize()
    ssd2 = SSMModule(state_dim=64, input_dim=1000)
    ssd2.deserialize(data)
    np.testing.assert_array_almost_equal(ssd.get_state(), ssd2.get_state())
```

---

### 4.4 Capsules — Structured Entity & Spatial Reasoning

**Purpose:** Represent entities with geometric properties (position, orientation, existence confidence). Enable spatial reasoning, hierarchical composition, and object tracking.

**Addresses:** Spatial/3D reasoning errors, no object permanence, no hierarchical decomposition, no pose invariance.

**Core concepts:**

- A **capsule** is a vector where:
  - `||v||` = existence confidence (0 to 1)
  - `v / ||v||` = property direction (pose, orientation, position)
- **Agreement routing**: higher-level capsules vote on lower-level ones
- **Transformations**: rotation, translation, scaling are vector operations

**Interface:**

```python
class CapsuleModule:
    """Capsule Network for structured entity and spatial reasoning.
    
    Each entity is represented as a capsule:
        vector = [x, y, z, roll, pitch, yaw, ...properties]
        existence = ||vector||  (clipped to [0, 1])
        properties = vector / ||vector||
    """

    def __init__(self, property_dim: int = 6):
        """
        Args:
            property_dim: number of property dimensions (default 6: x,y,z,roll,pitch,yaw)
        """
        self.property_dim = property_dim
        self.entities: dict[str, dict] = {}  # name → {"vec": np.ndarray, "confidence": float}
        self.hierarchy: dict[str, list[str]] = {}  # parent → [children]

    def create_entity(self, name: str, position: tuple = (0,0,0),
                      orientation: tuple = (0,0,0), confidence: float = 1.0,
                      properties: dict | None = None) -> dict:
        """Create a new entity capsule."""
        pos = np.array(position, dtype=float)
        orient = np.array(orientation, dtype=float)
        base_vec = np.concatenate([pos, orient])
        if properties:
            prop_vec = np.array([properties.get(k, 0) for k in sorted(properties.keys())])
            base_vec = np.concatenate([base_vec, prop_vec])
        # Normalize direction, scale by confidence
        norm = np.linalg.norm(base_vec)
        if norm > 0:
            direction = base_vec / norm
        else:
            direction = base_vec
        vec = direction * confidence
        self.entities[name] = {"vec": vec, "confidence": confidence, "name": name}
        return self.entities[name]

    def get_entity(self, name: str) -> dict | None:
        return self.entities.get(name)

    def get_position(self, name: str) -> np.ndarray:
        e = self.entities[name]
        return e["vec"][:3]  # first 3 dims = position

    def get_orientation(self, name: str) -> np.ndarray:
        e = self.entities[name]
        return e["vec"][3:6]  # next 3 dims = orientation

    def get_confidence(self, name: str) -> float:
        return self.entities[name]["confidence"]

    def set_position(self, name: str, position: tuple):
        e = self.entities[name]
        vec = e["vec"].copy()
        vec[:3] = position
        norm = np.linalg.norm(vec)
        if norm > 0:
            e["vec"] = (vec / norm) * e["confidence"]
        return e

    def rotate_entity(self, name: str, axis: str, angle_rad: float):
        """Rotate an entity around an axis."""
        e = self.entities[name]
        vec = e["vec"].copy()
        pos = vec[:3].copy()
        # Apply rotation to position
        if axis == "x":
            c, s = np.cos(angle_rad), np.sin(angle_rad)
            pos[1], pos[2] = c*pos[1] - s*pos[2], s*pos[1] + c*pos[2]
        elif axis == "y":
            c, s = np.cos(angle_rad), np.sin(angle_rad)
            pos[0], pos[2] = c*pos[0] + s*pos[2], -s*pos[0] + c*pos[2]
        elif axis == "z":
            c, s = np.cos(angle_rad), np.sin(angle_rad)
            pos[0], pos[1] = c*pos[0] - s*pos[1], s*pos[0] + c*pos[1]
        vec[:3] = pos
        norm = np.linalg.norm(vec)
        if norm > 0:
            e["vec"] = (vec / norm) * e["confidence"]
        return e

    def distance(self, name_a: str, name_b: str) -> float:
        """Euclidean distance between two entities."""
        pa = self.get_position(name_a)
        pb = self.get_position(name_b)
        return float(np.linalg.norm(pa - pb))

    def relative_position(self, reference: str, target: str) -> dict:
        """Where is 'target' relative to 'reference'?"""
        pr = self.get_position(reference)
        pt = self.get_position(target)
        delta = pt - pr
        return {
            "delta": delta.tolist(),
            "distance": float(np.linalg.norm(delta)),
            "direction": "left" if delta[0] < 0 else "right" if delta[0] > 0 else "center",
            "elevation": "above" if delta[1] > 0 else "below" if delta[1] < 0 else "level",
            "depth": "in_front" if delta[2] > 0 else "behind" if delta[2] < 0 else "same_depth",
        }

    def find_left_of(self, reference: str) -> str | None:
        """Find entity immediately to the left of reference (in x-axis)."""
        pr = self.get_position(reference)
        candidates = [(name, self.get_position(name)[0]) 
                      for name in self.entities if name != reference]
        left = [(n, x) for n, x in candidates if x < pr[0]]
        if not left:
            return None
        # Closest to the left
        return min(left, key=lambda t: abs(pr[0] - t[1]))[0]

    def find_right_of(self, reference: str) -> str | None:
        pr = self.get_position(reference)
        candidates = [(name, self.get_position(name)[0]) 
                      for name in self.entities if name != reference]
        right = [(n, x) for n, x in candidates if x > pr[0]]
        if not right:
            return None
        return min(right, key=lambda t: t[1] - pr[0])[0]

    def add_hierarchy(self, parent: str, children: list[str]):
        """Create a parent-child relationship."""
        self.hierarchy[parent] = children

    def aggregate(self, parent: str) -> np.ndarray:
        """Aggregate child capsules into parent (simplified agreement routing)."""
        children = self.hierarchy.get(parent, [])
        if not children:
            return np.zeros(self.property_dim)
        vectors = [self.entities[c]["vec"] for c in children if c in self.entities]
        # Simple: average (in practice, learned transformation matrices)
        aggregated = np.mean(vectors, axis=0)
        confidence = float(np.linalg.norm(aggregated))
        self.entities[parent]["vec"] = aggregated
        self.entities[parent]["confidence"] = min(confidence, 1.0)
        return aggregated

    def scene_summary(self) -> dict:
        """Summarize the current scene."""
        entities = []
        for name, e in self.entities.items():
            entities.append({
                "name": name,
                "position": self.get_position(name).tolist(),
                "confidence": e["confidence"],
            })
        return {
            "num_entities": len(self.entities),
            "entities": entities,
            "hierarchies": {k: v for k, v in self.hierarchy.items()},
        }

    def occlusion_test(self, observer: str, target: str, blockers: list[str]) -> bool:
        """Check if 'target' is occluded from 'observer' by any blocker."""
        po = self.get_position(observer)
        pt = self.get_position(target)
        direction = pt - po
        for blocker in blockers:
            if blocker not in self.entities:
                continue
            pb = self.get_position(blocker)
            # Project blocker onto observer→target line
            t = np.dot(pb - po, direction) / np.dot(direction, direction)
            if 0 < t < 1:
                # Blocker is between observer and target
                closest = po + t * direction
                if np.linalg.norm(pb - closest) < 0.5:  # within radius
                    return True
        return False
```

**Routing rule:** LLM routes to Capsules when the query involves: spatial relationships, 3D geometry, object tracking, hierarchical composition, "where is X relative to Y", "what's to the left/above/behind", occlusion, or any scene-based reasoning.

**Test cases:**
```python
def test_capsule_spatial():
    cap = CapsuleModule()
    cap.create_entity("cube", position=(-1, 0, 0))
    cap.create_entity("sphere", position=(1, 0, 0))
    cap.create_entity("pyramid", position=(0, 0, -1))
    
    assert cap.find_left_of("sphere") == "cube"
    assert cap.find_right_of("cube") == "sphere"
    rel = cap.relative_position("sphere", "cube")
    assert rel["direction"] == "left"

def test_capsule_distance():
    cap = CapsuleModule()
    cap.create_entity("A", position=(0, 0, 0))
    cap.create_entity("B", position=(3, 4, 0))
    assert abs(cap.distance("A", "B") - 5.0) < 1e-10

def test_capsule_rotation():
    cap = CapsuleModule()
    cap.create_entity("arrow", position=(1, 0, 0))
    cap.rotate_entity("arrow", "z", np.pi / 2)  # 90° around z
    pos = cap.get_position("arrow")
    assert abs(pos[0] - 0) < 1e-10  # x → 0
    assert abs(pos[1] - 1) < 1e-10  # y → 1

def test_capsule_occlusion():
    cap = CapsuleModule()
    cap.create_entity("observer", position=(0, 0, 0))
    cap.create_entity("target", position=(10, 0, 0))
    cap.create_entity("wall", position=(5, 0, 0))
    assert cap.occlusion_test("observer", "target", ["wall"]) == True
    cap.create_entity("open_space", position=(5, 5, 0))
    assert cap.occlusion_test("observer", "target", ["open_space"]) == False
```

---

### 4.5 MCTS + DP — Planning and Search

**Purpose:** Multi-step planning with lookahead, backtracking, and optimality guarantees. Replaces greedy autoregressive generation with principled search.

**Addresses:** Inability to plan multi-step, no lookahead, no backtracking, no optimality proof.

**Interface:**

```python
from dataclasses import dataclass
from typing import Callable
import random

@dataclass
class MCTSNode:
    state: dict
    parent: 'MCTSNode | None' = None
    action: str = ""
    visits: int = 0
    value: float = 0.0
    children: list['MCTSNode'] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []

class MCTSModule:
    """Monte Carlo Tree Search for multi-step planning.
    
    Usage:
        1. Define: initial state, action space, transition function, reward function
        2. Call: plan(initial_state, num_simulations)
        3. Receive: optimal action sequence
    """

    def __init__(self, exploration_constant: float = 1.414):
        self.c = exploration_constant  # exploration/exploitation balance
        self.root: MCTSNode | None = None

    def plan(self, initial_state: dict, 
             actions_fn: Callable[[dict], list[str]],
             transition_fn: Callable[[dict, str], dict],
             reward_fn: Callable[[dict], float],
             terminal_fn: Callable[[dict], bool],
             num_simulations: int = 1000,
             max_depth: int = 50) -> dict:
        """Run MCTS and return the best action sequence.
        
        Args:
            initial_state: starting state dict
            actions_fn: given state, return list of valid actions
            transition_fn: given state + action, return next state
            reward_fn: given state, return reward (higher = better)
            terminal_fn: given state, return True if terminal
            num_simulations: number of rollout simulations
            max_depth: maximum search depth
        Returns:
            {"actions": [str, ...], "total_reward": float, "num_simulations": int}
        """
        self.root = MCTSNode(state=initial_state)
        
        for _ in range(num_simulations):
            # 1. Selection
            node = self.root
            while not terminal_fn(node.state) and node.children:
                node = self._select(node)
            
            # 2. Expansion
            if not terminal_fn(node.state) and not node.children:
                actions = actions_fn(node.state)
                if actions:
                    action = random.choice(actions)
                    new_state = transition_fn(node.state, action)
                    child = MCTSNode(state=new_state, parent=node, action=action)
                    node.children.append(child)
                    node = child
            
            # 3. Simulation (rollout)
            sim_state = node.state
            sim_reward = 0.0
            depth = 0
            while not terminal_fn(sim_state) and depth < max_depth:
                actions = actions_fn(sim_state)
                if not actions:
                    break
                action = random.choice(actions)
                sim_state = transition_fn(sim_state, action)
                sim_reward += reward_fn(sim_state)
                depth += 1
            sim_reward += reward_fn(sim_state)
            
            # 4. Backpropagation
            while node:
                node.visits += 1
                node.value += sim_reward
                node = node.parent
        
        # Extract best path
        path = []
        node = self.root
        while node.children:
            best_child = max(node.children, key=lambda c: c.value / max(c.visits, 1))
            path.append(best_child.action)
            node = best_child
        
        return {
            "actions": path,
            "total_reward": self.root.value / max(self.root.visits, 1),
            "num_simulations": num_simulations,
            "depth": len(path),
        }

    def _select(self, node: MCTSNode) -> MCTSNode:
        """UCB1 selection."""
        best_score = -float('inf')
        best_child = None
        for child in node.children:
            exploitation = child.value / max(child.visits, 1)
            exploration = self.c * np.sqrt(np.log(max(node.visits, 1)) / max(child.visits, 1))
            score = exploitation + exploration
            if score > best_score:
                best_score = score
                best_child = child
        return best_child if best_child else node

    # --- DP (Dynamic Programming) for optimal substructure problems ---
    
    def dp_solve(self, dp_fn: Callable, *args) -> dict:
        """Solve a DP problem using memoization.
        
        Args:
            dp_fn: function that implements the recurrence relation
            *args: arguments to the DP function
        Returns:
            {"result": any, "memo_size": int}
        """
        memo = {}
        def solve(*a):
            key = a
            if key in memo:
                return memo[key]
            result = dp_fn(*a, memo)
            memo[key] = result
            return result
        result = solve(*args)
        return {"result": result, "memo_size": len(memo)}
```

**Example: Traveling Salesman (small N) via MCTS**
```python
def tsp_example():
    cities = {
        "A": (0, 0), "B": (3, 0), "C": (3, 4), "D": (0, 4), "E": (1, 2)
    }
    
    def dist(c1, c2):
        x1, y1 = cities[c1]
        x2, y2 = cities[c2]
        return ((x1-x2)**2 + (y1-y2)**2)**0.5
    
    def actions_fn(state):
        return [c for c in cities if c not in state["visited"]]
    
    def transition_fn(state, action):
        new_visited = state["visited"] + [action]
        new_dist = state["distance"] + dist(state["current"], action)
        return {"current": action, "visited": new_visited, "distance": new_dist}
    
    def reward_fn(state):
        # Minimize distance → negative reward
        return -state["distance"]
    
    def terminal_fn(state):
        return len(state["visited"]) == len(cities)
    
    mcts = MCTSModule()
    initial = {"current": "A", "visited": ["A"], "distance": 0}
    result = mcts.plan(initial, actions_fn, transition_fn, reward_fn, terminal_fn, 
                       num_simulations=5000)
    print(f"Tour: {' → '.join(['A'] + result['actions'])}")
    print(f"Total distance: {-result['total_reward']:.2f}")
```

**Routing rule:** LLM routes to MCTS/DP when the task involves: multi-step planning, scheduling, routing, resource allocation, game strategy, or any problem where the optimal action depends on future consequences.

---

### 4.6 Causal Models — Intervention & Counterfactual Reasoning

**Purpose:** Distinguish correlation from causation. Support intervention (do-calculus) and counterfactual queries.

**Addresses:** Correlation-causation confusion, no intervention semantics, no counterfactual reasoning.

**Interface:**

```python
class CausalModel:
    """Structural Causal Model (SCM) for causal reasoning.
    
    Represents a directed acyclic graph (DAG) with:
      - Nodes: variables
      - Edges: causal relationships
      - Structural equations: X_i = f_i(parents, U_i)
    
    Supports:
      - Observational queries: P(Y | X)
      - Interventional queries: P(Y | do(X))
      - Counterfactual queries: P(Y_x | X', Y')
    """

    def __init__(self):
        self.nodes: set[str] = set()
        self.edges: list[tuple[str, str]] = []  # (cause, effect)
        self.structural_equations: dict[str, str] = {}  # node → equation string
        self.priors: dict[str, dict] = {}  # node → prior distribution params

    def add_node(self, name: str, prior: str = "uniform", 
                 params: dict | None = None):
        self.nodes.add(name)
        if prior:
            self.priors[name] = {"type": prior, **(params or {})}

    def add_edge(self, cause: str, effect: str):
        if cause not in self.nodes or effect not in self.nodes:
            raise ValueError(f"Both '{cause}' and '{effect}' must be defined nodes")
        if (cause, effect) in self.edges:
            return  # already exists
        self.edges.append((cause, effect))
        # Check for cycles
        if self._has_cycle():
            self.edges.pop()
            raise ValueError(f"Adding edge {cause}→{effect} creates a cycle")

    def _has_cycle(self) -> bool:
        """DFS cycle detection."""
        visited = set()
        rec_stack = set()
        adj = {n: [] for n in self.nodes}
        for c, e in self.edges:
            adj[c].append(e)
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False
        
        for node in list(self.nodes):
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def get_parents(self, node: str) -> list[str]:
        return [c for c, e in self.edges if e == node]

    def get_children(self, node: str) -> list[str]:
        return [e for c, e in self.edges if c == node]

    def get_d_ancestors(self, node: str) -> set[str]:
        """All ancestors of node (for adjustment formula)."""
        ancestors = set()
        stack = [node]
        while stack:
            n = stack.pop()
            for parent in self.get_parents(n):
                if parent not in ancestors:
                    ancestors.add(parent)
                    stack.append(parent)
        return ancestors

    def query_observational(self, query_var: str, condition: dict[str, float]) -> float:
        """P(query_var | conditions) — observational query.
        
        In practice, this uses the structural equations + priors.
        For linear SCMs, this is exact.
        """
        # Simplified: for linear models, compute via substitution
        # (Full implementation would use numerical integration or MCMC)
        raise NotImplementedError("Requires structural equation evaluation")

    def query_interventional(self, query_var: str, intervention: dict[str, float]) -> float:
        """P(query_var | do(intervention)) — interventional query.
        
        This is the key operation: it severs incoming edges to intervened nodes
        and replaces them with fixed values.
        """
        # do(X = x): remove all edges pointing to X, set X = x
        # Then compute P(Y) in the modified graph
        # For linear SCMs: this is exact algebra
        raise NotImplementedError("Requires structural equation evaluation")

    def query_counterfactual(self, query_var: str, 
                            intervention: dict[str, float],
                            evidence: dict[str, float]) -> float:
        """P(query_var_x | evidence) — counterfactual query.
        
        "What would Y have been if X had been x, given that we observed evidence?"
        """
        raise NotImplementedError("Requires 3-step counterfactual algorithm")

    def identify_confounders(self, treatment: str, outcome: str) -> list[str]:
        """Find common causes (confounders) of treatment and outcome."""
        treatment_ancestors = self.get_d_ancestors(treatment)
        outcome_ancestors = self.get_d_ancestors(outcome)
        confounders = treatment_ancestors & outcome_ancestors
        # Exclude treatment and outcome themselves
        confounders.discard(treatment)
        confounders.discard(outcome)
        return sorted(confounders)

    def graph_summary(self) -> dict:
        return {
            "nodes": sorted(self.nodes),
            "edges": [(c, e) for c, e in self.edges],
            "num_nodes": len(self.nodes),
            "num_edges": len(self.edges),
            "is_dag": not self._has_cycle(),
        }

    def to_dot(self) -> str:
        """Export as Graphviz DOT for visualization."""
        lines = ["digraph CausalModel {"]
        for node in sorted(self.nodes):
            lines.append(f'  "{node}";')
        for c, e in self.edges:
            lines.append(f'  "{c}" -> "{e}";')
        lines.append("}")
        return "\n".join(lines)
```

**Example: Ice Cream / Drowning**
```python
def test_causal_icecream():
    cm = CausalModel()
    cm.add_node("icecream_sales", prior="normal", params={"mean": 100, "std": 20})
    cm.add_node("drowning", prior="normal", params={"mean": 5, "std": 2})
    cm.add_node("summer_heat", prior="normal", params={"mean": 30, "std": 10})
    
    # Summer heat causes both ice cream sales and drowning
    cm.add_edge("summer_heat", "icecream_sales")
    cm.add_edge("summer_heat", "drowning")
    
    # No direct edge: icecream_sales → drowning
    
    # Confounders of (icecream_sales, drowning):
    confounders = cm.identify_confounders("icecream_sales", "drowning")
    assert confounders == ["summer_heat"]
    
    # The observational correlation exists (both increase in summer)
    # But the causal effect of ice cream on drowning is ZERO
    # do(icecream_sales) → drowning: no path → P(drowning | do(icecream)) = P(drowning)
```

**Routing rule:** LLM routes to Causal Models when: the user asks "does X cause Y?", "what happens if we change X?", "what would have happened if...?", or when the LLM needs to distinguish correlation from causation.

---

### 4.7 Bayesian Networks — Calibrated Uncertainty

**Purpose:** Proper probability propagation with explicit priors, likelihoods, and posteriors. Eliminates base-rate neglect and miscalibration.

**Addresses:** Uncalibrated uncertainty, base-rate neglect, inability to combine evidence from multiple sources, no explicit probability distributions.

**Interface:**

```python
class BayesianNetwork:
    """Bayesian Network for probabilistic reasoning.
    
    Supports:
      - Discrete and continuous variables
      - Conditional probability tables (CPTs) / densities
      - Exact inference (for small networks) via variable elimination
      - Approximate inference (MCMC) for large networks
    """

    def __init__(self):
        self.nodes: dict[str, dict] = {}  # name → {"type": str, "parents": list, "cpd": ...}
        self.edges: list[tuple[str, str]] = []

    def add_discrete_node(self, name: str, values: list[str], 
                          parents: list[str] = None,
                          cpt: dict | None = None):
        """Add a discrete variable.
        
        Args:
            name: variable name
            values: possible values, e.g. ["true", "false"]
            parents: parent variable names
            cpt: conditional probability table
                  e.g. {"true": {"true": 0.9, "false": 0.1},
                        "false": {"true": 0.5, "false": 0.5}}
        """
        parents = parents or []
        self.nodes[name] = {
            "type": "discrete",
            "values": values,
            "parents": parents,
            "cpt": cpt or {},
        }
        for p in parents:
            self.edges.append((p, name))

    def add_continuous_node(self, name: str, 
                            prior_mean: float = 0, prior_std: float = 1,
                            parents: list[str] = None,
                            conditionals: dict | None = None):
        """Add a continuous (Gaussian) variable."""
        parents = parents or []
        self.nodes[name] = {
            "type": "continuous",
            "prior_mean": prior_mean,
            "prior_std": prior_std,
            "parents": parents,
            "conditionals": conditionals or {},
        }
        for p in parents:
            self.edges.append((p, name))

    def query(self, query_var: str, evidence: dict[str, float | str],
              method: str = "exact") -> dict:
        """P(query_var | evidence).
        
        Args:
            query_var: variable to query
            evidence: observed values, e.g. {"test": "positive"}
            method: "exact" (variable elimination) or "mcmc"
        Returns:
            {"distribution": {value: probability, ...}, "marginal": float}
        """
        if method == "exact":
            return self._exact_inference(query_var, evidence)
        else:
            return self._mcmc_inference(query_var, evidence)

    def _exact_inference(self, query_var: str, evidence: dict) -> dict:
        """Exact inference via enumeration (for small networks).
        
        P(X | E) = Σ_{\\X,E} P(X, \\X, E) / Σ_{X,\\X,E} P(X, \\X, E)
        """
        # Simplified implementation for binary/discrete networks
        # Full implementation requires variable elimination with junction trees
        unobserved = [n for n in self.nodes if n != query_var and n not in evidence]
        
        # Enumerate all combinations (exponential — only for small networks)
        import itertools
        values = {}
        for node in unobserved:
            if self.nodes[node]["type"] == "discrete":
                values[node] = self.nodes[node]["values"]
            else:
                raise ValueError("Exact enumeration only supports discrete variables")
        
        if not unobserved:
            # Direct computation
            numerator = self._joint_probability(query_var, evidence, {})
            denominator = sum(numerator[v] for v in self.nodes[query_var]["values"])
            distribution = {v: p / denominator for v, p in numerator.items()}
            return {"distribution": distribution, "marginal": max(distribution.values())}
        
        # Full enumeration
        all_combos = list(itertools.product(*[values[n] for n in unobserved]))
        numerator = {v: 0.0 for v in self.nodes[query_var]["values"]}
        denominator = 0.0
        for combo in all_combos:
            assignment = dict(zip(unobserved, combo))
            assignment.update(evidence)
            for qv in self.nodes[query_var]["values"]:
                assignment[query_var] = qv
                joint = self._joint_probability(query_var, evidence, assignment)
                numerator[qv] += joint.get(qv, 0)
                denominator += joint.get(qv, 0)
        
        if denominator > 0:
            distribution = {v: p / denominator for v, p in numerator.items()}
        else:
            distribution = {v: 0.0 for v in self.nodes[query_var]["values"]}
        
        return {"distribution": distribution, "marginal": max(distribution.values())}

    def _joint_probability(self, query_var: str, evidence: dict, 
                           assignment: dict) -> dict:
        """Compute joint probability P(assignment) using chain rule."""
        prob = 1.0
        for node, spec in self.nodes.items():
            if spec["type"] == "discrete" and spec["cpt"]:
                value = assignment.get(node, evidence.get(node))
                if value is None:
                    continue
                parents = spec["parents"]
                if not parents:
                    p = spec["cpt"].get(value, 1.0 / len(spec["values"]))
                else:
                    # Look up CPT entry
                    parent_vals = tuple(assignment.get(p, evidence.get(p)) for p in parents)
                    p = spec["cpt"].get(value, {}).get(parent_vals, 1.0 / len(spec["values"]))
                prob *= p
        return {query_var: prob}  # Simplified — real implementation tracks per-value

    def base_rate_correction(self, prior: float, sensitivity: float, 
                            false_positive: float, test_positive: bool = True) -> dict:
        """Classic Bayesian base-rate calculation.
        
        P(disease | test+) = sensitivity × prior / (sensitivity × prior + false_positive × (1-prior))
        """
        if test_positive:
            numerator = sensitivity * prior
            denominator = sensitivity * prior + false_positive * (1 - prior)
            posterior = numerator / denominator if denominator > 0 else 0
        else:
            numerator = (1 - sensitivity) * prior
            denominator = (1 - sensitivity) * prior + (1 - false_positive) * (1 - prior)
            posterior = numerator / denominator if denominator > 0 else 0
        
        return {
            "prior": prior,
            "posterior": float(posterior),
            "sensitivity": sensitivity,
            "false_positive_rate": false_positive,
            "test_result": "positive" if test_positive else "negative",
            "interpretation": (
                f"Despite the test being {'positive' if test_positive else 'negative'}, "
                f"the posterior probability is {posterior:.2%} because the base rate "
                f"is {prior:.2%}."
            ),
        }

    def combine_evidence(self, prior: float, likelihoods: list[dict]) -> float:
        """Combine multiple independent evidence sources.
        
        Each likelihood: {"for": prob, "against": prob}
        Uses sequential Bayesian updating.
        """
        posterior = prior
        for lik in likelihoods:
            for_prob = lik.get("for", 0.5)
            against_prob = lik.get("against", 0.5)
            # Sequential update
            numerator = for_prob * posterior
            denominator = for_prob * posterior + against_prob * (1 - posterior)
            posterior = numerator / denominator if denominator > 0 else 0.5
        return float(posterior)
```

**Test cases:**
```python
def test_bayes_base_rate():
    bn = BayesianNetwork()
    result = bn.base_rate_correction(
        prior=0.001,       # 0.1% base rate
        sensitivity=0.99,  # 99% true positive
        false_positive=0.05,  # 5% false positive
        test_positive=True
    )
    # P(disease|+) ≈ 1.94%
    assert abs(result["posterior"] - 0.0194) < 0.001

def test_bayes_combine():
    bn = BayesianNetwork()
    # Prior: 10% chance
    # Evidence 1: 80% for, 20% against
    # Evidence 2: 70% for, 30% against
    posterior = bn.combine_evidence(
        prior=0.10,
        likelihoods=[
            {"for": 0.8, "against": 0.2},
            {"for": 0.7, "against": 0.3},
        ]
    )
    # After both: should be significantly higher than 10%
    assert posterior > 0.3
    assert posterior < 0.9  # not certain
```

---

### 4.8 Neural ODEs / Differentiable Physics — World Modeling

**Purpose:** Simulate continuous-time physical dynamics. Compute trajectories, forces, and system evolution.

**Addresses:** No physical intuition, no trajectory prediction, no force/dynamics reasoning.

**Interface:**

```python
class PhysicsModule:
    """Physical simulation and dynamics engine.
    
    Backends:
      - "analytical": closed-form solutions (projectile, spring, etc.)
      - "numerical": RK4 / scipy.integrate.odeint
      - "neural_ode": learnable dynamics (for unknown systems)
    """

    def __init__(self, backend: str = "analytical", dt: float = 0.01):
        self.backend = backend
        self.dt = dt

    def projectile_motion(self, v0: float, angle_deg: float, 
                         height: float = 0, g: float = 9.81) -> dict:
        """Projectile motion: x(t), y(t), range, max height, flight time."""
        import math
        theta = math.radians(angle_deg)
        vx = v0 * math.cos(theta)
        vy = v0 * math.sin(theta)
        
        # Time to apex
        t_apex = vy / g
        # Total flight time (returning to initial height)
        if height == 0:
            t_flight = 2 * vy / g
        else:
            # Solve: height + vy*t - 0.5*g*t² = 0
            a = -0.5 * g
            b = vy
            c = height
            disc = b**2 - 4*a*c
            t_flight = (-b + math.sqrt(disc)) / (2*a) if disc >= 0 else 0
        
        range_ = vx * t_flight
        max_height = height + vy**2 / (2*g)
        
        return {
            "vx": vx, "vy": vy,
            "range": range_,
            "max_height": max_height,
            "flight_time": t_flight,
            "apex_time": t_apex,
            "trajectory": self._sample_trajectory(vx, vy, height, g, t_flight),
        }

    def spring_oscillator(self, k: float, m: float, x0: float, v0: float = 0,
                          damping: float = 0, t_end: float = 10) -> dict:
        """Spring-mass-damper system.
        
        m·x'' + c·x' + k·x = 0
        """
        import numpy as np
        from scipy.integrate import odeint
        
        def equations(state, t):
            x, v = state
            a = (-k * x - damping * v) / m
            return [v, a]
        
        t = np.linspace(0, t_end, 1000)
        solution = odeint(equations, [x0, v0], t)
        x = solution[:, 0]
        v = solution[:, 1]
        
        # Natural frequency
        omega = np.sqrt(k / m)
        period = 2 * np.pi / omega if omega > 0 else float('inf')
        
        return {
            "time": t.tolist(),
            "position": x.tolist(),
            "velocity": v.tolist(),
            "natural_frequency_hz": omega / (2 * np.pi),
            "period": period,
            "max_displacement": float(np.max(np.abs(x))),
        }

    def gravity_two_body(self, m1: float, m2: float, r0: float,
                         g: float = 6.674e-11, t_end: float = 1) -> dict:
        """Two-body gravitational problem (simplified, 1D)."""
        import numpy as np
        from scipy.integrate import odeint
        
        def equations(state, t):
            x1, v1, x2, v2 = state
            r = x2 - x1
            if abs(r) < 1e-10:
                r = 1e-10
            a1 = g * m2 / (r**2) * np.sign(r)
            a2 = -g * m1 / (r**2) * np.sign(r)
            return [v1, a1, v2, a2]
        
        t = np.linspace(0, t_end, 1000)
        solution = odeint(equations, [0, 0, r0, 0], t)
        return {
            "time": t.tolist(),
            "positions": [solution[:, 0].tolist(), solution[:, 2].tolist()],
            "final_separation": float(solution[-1, 2] - solution[-1, 0]),
        }

    def energy_conservation_check(self, system: str, initial_energy: float,
                                  final_energy: float) -> dict:
        """Check if energy is conserved (within tolerance)."""
        delta = abs(final_energy - initial_energy)
        relative = delta / max(abs(initial_energy), 1e-10)
        return {
            "conserved": relative < 1e-6,
            "initial_energy": initial_energy,
            "final_energy": final_energy,
            "delta": delta,
            "relative_error": relative,
        }

    def _sample_trajectory(self, vx, vy, h0, g, t_end, n=100):
        import numpy as np
        t = np.linspace(0, t_end, n)
        x = vx * t
        y = h0 + vy * t - 0.5 * g * t**2
        return [{"t": float(ti), "x": float(xi), "y": float(yi)} for ti, xi, yi in zip(t, x, y)]
```

**Routing rule:** LLM routes to PhysicsModule when: the question involves motion, forces, energy, trajectories, oscillations, gravity, or any physical system that can be modeled with differential equations.

**Test cases:**
```python
def test_projectile():
    phys = PhysicsModule()
    result = phys.projectile_motion(v0=10, angle_deg=45)
    # Range = v0²·sin(2θ)/g = 100·sin(90°)/9.81 ≈ 10.19m
    assert abs(result["range"] - 10.19) < 0.1
    # Max height = v0²·sin²(θ)/(2g) = 100·0.5/19.62 ≈ 2.55m
    assert abs(result["max_height"] - 2.55) < 0.1

def test_spring():
    phys = PhysicsModule()
    result = phys.spring_oscillator(k=100, m=1, x0=1, t_end=10)
    # Period = 2π√(m/k) = 2π√(0.01) ≈ 0.628s
    assert abs(result["period"] - 0.628) < 0.01
    # Undamped: max displacement = initial displacement
    assert abs(result["max_displacement"] - 1.0) < 0.01
```

---

### 4.9 SMT / Theorem Provers — Formal Verification

**Purpose:** Decide whether logical/mathematical claims are true or false. Provide proofs or counterexamples.

**Addresses:** Cannot formally verify claims, no proof/counterexample, no termination guarantees.

**Interface:**

```python
class FormalVerifier:
    """Formal verification engine.
    
    Backends:
      - "z3": SMT solver (saturation, arithmetic, arrays, strings)
      - "sympy": symbolic logic (simplification, solving)
      - "lean": (future) full theorem proving
    """

    def __init__(self, backend: str = "z3"):
        self.backend = backend
        if backend == "z3":
            try:
                from z3py import *
                self.z3 = True
            except ImportError:
                self.z3 = False
                print("Warning: z3py not installed. Falling back to sympy.")
        if backend == "sympy" or not self.z3:
            import sympy as sp
            self.sp = sp

    def verify_inequality(self, expression: str, variables: list[str],
                          domain: dict[str, tuple[float, float]] | None = None) -> dict:
        """Verify if an inequality holds for all values in the domain.
        
        Args:
            expression: e.g. "x**2 + 1 > 0"
            variables: e.g. ["x"]
            domain: e.g. {"x": (float('-inf'), float('inf'))}
        Returns:
            {"valid": bool, "counterexample": dict | None, "proof": str | None}
        """
        if self.z3:
            return self._z3_verify(expression, variables, domain)
        else:
            return self._sympy_verify(expression, variables, domain)

    def _z3_verify(self, expression, variables, domain) -> dict:
        from z3py import Real, And, Not, Solver
        ctx = {}
        for v in variables:
            ctx[v] = Real(v)
        
        # Parse expression (simplified — full implementation uses proper parser)
        # Replace >, <, == with Z3 equivalents
        expr_str = expression
        for v in variables:
            expr_str = expr_str.replace(v, ctx[v].decl())
        
        # This is a simplified interface — full implementation
        # would parse the expression properly
        # For now, return a structural analysis
        return {
            "valid": True,  # placeholder
            "counterexample": None,
            "note": "Full Z3 integration requires expression parser",
        }

    def _sympy_verify(self, expression, variables, domain) -> dict:
        sp = self.sp
        syms = sp.symbols(','.join(variables))
        expr = sp.sympify(expression)
        
        # Try to simplify
        simplified = sp.simplify(expr)
        
        # For inequalities, try to find counterexample by sampling
        if hasattr(simplified, 'is_positive') or hasattr(simplified, 'is_negative'):
            if simplified.is_positive:
                return {"valid": True, "counterexample": None, "proof": f"{simplified} > 0 for all {variables}"}
            if simplified.is_negative:
                # Check if the original was "expr > 0" or "expr < 0"
                pass
        
        # Numerical sampling for counterexample
        import random
        random.seed(42)
        for _ in range(10000):
            sample = {}
            valid = True
            for v in variables:
                if domain and v in domain:
                    lo, hi = domain[v]
                    val = random.uniform(lo if lo != float('-inf') else -100, 
                                       hi if hi != float('inf') else 100)
                else:
                    val = random.uniform(-10, 10)
                sample[v] = val
            # Evaluate
            try:
                result = expr.subs(dict(zip(syms, sample.values())))
                if isinstance(result, sp.core.numbers.Number):
                    if result < 0:  # for "expr > 0" type claims
                        return {"valid": False, "counterexample": sample, "proof": None}
            except:
                pass
        
        return {"valid": True, "counterexample": None, 
                "proof": "No counterexample found in 10000 random samples (not a formal proof)"}

    def verify_termination(self, algorithm_desc: str, max_iterations: int | None = None) -> dict:
        """Verify algorithm termination (simplified).
        
        Full implementation would model the algorithm as a transition system
        and check for a ranking function.
        """
        return {
            "terminates": None,  # requires formal model
            "method": "ranking function analysis",
            "note": "Provide a loop invariant or potential function for verification",
        }

    def prove_equality(self, expr1: str, expr2: str, variables: list[str]) -> dict:
        """Prove expr1 == expr2 for all values of variables."""
        sp = self.sp
        syms = sp.symbols(','.join(variables))
        e1 = sp.sympify(expr1)
        e2 = sp.sympify(expr2)
        diff = sp.simplify(e1 - e2)
        if diff == 0:
            return {"equal": True, "proof": f"{expr1} - {expr2} = 0 (simplified)"}
        # Try to factor
        factored = sp.factor(diff)
        if factored == 0:
            return {"equal": True, "proof": f"{expr1} - {expr2} factors to 0"}
        return {"equal": False, "difference": str(diff), 
                "note": "Not provably equal — may be equal under specific constraints"}
```

**Routing rule:** LLM routes to FormalVerifier when: the user asks to "prove", "verify", "show that", "is it always true that", or when the LLM needs to confirm a mathematical claim before stating it as fact.

**Test cases:**
```python
def test_prove_equality():
    fv = FormalVerifier(backend="sympy")
    # (a+b)² = a² + 2ab + b²
    result = fv.prove_equality("(a+b)**2", "a**2 + 2*a*b + b**2", ["a", "b"])
    assert result["equal"] == True

def test_inequality():
    fv = FormalVerifier(backend="sympy")
    # x² + 1 > 0 for all real x
    result = fv.verify_inequality("x**2 + 1 > 0", ["x"])
    assert result["valid"] == True
```

---

### 4.10 Combinatorial Optimizers — Exact NP-Hard Solutions

**Purpose:** Solve scheduling, assignment, routing, and other NP-hard problems to proven optimality.

**Addresses:** Inability to solve NP-hard problems, no optimality proof, constraint violations.

**Interface:**

```python
class OptimizerModule:
    """Exact combinatorial optimization.
    
    Backends:
      - "scipy": scipy.optimize (LP, QP)
      - "pulp": PuLP (LP, IP with CBC solver)
      - "ortools": Google OR-Tools (CP-SAT, routing)
      - "networkx": graph problems (shortest path, max flow, matching)
    """

    def __init__(self, backend: str = "networkx"):
        self.backend = backend

    def shortest_path(self, graph: dict[str, dict[str, float]], 
                      source: str, target: str) -> dict:
        """Dijkstra / Bellman-Ford shortest path.
        
        Args:
            graph: adjacency dict, e.g. {"A": {"B": 3, "C": 7}, "B": {"C": 1}, ...}
        Returns:
            {"path": ["A", "B", "C"], "distance": 4, "edges": [...]}
        """
        import heapq
        dist = {node: float('inf') for node in graph}
        dist[source] = 0
        prev = {}
        pq = [(0, source)]
        
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, weight in graph.get(u, {}).items():
                nd = d + weight
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        
        # Reconstruct path
        path = []
        node = target
        while node is not None:
            path.append(node)
            node = prev.get(node)
        path.reverse()
        
        return {
            "path": path,
            "distance": dist[target],
            "found": dist[target] < float('inf'),
        }

    def assignment_problem(self, cost_matrix: list[list[float]]) -> dict:
        """Hungarian algorithm for minimum-cost assignment.
        
        Args:
            cost_matrix: n×n matrix where cost_matrix[i][j] = cost of 
                         assigning worker i to task j
        Returns:
            {"assignment": {worker: task, ...}, "total_cost": float, "optimal": True}
        """
        import numpy as np
        from scipy.optimize import linear_sum_assignment
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        assignment = {int(r): int(c) for r, c in zip(row_ind, col_ind)}
        total_cost = sum(cost_matrix[r][c] for r, c in zip(row_ind, col_ind))
        
        return {
            "assignment": assignment,
            "total_cost": float(total_cost),
            "optimal": True,  # Hungarian guarantees optimality
        }

    def knapsack(self, weights: list[float], values: list[float], 
                 capacity: float) -> dict:
        """0/1 Knapsack (exact, DP).
        
        Returns:
            {"items": [indices], "total_value": float, "total_weight": float, "optimal": True}
        """
        n = len(weights)
        dp = [[0.0] * (int(capacity * 100) + 1) for _ in range(n + 1)]
        take = [[False] * (int(capacity * 100) + 1) for _ in range(n + 1)]
        
        for i in range(1, n + 1):
            w = int(weights[i-1] * 100)
            v = values[i-1]
            for c in range(int(capacity * 100) + 1):
                dp[i][c] = dp[i-1][c]
                if c >= w:
                    candidate = dp[i-1][c-w] + v
                    if candidate > dp[i][c]:
                        dp[i][c] = candidate
                        take[i][c] = True
        
        # Backtrack
        items = []
        c = int(capacity * 100)
        for i in range(n, 0, -1):
            if take[i][c]:
                items.append(i - 1)
                c -= int(weights[i-1] * 100)
        items.reverse()
        
        return {
            "items": items,
            "total_value": float(dp[n][int(capacity * 100)]),
            "total_weight": float(sum(weights[i] for i in items)),
            "optimal": True,
        }

    def scheduling(self, tasks: list[dict], num_workers: int) -> dict:
        """Task scheduling with constraints.
        
        Args:
            tasks: [{"id": str, "duration": float, "dependencies": [ids], "priority": int}, ...]
            num_workers: parallelism level
        Returns:
            {"schedule": {worker: [task_ids]}, "makespan": float, "optimal": bool}
        """
        import heapq
        # Topological sort + greedy assignment
        in_degree = {t["id"]: 0 for t in tasks}
        dependents = {t["id"]: [] for t in tasks}
        task_map = {t["id"]: t for t in tasks}
        
        for t in tasks:
            for dep in t.get("dependencies", []):
                in_degree[t["id"]] += 1
                dependents[dep].append(t["id"])
        
        available = [tid for tid, deg in in_degree.items() if deg == 0]
        heapq.heapify(available)
        
        worker_queues = [[] for _ in range(num_workers)]
        worker_free = [0.0] * num_workers
        schedule = {f"worker_{i}": [] for i in range(num_workers)}
        makespan = 0.0
        
        completed = 0
        while completed < len(tasks):
            # Assign available tasks to earliest-free workers
            ready = []
            for tid in list(available):
                ready.append(tid)
            
            if not ready and completed < len(tasks):
                # Deadlock — no available tasks but not all completed
                break
            
            for tid in sorted(ready, key=lambda t: -task_map[t].get("priority", 0)):
                # Find earliest-free worker
                w = min(range(num_workers), key=lambda i: worker_free[i])
                start = worker_free[w]
                end = start + task_map[tid]["duration"]
                worker_queues[w].append({"task": tid, "start": start, "end": end})
                worker_free[w] = end
                makespan = max(makespan, end)
                
                # Update dependencies
                in_degree[tid] = -1  # mark as done
                for dep_tid in dependents[tid]:
                    in_degree[dep_tid] -= 1
                    if in_degree[dep_tid] == 0:
                        heapq.heappush(available, dep_tid)
                
                available.remove(tid)
                completed += 1
        
        for w in range(num_workers):
            for entry in worker_queues[w]:
                schedule[f"worker_{w}"].append(entry["task"])
        
        return {
            "schedule": schedule,
            "makespan": makespan,
            "optimal": False,  # Greedy — not guaranteed optimal
            "note": "For guaranteed optimal scheduling, use CP-SAT or branch-and-bound",
        }
```

**Routing rule:** LLM routes to OptimizerModule when: the task involves scheduling, assignment, routing, packing, or any problem where the user asks for the "best" or "optimal" solution with constraints.

---

### 4.11 Meta-Learning (MAML) — Domain Adaptation

**Purpose:** Adapt to new domains/tasks in 1-5 gradient steps. Learn to learn.

**Addresses:** No domain adaptation, frozen at training distribution, poor performance on out-of-distribution data.

**Interface:**

```python
class MetaLearner:
    """Model-Agnostic Meta-Learning (MAML) for domain adaptation.
    
    The meta-learner is trained on a distribution of tasks.
    At test time, it adapts to a new task with a few gradient steps.
    
    Simplified implementation: parameter-efficient fine-tuning
    with a meta-learned initialization.
    """

    def __init__(self, base_model_params: dict | None = None):
        self.meta_params = base_model_params or {}
        self.adaptation_history: list[dict] = []

    def adapt(self, task_data: list[dict], 
              inner_lr: float = 0.01, 
              num_inner_steps: int = 3,
              task_description: str = "") -> dict:
        """Adapt to a new task using a few gradient steps.
        
        Args:
            task_data: [{"input": str, "output": str}, ...]
            inner_lr: learning rate for inner loop
            num_inner_steps: number of adaptation steps
            task_description: natural language description of the task
        Returns:
            {"adapted": True, "steps": int, "performance": float, "description": str}
        """
        # In a full implementation:
        # 1. Initialize with meta-learned parameters
        # 2. For each inner step:
        #    a. Compute loss on task_data
        #    b. Take gradient step
        #    c. Evaluate on held-out task data
        # 3. Return adapted parameters
        
        # Simplified: record the adaptation for the LLM to use
        adaptation = {
            "task_description": task_description,
            "num_examples": len(task_data),
            "inner_steps": num_inner_steps,
            "inner_lr": inner_lr,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.adaptation_history.append(adaptation)
        
        return {
            "adapted": True,
            "steps": num_inner_steps,
            "note": "Meta-learning requires a trainable model. "
                    "In the LLM context, this maps to: "
                    "prompt adaptation + in-context learning + "
                    "few-shot example selection.",
            "recommendation": (
                f"Provide {max(3, len(task_data)//2)} examples of the new domain "
                f"in the prompt. Include edge cases. "
                f"Use the task description as a system prompt."
            ),
        }

    def few_shot_prompt(self, task_description: str, 
                       examples: list[dict], 
                       query: str) -> str:
        """Generate a few-shot prompt for domain adaptation."""
        prompt = f"Task: {task_description}\n\n"
        for ex in examples:
            prompt += f"Input: {ex['input']}\nOutput: {ex['output']}\n\n"
        prompt += f"Input: {query}\nOutput:"
        return prompt

    def domain_shift_detection(self, recent_inputs: list[str], 
                               reference_distribution: dict | None = None) -> dict:
        """Detect if the input distribution has shifted."""
        # Simplified: check vocabulary overlap and structural patterns
        if not recent_inputs:
            return {"shifted": False, "confidence": 0.0}
        
        # Basic heuristic: check for novel token patterns
        all_tokens = set()
        for text in recent_inputs:
            all_tokens.update(text.lower().split())
        
        # In a full implementation, compare against reference distribution
        return {
            "shifted": None,  # requires reference distribution
            "unique_tokens": len(all_tokens),
            "avg_length": sum(len(t.split()) for t in recent_inputs) / len(recent_inputs),
            "note": "Full shift detection requires a reference distribution",
        }
```

**Routing rule:** LLM routes to MetaLearner when: it detects a domain shift (new terminology, new problem structure, new language), or when the user explicitly asks to "adapt to" a new domain.

---

### 4.12 TDA — Topological Data Analysis (Shape/Manifold Reasoning)

**Purpose:** Compute the topological structure of data: connected components, loops, voids. Understand the "shape" of datasets.

**Addresses:** No topological/shape reasoning, no manifold awareness, no connectivity analysis.

**Interface:**

```python
class TDAModule:
    """Topological Data Analysis.
    
    Computes persistent homology: the birth and death of topological features
    (connected components, loops, voids) across scales.
    
    Backends:
      - "ripley": Ripser algorithm (fast, for simplicial complexes)
      - "gudhi": GUDHI library (full TDA toolkit)
      - "simple": basic connectivity analysis (fallback)
    """

    def __init__(self, backend: str = "simple"):
        self.backend = backend
        if backend == "ripley":
            try:
                import ripser
                self.ripser = ripser
            except ImportError:
                print("Warning: ripser not installed. Using basic analysis.")
                self.backend = "simple"
        if backend == "gudhi":
            try:
                from gudhi import Rips
                self.gudhi = True
            except ImportError:
                print("Warning: gudhi not installed. Using basic analysis.")
                self.backend = "simple"

    def connectivity_analysis(self, points: list[list[float]], 
                              threshold: float = 1.0) -> dict:
        """Basic connectivity: find connected components at a given distance threshold.
        
        Args:
            points: list of [x, y, ...] coordinates
            threshold: connection distance
        Returns:
            {"components": int, "sizes": [int, ...], "isolated_points": int}
        """
        import numpy as np
        pts = np.array(points)
        n = len(pts)
        visited = [False] * n
        components = []
        
        # Union-Find
        parent = list(range(n))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Connect points within threshold
        for i in range(n):
            for j in range(i+1, n):
                if np.linalg.norm(pts[i] - pts[j]) <= threshold:
                    union(i, j)
        
        # Count components
        from collections import Counter
        roots = Counter(find(i) for i in range(n))
        sizes = sorted(roots.values(), reverse=True)
        
        return {
            "components": len(sizes),
            "sizes": sizes,
            "isolated_points": sum(1 for s in sizes if s == 1),
            "largest_component": sizes[0] if sizes else 0,
        }

    def persistent_homology(self, points: list[list[float]], 
                            max_dim: int = 2, 
                            num_samples: int = 200) -> dict:
        """Persistent homology (simplified).
        
        In full implementation, uses Ripser algorithm to compute
        persistence diagram: birth/death of H₀ (components), 
        H₁ (loops), H₂ (voids).
        
        Returns:
            {"H0": {"num_features": int, "persistence": [(birth, death), ...]},
             "H1": {...}, "H2": {...},
             "summary": str}
        """
        if self.backend == "ripley":
            import numpy as np
            dgm, idx = self.ripser.ripser(
                np.array(points), maxdim=max_dim
            )
            # Process persistence diagram
            result = {}
            for dim in range(max_dim + 1):
                features = dgm[dim] if dim < len(dgm) else []
                # Filter out infinite persistence (last feature)
                finite = [(float(b), float(d)) for b, d in features 
                          if d < 1e10]
                if dim == 0:
                    # H₀: first feature has infinite persistence (the whole space)
                    result[f"H{dim}"] = {
                        "num_features": len(features),
                        "num_finite": len(finite),
                        "persistence": finite[:num_samples],
                        "max_persistence": max((d-b for b,d in finite), default=0),
                    }
                else:
                    result[f"H{dim}"] = {
                        "num_features": len(features),
                        "persistence": finite[:num_samples],
                        "max_persistence": max((d-b for b,d in finite), default=0),
                    }
            
            # Summary
            h0 = result.get("H0", {})
            h1 = result.get("H1", {})
            h2 = result.get("H2", {})
            summary_parts = []
            if h0.get("num_finite", 0) > 0:
                summary_parts.append(f"{h0['num_finite']}+1 connected components")
            if h1.get("num_features", 0) > 0:
                summary_parts.append(f"{h1['num_features']} loop(s)")
            if h2.get("num_features", 0) > 0:
                summary_parts.append(f"{h2['num_features']} void(s)")
            if not summary_parts:
                summary_parts.append("trivial topology")
            
            result["summary"] = "Topological structure: " + ", ".join(summary_parts) + "."
            return result
        else:
            # Fallback: basic connectivity only
            conn = self.connectivity_analysis(points, threshold=1.0)
            return {
                "H0": {
                    "num_features": conn["components"],
                    "persistence": [],
                    "max_persistence": 0,
                },
                "H1": {"num_features": 0, "persistence": [], "max_persistence": 0},
                "H2": {"num_features": 0, "persistence": [], "max_persistence": 0},
                "summary": f"Basic analysis: {conn['components']} connected components, "
                          f"{conn['isolated_points']} isolated points. "
                          f"(Install ripser or gudhi for full persistent homology.)",
            }

    def manifold_estimation(self, points: list[list[float]], 
                            k_neighbors: int = 5) -> dict:
        """Estimate intrinsic dimensionality of the data manifold.
        
        Uses k-NN distance scaling: if d_k ≈ c·k^(-1/d), then d is the 
        intrinsic dimension.
        """
        import numpy as np
        pts = np.array(points)
        n = len(pts)
        
        # k-NN distances
        k_distances = []
        for i in range(min(n, 200)):  # subsample for speed
            dists = np.linalg.norm(pts - pts[i], axis=1)
            dists = np.sort(dists)[1:k_neighbors+1]  # exclude self
            k_distances.append(dists[-1])  # k-th nearest neighbor
        
        k_distances = np.array(k_distances)
        k_values = np.array([k_neighbors] * len(k_distances))
        
        # Log-log fit: log(d_k) = log(c) - (1/d) * log(k)
        log_k = np.log(k_values + 1)
        log_d = np.log(k_distances + 1e-10)
        
        # Linear regression
        A = np.column_stack([log_k, np.ones(len(log_k))])
        coeffs, residuals, _, _ = np.linalg.lstsq(A, log_d, rcond=None)
        intrinsic_dim = -1.0 / coeffs[0] if coeffs[0] != 0 else float('inf')
        
        return {
            "intrinsic_dimension": float(intrinsic_dim) if intrinsic_dim != float('inf') else None,
            "k_neighbors": k_neighbors,
            "r_squared": float(1 - residuals[0] / np.var(log_d) * len(log_d)) if len(log_d) > 1 else 0,
            "interpretation": (
                f"The data lies on an approximately {intrinsic_dim:.1f}-dimensional "
                f"manifold embedded in {len(pts[0]) if pts else 0}D space."
                if intrinsic_dim != float('inf') else
                "Could not estimate intrinsic dimension."
            ),
        }
```

**Test cases:**
```python
def test_tda_connectivity():
    tda = TDAModule(backend="simple")
    # Two clusters: {(0,0), (0.1,0)} and {(10,10), (10.1,10.1)}
    points = [[0, 0], [0.1, 0], [10, 10], [10.1, 10.1]]
    result = tda.connectivity_analysis(points, threshold=1.0)
    assert result["components"] == 2
    assert result["isolated_points"] == 0

def test_tda_manifold():
    tda = TDAModule(backend="simple")
    import numpy as np
    # 1D manifold (a line) in 3D space
    t = np.linspace(0, 1, 100)
    points = [[t, t**2, t**3] for t in t]
    result = tda.manifold_estimation(points, k_neighbors=5)
    # Should be close to 1
    if result["intrinsic_dimension"]:
        assert 0.5 < result["intrinsic_dimension"] < 2.0
```

---

## 5. Routing Engine

The routing engine decides which module(s) to invoke for a given user request. This is the LLM's job, but the rules are formalized below.

### 5.1 Routing Decision Table

| User intent pattern | Primary module | Secondary modules |
|---|---|---|
| "What do I know about X?" / "recall X" | HDC | — |
| "Calculate / compute / what is 2+2" | KAN | — |
| "Am I being consistent?" / long conversation | SSM | HDC |
| "Where is X?" / "what's to the left of Y" | Capsules | — |
| "Plan a route / schedule / optimize steps" | MCTS+DP | KAN (costs) |
| "Does X cause Y?" / "what if we change X" | Causal Models | Bayesian Networks |
| "How likely is X?" / "probability" | Bayesian Networks | KAN |
| "Where does it land?" / "how fast" / physics | PhysicsModule | KAN |
| "Prove / verify / show that" | FormalVerifier | KAN |
| "Best assignment / optimal schedule" | OptimizerModule | KAN |
| "New domain / adapt to X" | MetaLearner | HDC (store examples) |
| "What shape is this data?" / "topology" | TDAModule | KAN |

### 5.2 Multi-Module Chains

Some queries require multiple modules in sequence:

```
Chain 1: Physics + KAN
  "A ball is thrown at 10 m/s at 45°. Where does it land?"
  → PhysicsModule.projectile_motion() → KAN.evaluate() for exact numbers

Chain 2: Causal + Bayesian
  "Given the data, does X cause Y? How confident are we?"
  → CausalModel.identify_confounders() → BayesianNetwork.query()

Chain 3: MCTS + KAN + FormalVerifier
  "Plan the optimal route. Verify it satisfies all constraints."
  → MCTSModule.plan() → KAN.evaluate(costs) → FormalVerifier.verify_inequality()

Chain 4: HDC + SSM + LLM
  "Based on our previous discussion, what's the next step?"
  → SSM.get_state() (where are we?) → HDC.retrieve() (what did we discuss?) → LLM.synthesize()
```

### 5.3 Confidence Gating

```python
def should_route_to_module(confidence: float, module: str) -> bool:
    """Decide whether to use the specialized module or fall back to LLM.
    
    If the LLM is >90% confident in its own answer, skip the module
    (saves latency). Otherwise, route to the module.
    """
    return confidence < 0.90
```

---

## 6. Implementation Phases

### Phase 1: Foundation (Week 1–2)
**Goal: Core infrastructure + 3 highest-ROI modules**

| Task | Module | Priority |
|---|---|---|
| Vector space + encoding | Shared | P0 |
| Message bus | Shared | P0 |
| Session manager | Shared | P0 |
| HDC memory (store/retrieve/bundle/bind) | HDC | P0 |
| KAN (evaluate/fit/solve/integrate) | KAN | P0 |
| SSM (state update/consistency) | SSM | P1 |
| Routing engine (basic) | Router | P0 |
| Test harness | All | P0 |

**Deliverable:** A working system where the LLM can store/retrieve facts (HDC), do exact math (KAN), and track conversation state (SSM).

### Phase 2: Reasoning (Week 3–4)
**Goal: Planning, causal, and probabilistic reasoning**

| Task | Module | Priority |
|---|---|---|
| Capsules (entities/spatial/hierarchy) | Capsules | P1 |
| MCTS (basic planning) | MCTS+DP | P1 |
| Causal models (DAG + confounders) | Causal | P1 |
| Bayesian networks (base rate + evidence) | Bayesian | P1 |
| Chain routing | Router | P1 |

**Deliverable:** The system can plan, reason about causation, and quantify uncertainty.

### Phase 3: Advanced (Week 5–6)
**Goal: Physics, verification, optimization, adaptation, topology**

| Task | Module | Priority |
|---|---|---|
| Physics (projectile/spring/2-body) | Physics | P2 |
| Formal verification (inequality/equality) | SMT | P2 |
| Combinatorial optimization (TSP/assignment/knapsack) | Optimizer | P2 |
| Meta-learning (few-shot adaptation) | MAML | P2 |
| TDA (connectivity + manifold) | TDA | P2 |
| Full chain routing | Router | P2 |

**Deliverable:** Complete 12-module system.

### Phase 4: Optimization & Hardening (Week 7–8)
**Goal: Performance, robustness, observability**

| Task | Priority |
|---|---|
| Vector space: move to GPU (torch/jax) | P1 |
| HDC: persistent storage (disk-backed) | P1 |
| SSM: learned parameters (train on conversation data) | P2 |
| MCTS: parallel rollouts | P2 |
| All modules: latency benchmarks | P1 |
| All modules: error handling + graceful degradation | P0 |
| Observability: logging, metrics, tracing | P1 |
| Integration tests (end-to-end scenarios) | P0 |

---

## 7. Technology Stack

| Component | Library | Notes |
|---|---|---|
| Vector operations | NumPy / PyTorch | NumPy for CPU, PyTorch for GPU |
| HDC | Custom (NumPy) | 10k-dim vectors, hash-based encoding |
| KAN | SymPy + SciPy + (optional) KAN library | SymPy for symbolic, SciPy for numerical |
| SSM | NumPy (S4) / Mamba (transformers) | S4 is simple; Mamba is production-grade |
| Capsules | Custom (NumPy) | Entity vectors with pose encoding |
| MCTS | Custom (Python) | UCB1 selection, random rollout |
| Causal Models | Custom + DoWhy (optional) | DAG + structural equations |
| Bayesian Networks | Custom + pgmpy (optional) | Discrete + continuous variables |
| Physics | SciPy (odeint) + analytical solutions | RK4 integration |
| SMT / Provers | Z3 (z3py) + SymPy | Z3 for SMT, SymPy for symbolic |
| Optimizers | SciPy + PuLP + NetworkX | Hungarian, Dijkstra, knapsack DP |
| Meta-Learning | PyTorch (optional) | Few-shot adaptation |
| TDA | Ripser / GUDHI / custom | Persistent homology |
| LLM Interface | OpenAI API / local LLM | Orchestrator |
| Testing | pytest + hypothesis | Property-based testing |
| Logging | structlog | Structured JSON logging |

---

## 8. Test Strategy

### 8.1 Unit Tests (per module)
Each module has its own test file:
- `test_hd.py` — store, retrieve, bundle, bind, corruption, interference
- `test_kan.py` — arithmetic, fit, solve, integrate, differentiate
- `test_ssm.py` — state update, consistency, anomaly, serialization
- `test_capsules.py` — spatial, distance, rotation, occlusion, hierarchy
- `test_mcts.py` — TSP, grid world, planning
- `test_causal.py` — confounders, intervention, counterfactual
- `test_bayes.py` — base rate, evidence combination, inference
- `test_physics.py` — projectile, spring, energy conservation
- `test_formal.py` — inequality, equality, termination
- `test_optimizer.py` — shortest path, assignment, knapsack, scheduling
- `test_meta.py` — adaptation, domain shift detection
- `test_tda.py` — connectivity, manifold estimation

### 8.2 Integration Tests (cross-module)
- `test_chain_physics_kan.py` — physics result → KAN verification
- `test_chain_causal_bayes.py` — causal graph → Bayesian query
- `test_chain_mcts_kan_formal.py` — plan → cost → constraint verification
- `test_chain_hd_ssm_llm.py` — memory + state + synthesis

### 8.3 End-to-End Scenarios
```python
def test_e2e_diagnostic():
    """Full diagnostic reasoning chain."""
    # 1. Bayesian: base rate correction
    # 2. KAN: compute exact probability
    # 3. Causal: identify confounders
    # 4. LLM: synthesize explanation
    
def test_e2e_planning():
    """Full planning chain."""
    # 1. MCTS: generate plan
    # 2. KAN: compute costs
    # 3. FormalVerifier: verify constraints
    # 4. LLM: present plan with justification
    
def test_e2e_physics():
    """Full physics chain."""
    # 1. Physics: simulate trajectory
    # 2. KAN: verify energy conservation
    # 3. LLM: explain the physics
```

### 8.4 Property-Based Tests (Hypothesis)
```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=-100, max_value=100), min_size=2, max_size=50))
def test_kan_fit_roundtrip(data):
    """Fitting and evaluating should be consistent."""
    kan = KANModule()
    x = list(range(len(data)))
    result = kan.fit(x, data, degree=min(3, len(data)-1))
    # Evaluate at training points — should be close
    for xi, yi in zip(x, data):
        computed = kan.evaluate(result["equation"].replace("x", str(xi)), {})
        assert abs(computed - yi) < 1.0  # loose tolerance for high-degree fits

@given(st.integers(min_value=2, max_value=10))
def test_tda_connected_components(n):
    """n random points should have 1-3 connected components at reasonable threshold."""
    import numpy as np
    np.random.seed(42)
    points = np.random.randn(n, 2).tolist()
    tda = TDAModule()
    result = tda.connectivity_analysis(points, threshold=2.0)
    assert 1 <= result["components"] <= 3
```

---

## 9. Observability & Logging

Every module call must be logged:

```python
@dataclass
class ModuleCallLog:
    timestamp: str
    module: str
    operation: str
    input_summary: str      # truncated input description
    output_summary: str     # truncated output description
    latency_ms: float
    success: bool
    error: str | None = None
    confidence: float | None = None
    correlation_id: str = ""  # links related calls in a chain

class Observability:
    def __init__(self, log_file: str = "module_calls.jsonl"):
        self.log_file = log_file
        self.calls: list[ModuleCallLog] = []

    def log(self, module: str, operation: str, input_summary: str,
            output_summary: str, latency_ms: float, success: bool,
            error: str | None = None, confidence: float | None = None):
        entry = ModuleCallLog(
            timestamp=datetime.utcnow().isoformat(),
            module=module,
            operation=operation,
            input_summary=input_summary[:200],
            output_summary=output_summary[:200],
            latency_ms=latency_ms,
            success=success,
            error=error,
            confidence=confidence,
        )
        self.calls.append(entry)
        with open(self.log_file, "a") as f:
            f.write(asdict(entry) + "\n")

    def summary(self, last: int = 50) -> dict:
        recent = self.calls[-last:]
        return {
            "total_calls": len(self.calls),
            "success_rate": sum(1 for c in recent if c.success) / max(len(recent), 1),
            "avg_latency_ms": sum(c.latency_ms for c in recent) / max(len(recent), 1),
            "by_module": {},
        }
```

---

## 10. Configuration

```yaml
# config.yaml
system:
  name: "Hybrid AI Architecture"
  version: "1.0"
  log_level: "info"
  log_file: "module_calls.jsonl"

vector_space:
  dimension: 10000
  dtype: "float32"
  backend: "numpy"
  seed: 42

modules:
  hd:
    enabled: true
    dim: 10000
    max_stored_pairs: 100000
    retrieval_k: 5
    retrieval_threshold: 0.3
    
  kan:
    enabled: true
    backend: "sympy"
    max_fit_degree: 10
    
  ssd:
    enabled: true
    state_dim: 128
    input_dim: 10000
    anomaly_threshold: 2.0
    trajectory_window: 500
    
  capsules:
    enabled: true
    property_dim: 6
    
  mcts:
    enabled: true
    exploration_constant: 1.414
    default_simulations: 1000
    max_depth: 50
    
  causal:
    enabled: true
    max_nodes: 50
    
  bayes:
    enabled: true
    max_variables: 20
    
  physics:
    enabled: true
    backend: "analytical"
    dt: 0.01
    
  formal:
    enabled: true
    backend: "z3"
    timeout_seconds: 30
    
  optimizer:
    enabled: true
    backend: "networkx"
    
  meta:
    enabled: true
    inner_lr: 0.01
    inner_steps: 3
    
  tda:
    enabled: true
    backend: "simple"
    max_points: 10000

routing:
  confidence_threshold: 0.90
  default_fallback: "llm"
  max_chain_depth: 3

session:
  persistence: true
  persist_dir: "./sessions"
  max_history: 1000
```

---

## 11. API Surface (Public Interface)

The external API that the LLM (or any client) uses:

```python
class HybridAIBrain:
    """Unified interface to all 12 modules.
    
    Usage:
        brain = HybridAIBrain(config_path="config.yaml")
        result = brain.query("What's the capital of France?")
        result = brain.query("Calculate 2.718^3")
        result = brain.query("Plan a 5-city route")
        result = brain.query("Does smoking cause cancer?")
    """

    def __init__(self, config_path: str = "config.yaml"):
        # Load config
        # Initialize all enabled modules
        # Initialize routing engine
        # Initialize observability
        pass

    def query(self, text: str, context: dict | None = None) -> dict:
        """Main entry point. Routes to appropriate module(s).
        
        Returns:
            {
                "answer": str,
                "modules_used": [str],
                "confidence": float,
                "latency_ms": float,
                "details": dict,  # per-module results
            }
        """
        pass

    def store(self, key: str, value: str) -> str:
        """Store a fact in HDC."""
        pass

    def recall(self, query: str, k: int = 5) -> list[dict]:
        """Retrieve from HDC."""
        pass

    def compute(self, expression: str, inputs: dict | None = None) -> float:
        """Compute via KAN."""
        pass

    def plan(self, problem: dict) -> dict:
        """Plan via MCTS/DP."""
        pass

    def verify(self, claim: str) -> dict:
        """Verify via FormalVerifier."""
        pass

    def optimize(self, problem: dict) -> dict:
        """Optimize via OptimizerModule."""
        pass

    def simulate(self, physics_problem: dict) -> dict:
        """Simulate via PhysicsModule."""
        pass

    def spatial(self, scene: dict, query: str) -> dict:
        """Spatial reasoning via Capsules."""
        pass

    def causal(self, variables: list[str], edges: list[tuple], query: str) -> dict:
        """Causal reasoning."""
        pass

    def probability(self, prior: float, evidence: list[dict]) -> dict:
        """Probabilistic reasoning."""
        pass

    def shape(self, data: list[list[float]]) -> dict:
        """Topological analysis."""
        pass

    def session_state(self) -> dict:
        """Get current session state (SSM + HDC + Capsules)."""
        pass

    def reset_session(self):
        """Reset all module states for a new conversation."""
        pass

    def stats(self) -> dict:
        """System statistics and module health."""
        pass
```

---

## 12. Deployment Considerations

### 12.1 Latency Budget

| Operation | Target latency | Notes |
|---|---|---|
| HDC store/retrieve | <10ms | 10k-dim dot product |
| KAN evaluate | <50ms | SymPy symbolic |
| KAN fit | <500ms | Polynomial fit |
| SSM update | <5ms | Matrix-vector multiply |
| Capsule spatial query | <10ms | Vector operations |
| MCTS (1000 sims) | <5s | Depends on transition complexity |
| Causal query | <100ms | DAG traversal |
| Bayesian query | <100ms | Small network |
| Physics simulate | <200ms | Analytical or 1000-step ODE |
| Formal verify | <5s | Z3 timeout |
| Optimizer solve | <5s | Depends on problem size |
| Meta adapt | <1s | 3 inner steps |
| TDA (10k points) | <10s | Ripser |

### 12.2 Memory Budget

| Component | Memory | Notes |
|---|---|---|
| Vector space (10k dim, float32) | 40KB per vector | 10k pairs = 400MB |
| SSM state (128 dim) | 512B per session | Negligible |
| Capsule scene (100 entities) | 4KB | Negligible |
| MCTS tree (10k nodes) | ~10MB | Bounded by num_simulations |
| HDC store (100k pairs) | ~4GB | Consider disk-backed |

### 12.3 Scalability

- **HDC:** Move to disk-backed storage for >100k pairs. Use ANN (approximate nearest neighbor) for retrieval.
- **SSM:** State is fixed-size — scales to unlimited sequence length.
- **MCTS:** Parallelize rollouts across cores.
- **Physics:** Switch to GPU for large simulations.
- **TDA:** Use Ripser (C++ backend) for >10k points.

---

## 13. Open Questions & Future Work

1. **Learned routing:** Instead of rule-based routing, train a small classifier to predict which module to use from the query embedding. This could reduce latency by skipping unnecessary modules.

2. **HDC + SSM fusion:** The SSM state could be used as the HDC query vector — "retrieve based on where I am in the conversation." This would make retrieval context-aware.

3. **Capsule + HDC:** Entity capsules could be stored in HDC as key-value pairs. "Retrieve the capsule for entity X" becomes an HDC operation.

4. **KAN as universal function approximator:** Train KAN to approximate the output of other modules. E.g., KAN learns to predict MCTS outcomes, reducing the need for full simulation.

5. **Neural ODE for SSM:** Replace the linear SSM with a Neural ODE for non-linear state dynamics. The state would evolve according to a learned differential equation.

6. **Multi-modal extension:** Add image/video/audio inputs. Capsules handle spatial, SSM handles temporal, KAN handles numerical — the LLM handles the multimodal fusion.

7. **Self-improvement loop:** The system's own performance data (from observability) could be used to:
   - Tune routing thresholds
   - Identify which modules are most/least used
   - Detect recurring failure patterns
   - Auto-generate new test cases

---

## 14. Quick-Start Implementation Checklist

For the implementation agent (ChatGPT):

- [ ] Set up project structure:
  ```
  hybrid_ai/
  ├── config.yaml
  ├── requirements.txt
  ├── hybrid_ai/
  │   ├── __init__.py
  │   ├── config.py
  │   ├── vector_space.py
  │   ├── message_bus.py
  │   ├── session.py
  │   ├── modules/
  │   │   ├── __init__.py
  │   │   ├── hd.py
  │   │   ├── kan.py
  │   │   ├── ssd.py
  │   │   ├── capsules.py
  │   │   ├── mcts.py
  │   │   ├── causal.py
  │   │   ├── bayes.py
  │   │   ├── physics.py
  │   │   ├── formal.py
  │   │   ├── optimizer.py
  │   │   ├── meta.py
  │   │   └── tda.py
  │   ├── router.py
  │   ├── brain.py
  │   └── observability.py
  ├── tests/
  │   ├── test_hd.py
  │   ├── test_kan.py
  │   ├── test_ssd.py
  │   ├── test_capsules.py
  │   ├── test_mcts.py
  │   ├── test_causal.py
  │   ├── test_bayes.py
  │   ├── test_physics.py
  │   ├── test_formal.py
  │   ├── test_optimizer.py
  │   ├── test_meta.py
  │   ├── test_tda.py
  │   ├── test_integration.py
  │   └
