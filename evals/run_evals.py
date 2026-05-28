"""
Eval runner for the Observatory agent.
Executes test cases, scores with LLM-as-judge, and pushes scores to Langfuse.

Usage:
  python -m evals.run_evals                        # Run all 30 tests
  python -m evals.run_evals --n 5                   # Run first 5 tests
  python -m evals.run_evals --category labor        # Run only labor tests
  python -m evals.run_evals --dry-run               # Show test cases without executing
  python -m evals.run_evals --no-judge              # Skip LLM-as-judge scoring
  python -m evals.run_evals --api-url http://...    # Custom API URL

Requires:
  - GROQ_API_KEY set in environment (or .env file)
  - Observatory API running (default: https://api.brainit.run/analytics)
  - Optional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST for score pushing
"""

import json
import os
import time
import argparse
import requests
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

from evals.judge import judge_response

DEFAULT_API_URL = "https://api.brainit.run/analytics"


def load_dataset():
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path) as f:
        return json.load(f)


def run_agent_query(question: str, api_url: str) -> dict:
    """Call the Observatory agent via HTTP."""
    try:
        resp = requests.post(
            f"{api_url}/agent/ask",
            json={"question": question},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"answer": None, "tools_used": [], "steps": 0, "error": str(e)}


def score_deterministic(test_case: dict, result: dict) -> dict:
    """Deterministic scoring: tool selection, string matching, crash check, step count."""
    scores = {}

    # 1. Tool selection
    expected_tool = test_case["expected_tool"]
    tools_used = result.get("tools_used", [])
    scores["tool_correct"] = expected_tool in tools_used

    # 2. Answer contains expected string
    expected_contains = test_case.get("expected_contains")
    if expected_contains:
        answer = result.get("answer", "") or ""
        scores["answer_contains"] = expected_contains.lower() in answer.lower()
    else:
        scores["answer_contains"] = None

    # 3. Agent didn't crash
    scores["no_crash"] = bool(result.get("answer"))

    # 4. Reasonable step count
    steps = result.get("steps", 0)
    scores["steps_ok"] = 0 < steps <= 10

    return scores


def push_scores_to_langfuse(trace_id: str, judge_scores: dict, deterministic_scores: dict):
    """Push evaluation scores to Langfuse for the given trace."""
    try:
        from langfuse import Langfuse
        lf = Langfuse()

        # Push judge scores (numeric 1-5)
        for name in ["factual_accuracy", "language_match", "completeness", "data_grounding"]:
            value = judge_scores.get(name)
            if value is not None:
                lf.score(
                    trace_id=trace_id,
                    name=name,
                    value=float(value),
                    comment=judge_scores.get("reasoning", ""),
                )

        # Push deterministic scores (binary 0/1)
        for name in ["tool_correct", "no_crash", "steps_ok"]:
            value = deterministic_scores.get(name)
            if value is not None:
                lf.score(
                    trace_id=trace_id,
                    name=name,
                    value=1.0 if value else 0.0,
                )

        lf.flush()
        return True

    except Exception as e:
        print(f"       ⚠ Langfuse score push failed: {e}")
        return False


def extract_trace_id(result: dict) -> str:
    """Extract Langfuse trace ID from the agent response trace_url."""
    trace_url = result.get("trace_url", "")
    if trace_url and "/trace/" in trace_url:
        return trace_url.split("/trace/")[-1]
    return None


