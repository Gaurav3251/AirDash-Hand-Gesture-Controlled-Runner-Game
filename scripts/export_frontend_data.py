"""
Exports the latest evaluator summary to a tiny static frontend JSON file.

Usage:
    python scripts/export_frontend_data.py
    python scripts/export_frontend_data.py --session-id 3
"""
import argparse
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation_service import evaluate_session  # noqa: E402


DEFAULT_OUTPUT_PATH = os.path.join("frontend", "data", "session_summary.json")


def main():
    parser = argparse.ArgumentParser(description="Export evaluation summary for frontend")
    parser.add_argument("--session-id", type=int, default=None)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    summary = evaluate_session(session_id=args.session_id)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(asdict(summary), output_file, indent=2)
    print(f"Exported session #{summary.session_id} to {args.output}")


if __name__ == "__main__":
    main()
