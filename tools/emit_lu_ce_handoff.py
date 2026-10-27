"""Emit the current *non-installable* Lu DLC Core Extension discovery proposal.

    python tools/emit_lu_ce_handoff.py

Stdout is machine-readable JSON for architecture review, NOT a Lu installation,
capability grant, native registry call or current model-facing tool list.
"""
from __future__ import annotations

import json

from cognitum.ce_manifest import ProposedToolBinding
from cognitum.lu_ce_handoff import CALCULATOR_GUIDE, create_lu_ce_handoff
from cognitum.plugins.calculator import Calculator


def main():
    binding = ProposedToolBinding(
        cognitum_operation="calc.rational",
        native_tool_id="cognitum.calc.rational",
        model_tool_name="cognitum_calc_rational",
        input_type_url="type.googleapis.com/cognitum.v1.CalculateRationalRequest",
        output_type_url="type.googleapis.com/cognitum.v1.CalculateRationalResult",
    )
    proposal = create_lu_ce_handoff(
        Calculator().manifest(), "cognitum.calc", (binding,), (CALCULATOR_GUIDE,),
    )
    print(json.dumps(proposal, ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
