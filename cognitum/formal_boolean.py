"""C10 bounded Boolean CNF reference solver; NOT a general SMT engine.

Finite exhaustive checking is deliberately limited to <=12 Boolean variables.
The input is a developer-owned typed structure, not model-authored code.
No Lu tool registration, process permissions, network, or dynamic evaluation.
"""
from dataclasses import dataclass
from typing import Literal

MAX_VARIABLES = 12
MAX_CLAUSES = 64
MAX_LITERALS = 256
MAX_ASSIGNMENTS = 1 << MAX_VARIABLES


@dataclass(frozen=True)
class CNF:
    variables: int
    clauses: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Decision:
    status: Literal["SAT", "UNSAT_EXHAUSTIVE", "UNKNOWN_BUDGET"]
    assignment: tuple[bool, ...] = ()
    checked_assignments: int = 0
    assurance: str = "bounded_boolean_reference"
    limitations: tuple[str, ...] = (
        "formalization_not_verified", "not_general_smt",
        "no_independent_proof_artifact",
    )


def validate(formula: CNF) -> CNF:
    if type(formula) is not CNF:
        raise ValueError("expected typed CNF")
    if type(formula.variables) is not int or not 1 <= formula.variables <= MAX_VARIABLES:
        raise ValueError("bounded Boolean variable count required")
    if type(formula.clauses) is not tuple or len(formula.clauses) > MAX_CLAUSES:
        raise ValueError("bounded tuple of clauses required")
    total = 0
    for clause in formula.clauses:
        if type(clause) is not tuple:
            raise ValueError("clauses must be tuples")
        total += len(clause)
        if total > MAX_LITERALS:
            raise ValueError("too many literals")
        for literal in clause:
            if type(literal) is not int or literal == 0 or abs(literal) > formula.variables:
                raise ValueError("invalid signed Boolean literal")
    return formula


def evaluates_true(formula: CNF, assignment: tuple[bool, ...]) -> bool:
    validate(formula)
    if (type(assignment) is not tuple or len(assignment) != formula.variables
            or any(type(value) is not bool for value in assignment)):
        raise ValueError("complete Boolean assignment required")
    return all(any(assignment[abs(literal)-1] == (literal > 0)
                   for literal in clause) for clause in formula.clauses)


def _assignment(mask: int, variables: int) -> tuple[bool, ...]:
    return tuple(bool(mask & (1 << i)) for i in range(variables))


def solve(formula: CNF, *, assignment_budget: int = MAX_ASSIGNMENTS) -> Decision:
    validate(formula)
    if type(assignment_budget) is not int or not 1 <= assignment_budget <= MAX_ASSIGNMENTS:
        raise ValueError("bounded assignment budget required")
    full = 1 << formula.variables
    checked = min(full, assignment_budget)
    for mask in range(checked):
        candidate = _assignment(mask, formula.variables)
        if evaluates_true(formula, candidate):
            return Decision("SAT", candidate, mask+1)
    if checked != full:
        return Decision("UNKNOWN_BUDGET", checked_assignments=checked)
    return Decision("UNSAT_EXHAUSTIVE", checked_assignments=full)


def verify(formula: CNF, decision: Decision) -> bool:
    """Independent replay, not an exported proof certificate or host attestation.

    Checks every candidate for a claimed exhaustive UNSAT rather than trusting
    a count or producer receipt. SAT is accepted only when a typed witness works.
    UNKNOWN only confirms that no unsupported conclusion is being asserted.
    """
    validate(formula)
    if type(decision) is not Decision:
        return False
    if (decision.assurance != "bounded_boolean_reference"
            or decision.limitations != Decision("SAT").limitations
            or type(decision.checked_assignments) is not int):
        return False
    full = 1 << formula.variables
    if decision.status == "SAT":
        try:
            return (1 <= decision.checked_assignments <= full
                    and evaluates_true(formula, decision.assignment)
                    and decision.checked_assignments ==
                    1 + sum(int(x) << i for i, x in enumerate(decision.assignment)))
        except ValueError:
            return False
    if decision.assignment:
        return False
    if decision.status == "UNKNOWN_BUDGET":
        return 1 <= decision.checked_assignments < full
    if decision.status == "UNSAT_EXHAUSTIVE":
        if decision.checked_assignments != full:
            return False
        # Verifier independently exhausts the small finite domain.
        return not any(evaluates_true(formula, _assignment(mask, formula.variables))
                       for mask in range(full))
    return False
