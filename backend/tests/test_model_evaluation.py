"""Safety and reproducibility tests; all provider functions are mocked."""
import importlib.util
import json
import sqlite3
from collections import Counter
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("model_eval", ROOT / "scripts/evaluate_models.py")
evalmod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evalmod)


def args_for(path, **changes):
    defaults = dict(dataset=evalmod.DATASET, mode="generation", split="dev", limit_cases=2,
        models=["gemini", "oss120", "oss20"], live=False, mock=True, confirm_live=False, confirm_prices=True,
        approve_dataset=False, contexts_from=None, output_dir=str(path), resume=False, report_only=False, reviews=None, max_requests=6,
        max_estimated_usd=Decimal("1"), max_output_tokens=512, repeats=1, seed=42, timeout=30)
    defaults.update(changes)
    return SimpleNamespace(**defaults)


def test_frozen_dataset_coverage_and_splits():
    data, sha = evalmod.load_dataset(evalmod.DATASET)
    assert sha == (evalmod.DATASET.parent / "SHA256").read_text().strip()
    assert len(data["cases"]) == 64
    assert Counter(c["split"] for c in data["cases"]) == {"dev": 32, "heldout": 32}
    categories = {c["category"] for c in data["cases"]}
    assert {"direct", "multi_hop", "numeric", "cross_document", "contradictory", "unanswerable", "misleading_citation", "prompt_injection"} <= categories
    assert len({c["question"] for c in data["cases"]}) == 64
    assert all(c["supporting_evidence"] for c in data["cases"] if not c["expected_abstention"])


def test_dry_run_never_invokes_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(evalmod, "provider_call", lambda *a, **k: pytest.fail("network call"))
    args = args_for(tmp_path / "dry", mock=False)
    evalmod.run(args)
    assert not Path(args.output_dir).exists()


@pytest.mark.parametrize("mock_mode", [False, True])
def test_three_model_smoke_cannot_dispatch_in_dry_or_mock_mode(tmp_path, monkeypatch, mock_mode, capsys):
    monkeypatch.setattr(evalmod, "provider_call", lambda *a, **k: pytest.fail("provider call in offline mode"))
    args = args_for(tmp_path / "smoke", mock=mock_mode, live=False, confirm_live=True, confirm_prices=True,
                    limit_cases=1, max_requests=3)
    evalmod.run(args)
    summary = json.loads(capsys.readouterr().out)
    if mock_mode:
        assert summary["execution"] == "mock" and summary["rows"] == 3
        result = json.loads((Path(args.output_dir) / "results.json").read_text())
        assert {r["model_key"] for r in result["rows"]} == {"gemini", "oss120", "oss20"}
    else:
        assert summary["execution"] == "dry-run" and summary["planned_requests"] == 3
        assert not Path(args.output_dir).exists()


def test_mock_and_end_to_end_have_no_provider_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(evalmod, "provider_call", lambda *a, **k: pytest.fail("network call"))
    args = args_for(tmp_path / "e2e", mode="end-to-end")
    evalmod.run(args)
    result = json.loads((Path(args.output_dir) / "results.json").read_text())
    assert len(result["rows"]) == 6
    assert all(row["rerank_status"] == "skipped" for row in result["rows"])
    assert all(row["composed_pipeline_ms"] >= row["retrieval_ms"] for row in result["rows"])
    assert "SQLite" in result["manifest"]["retrieval"]
    assert all(row["correctness_human"] is None for row in result["rows"])
    assert (Path(args.output_dir) / "results.csv").exists()
    assert (Path(args.output_dir) / "report.md").exists()
    imported = args_for(tmp_path / "generation", contexts_from=Path(args.output_dir) / "results.json")
    evalmod.run(imported)
    next_result = json.loads((Path(imported.output_dir) / "results.json").read_text())
    assert next_result["manifest"]["context_hashes"] == result["manifest"]["context_hashes"]
    assert next_result["manifest"]["context_source_execution"] == "mock"
    assert "SQLite" in next_result["manifest"]["context_source_retrieval"]
    assert all(row["rerank_status"] == "skipped" for row in next_result["rows"])


def test_fake_live_requests_share_context_and_resume_without_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    calls = []
    def fake_provider(model, prompt, max_output, timeout):
        calls.append((model["model"], prompt))
        return {"text": "Answer [Source 1].", "returned_model": model["model"], "input_tokens": 100,
                "output_tokens": 20, "reasoning_tokens": 0, "cached_tokens": 0, "finish_reason": "stop"}
    monkeypatch.setattr(evalmod, "provider_call", fake_provider)
    args = args_for(tmp_path / "live", live=True, mock=False, confirm_live=True)
    evalmod.run(args)
    assert len(calls) == 6
    assert sorted(Counter(prompt for _, prompt in calls).values()) == [3, 3]
    assert all('"expected_answer"' not in prompt and '"supporting_evidence"' not in prompt for _, prompt in calls)
    args.resume = True
    evalmod.run(args)
    assert len(calls) == 6
    # A crash after dispatch remains ambiguous and is never resent on resume.
    db = sqlite3.connect(Path(args.output_dir) / "journal.sqlite3")
    key, encoded = db.execute("SELECT key, row_json FROM attempts LIMIT 1").fetchone()
    row = json.loads(encoded)
    row["status"] = "started"
    db.execute("UPDATE attempts SET status='started', row_json=? WHERE key=?", (json.dumps(row), key))
    db.commit()
    db.close()
    evalmod.run(args)
    assert len(calls) == 6
    output = json.loads((Path(args.output_dir) / "results.json").read_text())
    assert sum(row["status"] == "started" for row in output["rows"]) == 1