def main():
    parser = argparse.ArgumentParser(description="Run Observatory agent evaluations")
    parser.add_argument("--n", type=int, default=None, help="Number of tests to run")
    parser.add_argument("--category", type=str, default=None, help="Filter by category")
    parser.add_argument("--difficulty", type=str, default=None, help="Filter by difficulty")
    parser.add_argument("--dry-run", action="store_true", help="Show tests without executing")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM-as-judge scoring")
    parser.add_argument("--no-langfuse", action="store_true", help="Skip Langfuse score pushing")
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL, help="Observatory API URL")
    parser.add_argument("--delay", type=int, default=5, help="Seconds between tests (rate limit)")
    args = parser.parse_args()

    dataset = load_dataset()

    # Filter
    if args.category:
        dataset = [t for t in dataset if t["category"] == args.category]
    if args.difficulty:
        dataset = [t for t in dataset if t["difficulty"] == args.difficulty]
    if args.n:
        dataset = dataset[: args.n]

    if args.dry_run:
        print(f"\n{'='*70}")
        print(f"DRY RUN — {len(dataset)} test cases")
        print(f"{'='*70}")
        for t in dataset:
            ref = "✓" if t.get("reference_answer") else "—"
            print(f"\n  [{t['id']:2d}] {t['question']}")
            print(f"       Tool: {t['expected_tool']} | Contains: {t.get('expected_contains', '—')} | {t['difficulty']} | Ref: {ref}")
        return

    print(f"\n{'='*70}")
    print(f"RUNNING {len(dataset)} EVAL TESTS")
    print(f"API: {args.api_url}")
    print(f"Judge: {'OFF' if args.no_judge else 'ON (llama-3.1-8b-instant)'}")
    print(f"Langfuse: {'OFF' if args.no_langfuse else 'ON'}")
    print(f"{'='*70}")

    results = []
    judge_totals = {"factual_accuracy": [], "language_match": [], "completeness": [], "data_grounding": []}

    for i, test in enumerate(dataset):
        print(f"\n[{test['id']:2d}/{dataset[-1]['id']}] {test['question'][:65]}...")

        # 1. Run agent query
        result = run_agent_query(test["question"], args.api_url)

        if result.get("error"):
            print(f"       ERROR: {result['error'][:80]}")
            results.append({
                "test_id": test["id"],
                "status": "ERROR",
                "deterministic_scores": {"tool_correct": False, "answer_contains": False, "no_crash": False, "steps_ok": False},
                "judge_scores": None,
                "error": result["error"][:200],
            })
            if i < len(dataset) - 1:
                time.sleep(args.delay)
            continue

        # 2. Deterministic scoring
        det_scores = score_deterministic(test, result)
        tool_mark = "✓" if det_scores["tool_correct"] else "✗"
        contains_mark = "✓" if det_scores["answer_contains"] else ("✗" if det_scores["answer_contains"] is not None else "—")

        print(f"       Tool: {tool_mark} ({', '.join(result.get('tools_used', []))}) | Contains: {contains_mark} | Steps: {result.get('steps', 0)} | {result.get('latency_ms', '?')}ms")
        print(f"       Answer: {(result.get('answer', '') or '')[:90]}...")

        # 3. LLM-as-judge scoring
        judge_scores = None
        if not args.no_judge and result.get("answer"):
            time.sleep(1)  # Small delay before judge call
            judge_scores = judge_response(
                question=test["question"],
                answer=result["answer"],
                language=test["language"],
                reference_answer=test.get("reference_answer"),
            )

            fa = judge_scores.get("factual_accuracy", "?")
            lm = judge_scores.get("language_match", "?")
            co = judge_scores.get("completeness", "?")
            dg = judge_scores.get("data_grounding", "?")
            print(f"       Judge: accuracy={fa} language={lm} completeness={co} grounding={dg}")
            print(f"       Reasoning: {judge_scores.get('reasoning', '—')[:90]}")

            # Accumulate for averages
            for key in judge_totals:
                val = judge_scores.get(key)
                if val is not None:
                    judge_totals[key].append(val)

        # 4. Push scores to Langfuse
        if not args.no_langfuse:
            trace_id = extract_trace_id(result)
            if trace_id and (det_scores or judge_scores):
                push_scores_to_langfuse(trace_id, judge_scores or {}, det_scores)

        # 5. Record result
        status = "PASS" if det_scores["tool_correct"] and det_scores["no_crash"] else "FAIL"
        results.append({
            "test_id": test["id"],
            "question": test["question"],
            "status": status,
            "deterministic_scores": det_scores,
            "judge_scores": judge_scores,
            "tools_used": result.get("tools_used", []),
            "steps": result.get("steps", 0),
            "latency_ms": result.get("latency_ms"),
            "trace_url": result.get("trace_url"),
            "answer_preview": (result.get("answer", "") or "")[:150],
        })

        # Rate limit delay
        if i < len(dataset) - 1:
            time.sleep(args.delay)

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("EVAL SUMMARY")
    print(f"{'='*70}")

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    tool_correct = sum(1 for r in results if r["deterministic_scores"].get("tool_correct"))
    contains_correct = sum(1 for r in results if r["deterministic_scores"].get("answer_contains"))
    contains_total = sum(1 for r in results if r["deterministic_scores"].get("answer_contains") is not None)

    print(f"\n  Deterministic Scores")
    print(f"  {'─'*40}")
    print(f"  Total:           {total}")
    print(f"  Passed:          {passed} ({passed / total * 100:.0f}%)")
    print(f"  Failed:          {failed}")
    print(f"  Errors:          {errors}")
    print(f"  Tool accuracy:   {tool_correct}/{total} ({tool_correct / total * 100:.0f}%)")
    if contains_total > 0:
        print(f"  Answer contains: {contains_correct}/{contains_total} ({contains_correct / contains_total * 100:.0f}%)")

    if not args.no_judge and any(judge_totals.values()):
        print(f"\n  LLM-as-Judge Scores (1-5 scale)")
        print(f"  {'─'*40}")
        for key, values in judge_totals.items():
            if values:
                avg = sum(values) / len(values)
                print(f"  {key:20s}: {avg:.1f} avg (n={len(values)})")

        # Overall quality score
        all_scores = [v for vals in judge_totals.values() for v in vals]
        if all_scores:
            overall = sum(all_scores) / len(all_scores)
            print(f"  {'─'*40}")
            print(f"  {'overall_quality':20s}: {overall:.1f} avg")

    # ── Latency stats ────────────────────────────────────────────────────
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95_idx = min(int(len(latencies_sorted) * 0.95), len(latencies_sorted) - 1)
        p95 = latencies_sorted[p95_idx]
        print(f"\n  Latency")
        print(f"  {'─'*40}")
        print(f"  p50: {p50}ms | p95: {p95}ms | max: {max(latencies)}ms")

    # ── Save results ─────────────────────────────────────────────────────
    output_path = Path(__file__).parent / "results.json"
    judge_averages = {}
    for key, values in judge_totals.items():
        if values:
            judge_averages[key] = round(sum(values) / len(values), 2)

    with open(output_path, "w") as f:
        json.dump(
            {
                "model": os.getenv("LLM_MODEL", "default"),
                "judge_model": os.getenv("JUDGE_MODEL", "llama-3.1-8b-instant"),
                "api_url": args.api_url,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                    "tool_accuracy_pct": round(tool_correct / total * 100),
                    "answer_contains_pct": round(contains_correct / contains_total * 100) if contains_total else None,
                    "judge_averages": judge_averages if judge_averages else None,
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
