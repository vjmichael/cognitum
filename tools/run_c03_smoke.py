"""C03-only synthetic evaluator. Default output is native binary Protobuf."""
import argparse
import sys

from cognitum.eval_protobuf import (
    encode_component_report, decode_component_report,
)


def main():
    parser = argparse.ArgumentParser(
        description="C03 synthetic in-process calculator check; not a Lu/model benchmark")
    parser.add_argument("--check", action="store_true",
                        help="print human-readable smoke status and exit nonzero on failure")
    args = parser.parse_args()
    wire = encode_component_report()
    verified = decode_component_report(wire)
    if args.check:
        print(f"C03 component-only synthetic cases: {verified.passed}/{verified.total}; "
              "Lu/model arms executed: false; promotion evidence: false")
    else:
        sys.stdout.buffer.write(wire)
    return 0 if verified.total and verified.passed == verified.total else 1


if __name__ == "__main__":
    sys.exit(main())