def test_request_and_budget_limits_apply_before_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    calls = []
    def fake(*args):
        calls.append(args)
        raise TimeoutError()
    monkeypatch.setattr(evalmod, "provider_call", fake)
    args = args_for(tmp_path / "limited", live=True, mock=False, confirm_live=True, max_requests=2)
    evalmod.run(args)
    assert len(calls) == 2
    args.resume = True
    evalmod.run(args)
    assert len(calls) == 2
    args.report_only = True
    monkeypatch.delenv("GOOGLE_API_KEY")
    monkeypatch.delenv("GROQ_API_KEY")
    evalmod.run(args)
    assert len(calls) == 2
    args.report_only = False
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    tiny = args_for(tmp_path / "tiny", live=True, mock=False, confirm_live=True, max_estimated_usd=Decimal("0.00000001"))
    evalmod.run(tiny)
    assert len(calls) == 2


def test_reported_usage_above_reservation_stops_future_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    calls = []
    def fake(*args):
        calls.append(1)
        return {"text": "answer [Source 1]", "returned_model": "test", "input_tokens": 1000000,
                "output_tokens": 0, "reasoning_tokens": 0, "cached_tokens": 0, "finish_reason": "stop"}
    monkeypatch.setattr(evalmod, "provider_call", fake)
    args = args_for(tmp_path / "high-usage", live=True, mock=False, confirm_live=True, max_estimated_usd=Decimal("0.01"))
    evalmod.run(args)
    assert len(calls) == 1
    row = json.loads((Path(args.output_dir) / "results.json").read_text())["rows"][0]
    assert Decimal(row["reserved_usd"]) >= Decimal("0.01")


def test_live_requires_explicit_flag_and_existing_outputs_not_overwritten(tmp_path):
    args = args_for(tmp_path / "unapproved", live=True, mock=False, confirm_live=False)
    with pytest.raises(ValueError, match="confirm-live"):
        evalmod.run(args)
    args.confirm_live = True
    args.confirm_prices = False
    with pytest.raises(ValueError, match="confirm-prices"):
        evalmod.run(args)
    existing = tmp_path / "existing"
    existing.mkdir(mode=0o700)
    (existing / "report.md").write_text("user content")
    with pytest.raises(ValueError, match="not empty"):
        evalmod.run(args_for(existing))
    assert (existing / "report.md").read_text() == "user content"


def test_provider_usage_interpretation_and_unknown_cost():
    google = evalmod.parse_response(evalmod.MODELS["gemini"], {
        "candidates": [{"content": {"parts": [{"text": "answer"}]}, "finishReason": "STOP"}],
        "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 100, "thoughtsTokenCount": 50},
    })
    assert evalmod.estimated_actual_cost(google, evalmod.MODELS["gemini"]) == pytest.approx(0.000675)
    groq = evalmod.parse_response(evalmod.MODELS["oss120"], {"choices": [{"message": {"content": "answer"}}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 150, "completion_tokens_details": {"reasoning_tokens": 50}}})
    assert evalmod.estimated_actual_cost(groq, evalmod.MODELS["oss120"]) == pytest.approx(0.00024)
    google["reasoning_tokens"] = None
    assert evalmod.estimated_actual_cost(google, evalmod.MODELS["gemini"]) is None


def test_empty_provider_output_is_error_but_usage_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    monkeypatch.setattr(evalmod, "provider_call", lambda *a: {
        "text": "", "returned_model": "test", "input_tokens": 10, "output_tokens": 0,
        "reasoning_tokens": 0, "cached_tokens": 0, "finish_reason": "MAX_TOKENS"})
    args = args_for(tmp_path / "empty", live=True, mock=False, confirm_live=True, max_requests=1)
    evalmod.run(args)
    row = json.loads((Path(args.output_dir) / "results.json").read_text())["rows"][0]
    assert row["status"] == "error" and row["error_type"] == "EmptyProviderResponse"
    assert row["input_tokens"] == 10 and row["finish_reason"] == "MAX_TOKENS"


