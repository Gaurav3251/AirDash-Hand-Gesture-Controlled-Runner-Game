"""
scripts/run_evaluation.py: prints the post-session evaluation summary
described in the proposal — accuracy proxy, false-trigger rate, latency,
FPS, and completion status, checked against MVP target thresholds.

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --session-id 3
    python scripts/run_evaluation.py --list
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.evaluation_service import evaluate_session, list_sessions  # noqa: E402


def _status(passed):
    return "PASS" if passed else "FAIL"


def print_summary(summary):
    print(f"\nSession #{summary.session_id} ({summary.input_mode} mode)")
    print("-" * 50)
    print(f"Duration:               {summary.duration_seconds:.1f}s")
    print(f"Completed:              {summary.completed}")
    print(f"Final score:            {summary.final_score}")
    print(f"Total frames logged:    {summary.total_frames}")
    print(f"Commands fired:         {summary.fired_commands}")
    print()
    print(f"Stable prediction rate: {summary.stable_prediction_rate:.1%} "
          f"[{_status(summary.meets_accuracy_target)}, target >= 85%]")
    print(f"False trigger rate:     {summary.false_trigger_rate_per_min:.2f}/min "
          f"[{_status(summary.meets_false_trigger_target)}, target < 2/min]")
    print(f"Avg latency:            {summary.avg_latency_ms:.0f}ms "
          f"[{_status(summary.meets_latency_target)}, target < 200ms]")
    print(f"Avg FPS:                {summary.avg_fps:.1f} "
          f"[{_status(summary.meets_fps_target)}, target > 20]")
    print()


def print_session_list():
    sessions = list_sessions()
    if not sessions:
        print("No sessions logged yet. Run `python main.py --input gesture` first.")
        return
    print(f"{'ID':<5}{'Mode':<12}{'Completed':<12}{'Score':<8}")
    for session_id, input_mode, start_time, completed, final_score in sessions:
        print(f"{session_id:<5}{input_mode:<12}{bool(completed)!s:<12}{final_score:<8}")


def main():
    parser = argparse.ArgumentParser(description="Print MVP evaluation summary")
    parser.add_argument("--session-id", type=int, default=None,
                         help="Evaluate a specific session (defaults to most recent).")
    parser.add_argument("--list", action="store_true", help="List all logged sessions.")
    args = parser.parse_args()

    if args.list:
        print_session_list()
        return

    try:
        summary = evaluate_session(session_id=args.session_id)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print_summary(summary)


if __name__ == "__main__":
    main()
