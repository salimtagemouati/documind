# Running the model evaluation

This tool is separate from the production API. It defaults to an offline dry run; nothing below authorizes a live call. The v1 corpus is fictional. Its labels have not been independently reviewed. Live provider access, model IDs and adapters have **not** been verified. Never put keys into commands, output artifacts or repository files.

Prerequisites: use the existing backend virtual environment; check the current provider prices and model policies before approving a run. The script contains standard input/output prices from 2026-10-26: Gemini $0.30/$2.50, GPT-OSS 120B $0.15/$0.60, 20B $0.075/$0.30 per million tokens. If rates have changed, update and review the catalog in the script before the run; changed code creates a different run identity. See [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Groq model catalog](https://console.groq.com/docs/models), [Google usage fields](https://ai.google.dev/api/generate-content), and [Groq usage fields](https://console.groq.com/docs/api-reference). Confirm rate limits and data retention independently. A free tier is not guaranteed to be free for an account.

## Offline preparation

From the repository root, generate frozen retrieved contexts using the application's chunker, SQLite indexing and local lexical retrieval. This makes **no provider calls** and selects no model winner:

```bash
backend/.venv/bin/python scripts/evaluate_models.py --mock --mode end-to-end --split heldout --max-requests 96 --max-estimated-usd 1 --output-dir eval/runs/heldout-retrieval
```

The output is a **SQLite lexical diagnostic**: no embeddings, pgvector, HNSW, production DB or reranker call. `rerank_status` is `skipped`; timing is local shared retrieval, not actual end-to-end production latency. It uses synthetic page text directly, not PDF extraction. The selected contexts are recorded once per case and reused for all models. Alternatively generation mode without `--contexts-from` uses preselected curated page contexts, which are not retrieval results.

Inspect the planned generation-only comparison, still without network calls:

```bash
backend/.venv/bin/python scripts/evaluate_models.py --dry-run --mode generation --split heldout --contexts-from eval/runs/heldout-retrieval/results.json --max-requests 96 --max-estimated-usd 1
```

The dry run checks our request shapes locally. `live_verified: false` means it does not check provider account access, model availability, wire compatibility, or permissions. It reports a conservative estimated reservation, not guaranteed provider billing. Configure provider credentials privately in the process environment only after the user has approved a live run: `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) and `GROQ_API_KEY`. Never print them.

## Future live run — explicit approval required

After approval, price verification, privacy review and the offline preparation above, this exact command runs at most 96 generation requests and stops before its estimated reservations exceed $1:

```bash
backend/.venv/bin/python scripts/evaluate_models.py --live --confirm-live --confirm-prices --mode generation --split heldout --contexts-from eval/runs/heldout-retrieval/results.json --max-requests 96 --max-estimated-usd 1 --output-dir eval/runs/heldout-live
```

`--confirm-live` records the operator's confirmation of explicit user approval; it is not permission by itself. `--confirm-prices` confirms the bundled rate assumptions were checked. The request limit counts attempted provider requests including failures and ambiguous requests; no evidence requires no provider call. The estimated budget reserves `2 × UTF-8 prompt bytes + 1024` input tokens plus the maximum 512 output tokens per request at the listed rates, including failed or interrupted requests. This deliberately conservative heuristic is **not a provider-enforced spending cap**: tokenization, billing rules, reasoning, rate changes, and provider-side processing may cause actual charges to differ or exceed it. Set provider-side billing controls separately. No automatic retry or model fallback is used. A request may be billed even if it times out or returns an error.

Existing nonempty output directories are never used for a new run. A full synchronous SQLite journal records each attempt before dispatch. On `--resume`, the command must use the same options, code, dataset, model catalog, context hashes and budget; completed, failed and `started` entries are never resent. `started` means the result may have been lost after dispatch; reconcile with the provider manually. The tool will not automatically replay it. Run identity includes code and dependency versions, so changed code or datasets require a new directory. The single-process file lock prevents two benchmark processes from sharing the journal. If the request or reservation limit stops a run, the report is partial, not a complete paired comparison. Increasing a cap requires a new run and can repeat paid calls; do not do so without accounting for prior usage.

Each run produces `results.json`, `results.csv`, `report.md`, `review_template.json` and a private `journal.sqlite3`. JSON/CSV include exact evidence, model output, ground truth for reviewers, citation-reference status, response token fields where available, zero configured retries/fallback, and error types. They contain document text and answers, so treat them as sensitive for any separately approved corpus. Actual billed dollars remain null unless reconciled against provider records; estimated costs do not include provider discounts or guarantees. Gemini output cost estimates require an explicit reasoning-token count and remain unknown if it is absent. Output/reasoning token conventions differ across providers.

Copy `review_template.json` to a separate review file. Each review identifies `case_id`, `model_key`, `repeat`, a `reviewer`, nullable booleans `correctness_human` and `abstention_correct_human`, and a `claim_review` list such as `[{"claim":"...","supported":true,"citation_supported":false,"notes":"..."}]`. Optional `actual_billed_usd` requires `billing_evidence`; use provider invoice/export evidence, and do not assign aggregate invoice costs to individual responses without a defensible allocation. Regenerate reports without any provider requests using the original live options plus `--resume --report-only --reviews /path/to/reviews.json`. The generated template is overwritten when reports are regenerated, so always edit a separate copy.

Provider-specific parameters differ: Gemini uses the provider's default temperature while Groq uses 0.1, and reasoning settings are provider defaults. Both receive the same system instruction, user prompt and frozen context. The direct HTTP adapters bypass application LiteLLM routing, retry and fallback to make request accounting explicit. This isolates generation, but is not a measurement of the complete production request stack. Record versions and review differences before drawing conclusions.

## Development-only pilot prepared by the benchmark audit

**NO-GO until independent human label review and explicit user approval.** The pilot is a separate checksummed synthetic dataset, not the held-out set and not a production retrieval snapshot. It includes one new same-subject conflicting-evidence case; its 12 answers and page labels need separate human adjudication. The `--approve-dataset`, `--confirm-live` and `--confirm-prices` flags do not themselves grant user approval. See `MODEL_BENCHMARK_AUDIT.md` and `BLINDED_REVIEW_RUBRIC.md`.

Offline preflight (no provider requests):

```bash
backend/.venv/bin/python scripts/evaluate_models.py --dry-run --dataset eval/datasets/pilot_dev_v1/dataset.json --mode generation --split dev --max-output-tokens 2048 --timeout 60 --max-requests 36 --max-estimated-usd 1
```

After those blockers are resolved and the user explicitly authorizes paid calls, the exact prospective command is:

```bash
backend/.venv/bin/python scripts/evaluate_models.py --live --confirm-live --confirm-prices --approve-dataset --dataset eval/datasets/pilot_dev_v1/dataset.json --mode generation --split dev --max-output-tokens 2048 --timeout 60 --max-requests 36 --max-estimated-usd 1 --output-dir eval/runs/dev-pilot-live
```

This uses curated page evidence and one response for each of 12 questions from each of three models. It is a generation-only diagnostic, not evidence about production retrieval. The $1 ceiling is a reservation estimate rather than a guaranteed cap on provider charges. Separate output directories have separate journals and can repeat paid requests. The run directory is created private; an existing directory with group/other permissions is refused. Nonempty token-limited outputs are marked `partial`, with raw text and usage retained; HTTP status and timeout classifications are recorded without error bodies or secrets. No reviewed results exist yet.
