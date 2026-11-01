import argparse
import json
import platform
import sys
from pathlib import Path
from .contracts import Request, HostContext
from .registry import Registry
from .runtime import Runtime
from .tracing import Trace
from .evaluation import replay
from .plugins.calculator import Calculator
from .plugins.specialists import Specialists

def main():
    parser = argparse.ArgumentParser(description="Standalone Cognitum Phase 0 harness")
    parser.add_argument("--calculator", action="store_true", help="explicitly enable trusted reference calculator")
    parser.add_argument("--enable-specialists", action="store_true", help="explicitly admit bundled research HDC/KAN/SSM specialists")
    parser.add_argument("--trace", type=Path, help="optional metadata-only JSONL file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("registry")
    commands.add_parser("specialists")
    calc = commands.add_parser("calc")
    calc.add_argument("expression")
    evaluation = commands.add_parser("replay")
    evaluation.add_argument("fixtures", type=Path)
    args = parser.parse_args()
    registry = Registry()
    if args.calculator:
        registry.install(Calculator, enabled=True)
        registry.nominate("calc", "reference_calc")
    if args.enable_specialists:
        registry.install(Specialists, enabled=True)
        for slot in ("hdc", "kan", "ssm"):
            registry.nominate(slot, "cognitum_specialists")
    runtime = Runtime(registry, Trace(args.trace))
    if args.command == "registry":
        output = registry.snapshot()
    elif args.command == "specialists":
        output = {"distribution": "cognitum-core", "separate_specialist_package": False,
                  "installed": [x.describe() for x in Specialists().manifest().operations],
                  "enabled": bool(args.enable_specialists),
                  "status": "research_specialists_not_automatically_authorized"}
    elif args.command == "calc":
        output = runtime.call(Request("cli-1", "cli", "calc.rational", {"expression": args.expression}),
                              HostContext("local", "local-user")).to_dict()
    else:
        output = replay(runtime, json.loads(args.fixtures.read_text(encoding="utf-8")))
        output["environment"] = {"python": platform.python_version(), "platform": platform.platform()}
    print(json.dumps(output, indent=2))
    if args.command == "replay":
        return int(output["passed"] != output["total"])
    if args.command == "calc":
        return int(output["execution_status"] != "completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
