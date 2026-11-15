"""Stage 2: the report. Reads files.jsonl and problems.jsonl from --data, writes bins.json there and prints
the tables."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tptp_count.report import report, tables  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="the folder stage 1 wrote to")
    args = parser.parse_args(argv)
    print(tables(report(args.data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
