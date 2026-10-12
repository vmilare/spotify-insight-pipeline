# Cost and runtime calculator — report

Generated 2026-10-12T04:58:57+00:00 by `python cost/calculator.py` (offline replay; rate scale 1.0). Inputs: `cost/usage.csv`, `cost/rates.csv`, `cost/pilot_measurements.json`, `cost/assumptions.yaml`.

## 1. Measured: real 100-review pilot (`cost_100.csv`)

- Input `cost_100.csv` · SHA-256 `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e` · matches manifest: **True** · 100 IDs · 100 unique texts
- Workspace `pilot-20261011T215750` (empty result cache at start) · workers: 1 · run at 2026-10-12T04:57:50+00:00
- Record statuses (cold): {'completed': 100}

| Stage | Provider / model | Effort / settings | Prompt / schema | Batch | Cold requests (attempts) | Failed | Cache hits (warm) | Cold usage | Cold API cost | Warm requests | Warm cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ingest | local code / `-` | - | - | CSV stream | 0 (0) | 0 | - | — | $0.000000 | 0 | $0.000000 |
| enrich | TypeSafe / `jev-1.13.0` | questions: topic, intent, severity (Choice) | jev-1.13.0+jev-q-tiny-v1-pack10+schema-v1+quote-v1+sent-from-intent-v1 | 10 reviews/request | 10 (10) | 0 | 0 new requests | input 46,807, output 18,808 | $0.001966 | 0 | $0.000000 |
| verify | Anthropic / `claude-haiku-5-5` | effort low, thinking off | verify-v1 / JSON schema | 25 reviews/request | 1 (1) | 0 | 1 | input 2,459, output 750 | $0.000621 | 0 | $0.000000 |
| group | local code / `-` | issues-v2 keyword rules | - | - | 0 (0) | 0 | - | — | $0.000000 | 0 | $0.000000 |
| group_review | Anthropic / `claude-haiku-5-5` | effort low, thinking off | group-review-v1 / JSON schema | 1 request/topic, ≤12 quotes/issue | 8 (8) | 0 | 8 | input 9,849, output 2,028 | $0.001999 | 0 | $0.000000 |
| rank | local code / `-` | - | - | - | 0 (0) | 0 | - | — | $0.000000 | 0 | $0.000000 |
| recommend | Anthropic / `claude-sonnet-5-5` | effort high, adaptive thinking, fallbacks default | memo-v1 / JSON schema | 1 evidence pack | 1 (1) | 0 | 1 | input 9,413, output 4,131 | $0.060136 | 0 | $0.000000 |

**Cold run:** API cost **$0.064722** · end-to-end wall clock **52.614 s** (stage clocks: ingest 0.004s, enrich 1.557s, verify 3.280s, group 0.017s, group_review 18.637s, rank 0.004s, recommend 29.114s)
- Cost per 1,000 input rows: $0.6472 · per completed record: $0.000647 · enrichment throughput 64.52 texts/s (1 worker)
- **Warm run** (same settings, saved results): enrichment requests **0**, downstream model calls 0, incremental API cost **$0.000000**, wall clock **0.034 s**
- API spend vs other costs: all figures above are API spend from recorded usage. Local compute (laptop CPU/electricity): **unknown, not measured** (Pipeline runs on a laptop; electricity/hardware cost not measured. Reported as unknown, not zero.)

## 2. Estimate refreshes on development checkpoints (enrichment, main workspace)

| Checkpoint | Run | Texts labeled | Cache-hit reviews | Tokens / text | Texts / s | Workers |
|---|---|---|---|---|---|---|
| cost_100 | `main-cost_100-20261011T203957` | 100 | 0 | 468.1 | 68.37 | 1 |
| checkpoint_500 | `main-checkpoint_500-20261011T204012` | 379 | 112 | 467.7 | 68.52 | 1 |

Projection basis: **467.7 tokens/text**, **68.52 texts/s per worker** from checkpoint_500 run main-checkpoint_500-20261011T204012; 4 workers at 0.8 efficiency → 3.4× (modeled, not measured).

## 3. Full-run projection (660,622 rows · 660,609 nonempty · 13 empty-text quarantines)

| Scenario | Exact-text reuse | Model work units | Enrich | Verify | Group review | Memo | Total API | Elapsed |
|---|---|---|---|---|---|---|---|---|
| base | yes (484,189 texts) | 484,189 | $9.70 | $0.016 | $0.002 | $0.060 | **$9.78** | 0.7 h |
| base | no (660,609 reviews) | 660,609 | $13.24 | $0.016 | $0.002 | $0.060 | **$13.31** | 0.9 h |
| conservative | yes (484,189 texts) | 484,189 | $10.46 | $0.023 | $0.004 | $0.120 | **$10.61** | 0.7 h |
| conservative | no (660,609 reviews) | 660,609 | $14.27 | $0.023 | $0.004 | $0.120 | **$14.42** | 1.0 h |

Fixed overhead (group review, memo) is counted once, not per review. Fallback model cost is $0 by design (no stronger-model fallback; low-confidence labels are flagged needs_review instead).

## 4. Controls and budget

- Budget (project spending limit): **$11.00** · already spent (ledger): **$0.1650** · remaining: **$10.8351**
- Max workers: 4 · fallback fraction: 0.0 · output-token caps per request: {'verify': 3000, 'group_review': 3000, 'memo': 16000} (Jev output tokens are free)
- Enforcement in code: spend ledger reserves worst-case cost before each request and refuses to send past the cap (`config/settings.yaml` budget); circuit breaker after consecutive failures; bounded retries with backoff + jitter.
- ✓ base / reuse fits: $9.94 ≤ $11.00
- ⚠ **base / no reuse exceeds the budget**: $0.16 + $13.31 = $13.48 > $11.00
- ✓ conservative / reuse fits: $10.77 ≤ $11.00
- ⚠ **conservative / no reuse exceeds the budget**: $0.16 + $14.42 = $14.59 > $11.00

## 5. Rates used (editable `cost/rates.csv`)

| Provider | Model | Billing item | USD per unit | Unit size | Source | Checked |
|---|---|---|---|---|---|---|
| typesafe | jev-1.13.0 | input_tokens | 0.042 | 1000000 tokens | https://docs.typesafe.ai/models | 2026-10-11 |
| typesafe | jev-1.13.0 | output_tokens | 0 | 1000000 tokens | https://docs.typesafe.ai/models | 2026-10-11 |
| anthropic | claude-haiku-5-5 | input_tokens | 0.1 | 1000000 tokens | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-11 |
| anthropic | claude-haiku-5-5 | output_tokens | 0.5 | 1000000 tokens | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-11 |
| anthropic | claude-haiku-5-5 | cache_write_tokens | 0.125 | 1000000 tokens | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 2026-10-11 |
| anthropic | claude-haiku-5-5 | cache_read_tokens | 0.01 | 1000000 tokens | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 2026-10-11 |
| anthropic | claude-sonnet-5-5 | input_tokens | 2 | 1000000 tokens | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-11 |
| anthropic | claude-sonnet-5-5 | output_tokens | 10 | 1000000 tokens | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-11 |
| anthropic | claude-sonnet-5-5 | cache_write_tokens | 2.5 | 1000000 tokens | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 2026-10-11 |
| anthropic | claude-sonnet-5-5 | cache_read_tokens | 0.2 | 1000000 tokens | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 2026-10-11 |

Formula: item_cost = billed_units × (usd_per_unit / unit_size); items are mutually exclusive (input = uncached input; output already includes thinking tokens); total = Σ item_cost.
