"""Export canonical Protobuf Lu CE handoff (inert, unapproved proposal).

    python tools/emit_lu_ce_handoff.py > cognitum.ce_handoff.pb

Optional external-model-adapter preview:
    python tools/emit_lu_ce_handoff.py --model-boundary-json

The model boundary preview is NOT a native handoff and does not grant any
permission or advertise/install a Cognitum tool in Lu.
"""
import argparse
import json
import sys

from cognitum.lu_ce_protobuf import (
    create_lu_ce_handoff_proto,
    encode_lu_ce_handoff,
    model_boundary_function_definition,
)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-boundary-json", action="store_true",
                   help="view external LLM provider tool JSON only; never used for native handoff")
    args = p.parse_args()
    if args.model_boundary_json:
        preview = model_boundary_function_definition(create_lu_ce_handoff_proto())
        print(json.dumps(preview, sort_keys=True, indent=2))
    else:
        sys.stdout.buffer.write(encode_lu_ce_handoff())


if __name__ == "__main__":
    main()
