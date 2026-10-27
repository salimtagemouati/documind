# Provider readiness and three-request compatibility smoke test

**Current state: not approved or live-verified.** This checklist concerns the fictional development pilot only. No key was inspected, no account access was checked, no spending controls were changed, and no model inference request was made while preparing it. Complete the items with an authorized account owner; never paste keys into this document, commands, logs, review packets, or chat.

## Human review and authorization

- [ ] An independent reviewer marks each of the 12 items in `PILOT_DEV_REVIEW_PACKET.md` Accept, Reject, or Needs correction, with rationale and provenance. Adjudicate `delta-08` (comparison, not same-subject contradiction), the Northbridge conflict, absence labels, and source-number traps. A corrected frozen dataset needs a new version and checksum; do not edit v1 held-out labels.
- [ ] The user explicitly authorizes **only** a three-request compatibility test, approves disclosure of the synthetic `atlas-01` context to Google and Groq, and approves the request ceiling and estimated cost budget. The command flags record those confirmations; they are not themselves authorization.
- [ ] The user separately approves any later 36-request model pilot. Passing the smoke test does not authorize that pilot or production use.

## Credentials and model access — account state unknown

- [ ] Confirm privately that the intended Google project has a working `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) and that the intended Groq organization has a working `GROQ_API_KEY`. Restrict access and set them in the process environment only; do not print their values. No credentials are provisioned by this checklist.
- [ ] Confirm account-specific region, project, organization, quota and permissions for `gemini-3.5-flash-lite`, `openai/gpt-oss-120b`, and `openai/gpt-oss-20b`. Public documentation lists the [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) and [Groq production models](https://console.groq.com/docs/models), but listing is not proof this account can invoke them. This is ultimately verified by the authorized smoke requests.
- [ ] Review request-shape and setting differences: Gemini uses `generateContent`, `maxOutputTokens=1024`, provider-default temperature/thinking; Groq uses chat completions, `max_completion_tokens=1024`, temperature 0.1 and provider-default reasoning. Limits include output/reasoning according to provider behavior; truncation or a timeout does not necessarily mean the model is unavailable. See [Google GenerateContent](https://ai.google.dev/api/generate-content) and [Groq API](https://console.groq.com/docs/api-reference).

## Prices and privacy — public documentation checked, account terms unknown

- [ ] Recheck the applicable model, tier, rates, currency, region and billing status immediately before authorization. As of the documentation checked 2026-10-26, standard paid text rates per million input/output tokens were Google $0.30/$2.50, Groq 120B $0.15/$0.60, and Groq 20B $0.075/$0.30. Thinking, cache, failed requests, taxes and other terms can affect charges. See [Google pricing](https://ai.google.dev/gemini-api/docs/pricing) and [Groq model prices](https://console.groq.com/docs/models).
- [ ] Review the selected Gemini tier and [Gemini API terms](https://ai.google.dev/gemini-api/terms). Google's pricing page indicates free-tier content may be used to improve products while paid standard content is not; confirm the terms that apply to the account and dataset.
- [ ] Review [Groq data controls](https://console.groq.com/docs/your-data), location and retention. Groq documents possible retention for reliability/abuse monitoring up to 30 days and an optional zero-data-retention setting; verify the actual organization's configuration and contract. Only fictional pilot excerpts are approved for consideration here; no customer documents are included.

## Spending controls — configuration not inspected or changed

- [ ] Record the user-approved dollar budget and confirm the applicable provider-side limit, account tier, responsible owner, alerts and any existing project/organization usage. The harness's `--max-estimated-usd 0.05` is a request-reservation estimate, **not a guaranteed hard billing cap**; charges may exceed it.
- [ ] For Gemini, assess available [AI Studio project spend caps](https://ai.google.dev/gemini-api/docs/billing/) or eligible [Cloud Billing spend cap budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps). Google describes project spend caps as experimental with reporting/enforcement delay and possible overage; alerts-only budgets do not stop usage. Availability and permissions depend on the account.
- [ ] For Groq, assess the [organization spending limit](https://console.groq.com/docs/spend-limits). Groq describes a paid-tier/owner requirement and a 10–15 minute tracking delay, so overages may occur. Verify applicability rather than assuming it is active.
- [ ] Decide who will reconcile any timeout or interrupted request against provider usage before deciding whether to repeat it. The journal prevents automatic replay only within the same output directory; a new directory may duplicate charges. Actual billed usage may be unavailable per request.

## Offline verification — no provider calls

The smoke test uses the first frozen development case, `atlas-01`, once for each model. These offline commands must not issue provider calls. `--dry-run` checks local request construction only; `--mock` produces fake abstentions and cannot establish provider compatibility.

```bash
backend/.venv/bin/python scripts/evaluate_models.py --dry-run --dataset eval/datasets/pilot_dev_v1/dataset.json --mode generation --split dev --limit-cases 1 --models gemini oss120 oss20 --repeats 1 --max-output-tokens 1024 --timeout 60 --max-requests 3 --max-estimated-usd 0.05
```

A dry run on 2026-10-26 reported three planned requests and an estimated reservation of $0.00543145; this is not measured or guaranteed cost. Automated tests additionally assert that even supplying confirmation flags in mock or dry-run mode cannot dispatch a provider call. `--live`, `--mock`, and `--dry-run` are mutually exclusive, and omitting all three selects dry-run. Adding `--confirm-live` alone never selects live mode.

## Prospective live command — DO NOT RUN without explicit authorization

After completing the checks and receiving the user's explicit authorization, use this command exactly once:

```bash
backend/.venv/bin/python scripts/evaluate_models.py --live --confirm-live --confirm-prices --approve-dataset --dataset eval/datasets/pilot_dev_v1/dataset.json --mode generation --split dev --limit-cases 1 --models gemini oss120 oss20 --repeats 1 --max-output-tokens 1024 --timeout 60 --max-requests 3 --max-estimated-usd 0.05 --output-dir eval/runs/provider-smoke-v1
```

This plans at most one request per named model, three total, with no automatic retries or fallback. Budget exhaustion, missing credentials or other failures can prevent all three from being attempted. A timeout or error can still incur charges; `started` means the result is ambiguous and is not automatically resent. Resume only with the same command plus `--resume`, and never create a new output directory to repeat requests without separately accounting for prior usage and authorization. Inspect returned model identifiers, status, finish reason, actual usage fields, partial/error rows and provider billing; no result establishes RAG quality or authorizes the full pilot.