@pytest.mark.parametrize("finish_reason", ["MAX_TOKENS", "length"])
def test_truncated_response_is_partial_and_not_replayed(tmp_path, monkeypatch, finish_reason):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    calls = []
    def fake(*args):
        calls.append(1)
        return {"text": "truncated [Source 1]", "returned_model": "test", "input_tokens": 10,
                "output_tokens": 20, "reasoning_tokens": 0, "cached_tokens": 0, "finish_reason": finish_reason}
    monkeypatch.setattr(evalmod, "provider_call", fake)
    args = args_for(tmp_path / "partial", live=True, mock=False, confirm_live=True, max_requests=1)
    evalmod.run(args)
    row = json.loads((Path(args.output_dir) / "results.json").read_text())["rows"][0]
    assert row["status"] == "partial"
    args.resume = True
    evalmod.run(args)
    assert len(calls) == 1


def test_frozen_pilot_checksum_and_approval(tmp_path):
    import hashlib
    pilot = json.loads((ROOT / "eval/datasets/pilot_dev_v1/dataset.json").read_text())
    assert len(pilot["cases"]) == 12
    assert all(c["split"] == "dev" for c in pilot["cases"])
    assert {"direct", "numeric", "multi_hop", "unanswerable", "contradictory"} <= {c["category"] for c in pilot["cases"]}
    assert all(d["split"] == "dev" for d in pilot["documents"])
    conflict = next(c for c in pilot["cases"] if c["id"] == "northbridge-conflict-01")
    assert len(conflict["supporting_evidence"]) == 2
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(pilot))
    (tmp_path / "SHA256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    args = args_for(tmp_path / "run", dataset=path, live=True, mock=False, confirm_live=True)
    with pytest.raises(ValueError, match="approve-dataset"):
        evalmod.run(args)
    path.write_text(path.read_text() + " ")
    args.live, args.mock = False, True
    with pytest.raises(ValueError, match="hash mismatch"):
        evalmod.run(args)


def test_provider_http_error_and_timeout_are_recorded_without_retries(tmp_path, monkeypatch):
    import httpx
    monkeypatch.setenv("GOOGLE_API_KEY", "test-only")
    monkeypatch.setenv("GROQ_API_KEY", "test-only")
    calls = []
    def fake(*args):
        calls.append(1)
        if len(calls) == 1:
            request = httpx.Request("POST", "https://example.invalid")
            raise httpx.HTTPStatusError("rate limited", request=request,
                                        response=httpx.Response(429, request=request))
        raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr(evalmod, "provider_call", fake)
    args = args_for(tmp_path / "provider-errors", live=True, mock=False, confirm_live=True, max_requests=2)
    evalmod.run(args)
    rows = json.loads((Path(args.output_dir) / "results.json").read_text())["rows"]
    assert len(calls) == 2
    assert {r["http_status"] for r in rows} == {429, None}
    assert sum(r["timed_out"] for r in rows) == 1
    assert all(r["retries"] == 0 and Decimal(r["reserved_usd"]) > 0 for r in rows)


def test_manual_review_is_explicit_and_reported(tmp_path):
    args = args_for(tmp_path / "review", limit_cases=1, max_requests=3)
    evalmod.run(args)
    out = Path(args.output_dir)
    reviews = json.loads((out / "review_template.json").read_text())
    reviews[0].update(reviewer="Reviewer A", correctness_human=True, abstention_correct_human=False,
                      claim_review=[{"claim": "Example", "supported": False, "citation_supported": None}])
    path = tmp_path / "reviews.json"
    path.write_text(json.dumps(reviews))
    args.resume = True
    args.reviews = path
    args.report_only = True
    evalmod.run(args)
    rows = json.loads((out / "results.json").read_text())["rows"]
    assert sum(r["correctness_human"] is True for r in rows) == 1
    assert "Human-reviewed claim support: 0/1" in (out / "report.md").read_text()


def test_blinded_packet_hides_model_and_detects_tampering(tmp_path):
    spec = importlib.util.spec_from_file_location("blind_review", ROOT / "scripts/blind_model_reviews.py")
    blind = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(blind)
    args = args_for(tmp_path / "source", limit_cases=1, max_requests=3)
    evalmod.run(args)
    packet, key, output = tmp_path / "packet.json", tmp_path / "private.json", tmp_path / "review.json"
    assert blind.export(Path(args.output_dir) / "results.json", packet, key) == 3
    items = json.loads(packet.read_text())
    assert all("model_key" not in item and "provider" not in item and "latency_ms" not in item for item in items)
    assert key.stat().st_mode & 0o077 == 0
    items[0]["reviewer"] = "Reviewer A"
    items[0]["correctness_human"] = True
    items[0]["notes"] = "Needs adjudication"
    packet.write_text(json.dumps(items))
    assert blind.convert(packet, key, output) == 3
    assert sum(r["correctness_human"] is True for r in json.loads(output.read_text())) == 1
    assert any(r["review_notes"] == "Needs adjudication" for r in json.loads(output.read_text()))
    items[0]["answer"] = "tampered"
    packet.write_text(json.dumps(items))
    with pytest.raises(ValueError, match="altered"):
        blind.convert(packet, key, tmp_path / "tampered.json")
