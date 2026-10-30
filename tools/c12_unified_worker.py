"""Host-pinned optional Unified Planning worker. Invoked with fixed file paths.

Requirements: offline installed unified_planning and explicitly selected local
planner plugin. This executable is NOT a security sandbox; Lu must isolate it.
"""
from __future__ import annotations
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 5:
        return 2
    domain, problem, output, engine_name = sys.argv[1:]
    # Cost-aware tasks require a compatible planner. Pyperplan drops action costs.
    if engine_name != 'fast-downward':
        return 2
    try:
        from unified_planning.io import PDDLReader
        from unified_planning.shortcuts import OneshotPlanner
        instance = PDDLReader().parse_problem(domain, problem)
        with OneshotPlanner(name=engine_name) as planner:
            solution = planner.solve(instance)
        if not solution.status.name.startswith('SOLVED_') or solution.plan is None:
            return 3
        actions = solution.plan.actions
        # Only typed, already-grounded, parameterless Cognitum PDDL supported.
        lines=[]
        for item in actions:
            if item.actual_parameters or not item.action.name.startswith('act'):
                return 4
            lines.append(f'({item.action.name})')
        Path(output).write_text('\n'.join(lines)+'\n', encoding='ascii')
        return 0
    except (ImportError, RuntimeError, OSError, ValueError, TypeError):
        return 5


if __name__ == '__main__':
    sys.exit(main())
