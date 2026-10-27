"""Offline comparison plumbing smoke test. Never makes network calls.

Synthetic fixtures deliberately expose no evidence of real model quality.
"""
import json
import statistics
import time

FACTS = [
    ("warranty", "24 months"), ("notice", "60 days"), ("retention", "90 days"),
    ("budget", "45000 euros"), ("vacation", "25 days"), ("response time", "4 hours"),
    ("renewal", "12 months"), ("uptime", "99.9 percent"), ("deductible", "500 dollars"),
    ("delivery", "14 days"), ("refund", "30 days"), ("capacity", "200 seats"),
]


def cases():
    result = []
    for name, value in FACTS:
        context = f"[Source 1, Page 1] The {name} is {value}."
        result.append({"id": f"{name}-positive", "context": context,
                       "question": f"What is the {name}?", "expected": value, "negative": False})
        result.append({"id": f"{name}-negative", "context": context,
                       "question": "What is the CEO's birth date?", "expected": None, "negative": True})
    return result


def mock_answer(case):
    # An intentionally simplistic fake, not a provider and not a quality benchmark.
    if case["negative"]:
        return "This information is not found in the document."
    return case["context"].replace("[Source 1, Page 1] ", "") + " [Source 1]"


def main():
    rows = []
    for case in cases():
        start = time.perf_counter()
        answer = mock_answer(case)
        elapsed = (time.perf_counter() - start) * 1000
        rows.append({"case_id": case["id"], "answer": answer, "elapsed_ms": elapsed,
                     "exact_answer_proxy": None if case["negative"] else case["expected"] in answer,
                     "refusal_phrase_proxy": "not found in the document" in answer.lower() if case["negative"] else None,
                     "citation_present_proxy": "[Source 1]" in answer if not case["negative"] else None,
                     "faithfulness_manual": None, "citation_support_manual": None,
                     "input_tokens": None, "output_tokens": None, "estimated_cost_usd": None, "error": None})
    times = sorted(row["elapsed_ms"] for row in rows)
    print(json.dumps({"mode": "mock-only; no model quality or provider latency claims", "cases": len(rows),
                      "mock_p50_ms": statistics.median(times), "mock_p95_ms": times[int(0.95 * (len(times) - 1))],
                      "results": rows}, indent=2))


if __name__ == "__main__":
    main()
