import argparse
import json

from .pipeline import run


def main():
    p = argparse.ArgumentParser(description="Generate ledger, backtests and cash-planning workbook")
    p.add_argument("command", choices=["run"], nargs="?", default="run")
    p.add_argument("--as-of", default="2025-12-31")
    args = p.parse_args()
    print(json.dumps(run(args.as_of), indent=2))
