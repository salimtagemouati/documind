# Improvement roadmap

| Priority | Work | Impact / effort / risk | Verification |
|---|---|---|---|
| P1 | Atomic quota reservations and durable Stripe event deduplication/reconciliation | Cost and entitlement integrity / medium / schema and rollout risk | Concurrent DB tests; signed duplicate and out-of-order webhook replay |
| P1 | Durable processing queue, isolated parser process, cleanup and object/DB reconciliation | Availability and hostile-file containment / high / deployment complexity | Kill worker, malformed/zip-bomb corpus, storage and DB fault injection |
| P1 | Citation validation and calibrated abstention with independently labeled held-out cases | Trust / high / answer quality trade-off | Human claim-support and negative-case review; publish denominators |
| P1 | Verify deployed RLS, private storage, role grants and cross-tenant isolation | Confidentiality / medium / access-controlled verification | Authorized two-tenant tests on disposable resources; review deployed config |
| P2 | Live ANN/FTS/rerank evaluation with corpus > K and EXPLAIN | RAG validity / medium / low | Exact-vs-ANN recall, sparse-only candidates, paired reranker metrics |
| P2 | Provider token/cost/retry telemetry, global quotas, usage caps and budgets | Cost and operations / medium / privacy | Reconcile usage with invoices; load-test across replicas |
| P2 | Fix multi-document representation and repeated embeddings | Fairness and latency / medium / behavior change | Order permutation, many-document and latency tests |
| P2 | Adopt secure cookie sessions and refresh rotation; CSP | Credential exposure reduction / medium / auth migration | XSS, CSRF, revocation and browser tests |
| P2 | Evaluate hosted GPT-OSS with fixed contexts before enabling | Potential cost/quality / medium / data transfer and provider failure | Blinded benchmark and privacy/contract review |
| P3 | Lock Python transitive dependencies, vulnerability scanning, UI E2E/a11y | Reproducibility and UX / medium / low | Clean CI install, dependency scan, keyboard/mobile journeys |

This branch implements only an opt-in generation route and modest reporting/cache improvements. It does not add schemas, change embeddings, deploy, create billing traffic or claim the above gates passed.
