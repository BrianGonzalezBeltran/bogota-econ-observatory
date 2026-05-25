"""
Eval runner for the Observatory agent.
Executes test cases from dataset.json and scores tool selection + answer quality.

Usage:
  python -m evals.run_evals                    # Run all 30 tests
  python -m evals.run_evals --n 5              # Run first 5 tests
  python -m evals.run_evals --category labor   # Run only labor tests
  python -m evals.run_evals --dry-run          # Show test cases without executing

Requires:
  - GROQ_API_KEY set in environment
  - Observatory API running on localhost:8003
"""

import json
import sys
import os
import time
import argparse
from pathlib import Path

# Load .env if present
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

from src.agent.graph import ask


def load_dataset():
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path) as f:
        return json.load(f)


def score_result(test_case, result):
    """Score a single test case result. Returns dict with pass/fail for each criterion."""
    scores = {}

    # 1. Tool selection: did the agent use the expected tool?
    expected_tool = test_case["expected_tool"]
    tools_used = result.get("tools_used", [])
    scores["tool_correct"] = expected_tool in tools_used

    # 2. Answer contains expected string (if specified)
    expected_contains = test_case.get("expected_contains")
    if expected_contains:
        answer = result.get("answer", "")
        scores["answer_contains"] = expected_contains.lower() in answer.lower()
    else:
        scores["answer_contains"] = None  # Not evaluated

    # 3. Agent didn't crash (got an answer)
    scores["no_crash"] = bool(result.get("answer"))

    # 4. Reasonable step count (not a runaway loop)
    steps = result.get("steps", 0)
    scores["steps_ok"] = 0 < steps <= 10

    return scores


def main():
    parser = argparse.ArgumentParser(description="Run Observatory agent evaluations")
    parser.add_argument("--n", type=int, default=None, help="Number of tests to run")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument("--dry-run", action="store_true", help="Show tests without executing")
    parser.add_argument("--delay", type=int, default=3, help="Seconds between tests (rate limit)")
    args = parser.parse_args()

    dataset = load_dataset()

    # Filter
    if args.category:
        dataset = [t for t in dataset if t["category"] == args.category]
    if args.n:
        dataset = dataset[:args.n]

    if args.dry_run:
        print(f"\n{'='*70}")
        print(f"DRY RUN — {len(dataset)} test cases")
        print(f"{'='*70}")
        for t in dataset:
            print(f"\n  [{t['id']:2d}] {t['question']}")
            print(f"       Tool: {t['expected_tool']} | Contains: {t.get('expected_contains', '—')} | {t['difficulty']}")
        return

    print(f"\n{'='*70}")
    print(f"RUNNING {len(dataset)} EVAL TESTS")
    print(f"Model: {os.getenv('LLM_MODEL', 'default')}")
    print(f"{'='*70}")

    results = []
    for i, test in enumerate(dataset):
        print(f"\n[{test['id']:2d}/{dataset[-1]['id']}] {test['question'][:60]}...")

        try:
            result = ask(test["question"])
            scores = score_result(test, result)

            status = "PASS" if scores["tool_correct"] and scores["no_crash"] else "FAIL"
            tool_mark = "✓" if scores["tool_correct"] else "✗"
            contains_mark = "✓" if scores["answer_contains"] else ("✗" if scores["answer_contains"] is not None else "—")

            print(f"       Tool: {tool_mark} ({', '.join(result.get('tools_used', []))})")
            print(f"       Contains: {contains_mark} | Steps: {result.get('steps', 0)} | {status}")
            print(f"       Answer: {result.get('answer', '')[:80]}...")

            results.append({
                "test_id": test["id"],
                "status": status,
                "scores": scores,
                "tools_used": result.get("tools_used", []),
                "steps": result.get("steps", 0),
                "answer_preview": result.get("answer", "")[:100],
            })

        except Exception as e:
            print(f"       ERROR: {str(e)[:80]}")
            results.append({
                "test_id": test["id"],
                "status": "ERROR",
                "scores": {"tool_correct": False, "answer_contains": False, "no_crash": False, "steps_ok": False},
                "error": str(e)[:100],
            })

        # Rate limit delay between tests
        if i < len(dataset) - 1:
            time.sleep(args.delay)

    # Summary
    print(f"\n{'='*70}")
    print("EVAL SUMMARY")
    print(f"{'='*70}")

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    tool_correct = sum(1 for r in results if r["scores"].get("tool_correct"))
    contains_correct = sum(1 for r in results if r["scores"].get("answer_contains"))
    contains_total = sum(1 for r in results if r["scores"].get("answer_contains") is not None)

    print(f"\n  Total:           {total}")
    print(f"  Passed:          {passed} ({passed/total*100:.0f}%)")
    print(f"  Failed:          {failed}")
    print(f"  Errors:          {errors}")
    print(f"  Tool accuracy:   {tool_correct}/{total} ({tool_correct/total*100:.0f}%)")
    if contains_total > 0:
        print(f"  Answer quality:  {contains_correct}/{contains_total} ({contains_correct/contains_total*100:.0f}%)")

    # Save results
    output_path = Path(__file__).parent / "results.json"
    with open(output_path, "w") as f:
        json.dump({
            "model": os.getenv("LLM_MODEL", "default"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "tool_accuracy_pct": round(tool_correct / total * 100),
                "answer_quality_pct": round(contains_correct / contains_total * 100) if contains_total else None,
            },
            "results": results,
        }, f, indent=2)
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
