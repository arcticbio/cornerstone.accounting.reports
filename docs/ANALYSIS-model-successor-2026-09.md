# Analysis — running on Opus 5's successor (`claude-opus-5-5`), 2026-09

Why this exists: `claude-opus-5` (and `claude-sonnet-5`) will be retired. This records what
`crr` needs to run on the next Opus, measured rather than assumed, so that the switch is an
environment variable on the day and not an incident. It does **not** switch production:
`Settings.model` still defaults to `claude-opus-5`.

Branch `claude/gracious-dirac-t7w39j`. Code: A-14 in `QUESTIONS.md`, SPEC §7.2.

## What breaks, and what was changed

| Opus 5.5 difference | Effect on `crr` if only `CRR_MODEL` changes | Change |
|---|---|---|
| `tool_choice: {type: "tool"}` → **400** | **Every page request fails.** Confirmed live. | `auto` + `strict` + `disable_parallel_tool_use`, one instruction appended to the cached system block. Forced path kept, byte-identical, for the models known to accept it. Unknown models take the `auto` path. |
| Thinking cannot be disabled | `max_tokens=400` could be spent on thinking before the tool call → page `unknown` → review | 4096 on the `auto` path; a `max_tokens` stop is logged as `classify.max_tokens` |
| Not in the price table | Every manifest and eval reports **$0.00** | Row added: $4 / $0.20 read / $8 1h-write / $20 |
| Default effort `medium` (was `high`) | Classifier: none — it sends `low` explicitly. Arbiter: sends none, so it runs at `medium` | None needed — arbiter measured at 12/12 at the default |
| Broader safety classifiers (`bio`, `reasoning_extraction`) | A decline → `unknown` → review (D-12) | None; zero declines in 3 × 172 pages |
| Thinking blocks bound to model/conversation | None — one single-turn request per page, nothing replayed | None |

## Results — 31 documents, 172 golden pages, June 2026 bundle

| Run | Model | Effort | Page acc. | Cont. | Record | Orient. | Boundary F1 | Input | Cache read | Output | Thinking tok. | **USD** |
|---|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|
| baseline (this branch) | opus-5 | low | 100 % | 100 % | 100 % | 1/1 | 1.0000 | 695,657 | 606,465 | 34,681 | 0 | **$4.67** |
| 1 | opus-5-5 | low | 100 % | 100 % | 100 % | 1/1 | 1.0000 | 674,123 | 607,374 | 40,443 | 157 | **$3.68** |
| 2 (repeat) | opus-5-5 | low | 100 % | 100 % | 100 % | 1/1 | 1.0000 | 674,123 | 614,639 | 40,682 | 350 | **$3.63** |
| 3 | opus-5-5 | medium | 100 % | 100 % | 100 % | 1/1 | 1.0000 | 674,123 | 614,639 | 45,206 | 3,149 | **$3.72** |

Reports: `eval/reports/20260925T2142*–2219*`. Per-call data from the `classify.call` log events.

- **Every call returned the tool on the first attempt** under `auto` — 172/172 × 3, no repair,
  no prose answers, no `max_tokens` stops, no refusals.
- **Confidence unchanged:** min 0.95, median 0.97 on both models at `low` (0.93 min at
  `medium`); nothing near the 0.85 gate.
- **Cost −21 to −22 %.** Almost all of it is the input price ($3.48 → $2.70). Output is *up*
  17 % per page (median 233 vs 200 tokens) — longer tool arguments, not thinking; at `low` the
  model thought on 1–4 pages of 172. Cache reads cost $0.12 instead of $0.30 (0.05× input).
  Input tokens are 3 % lower: an `auto` request carries a smaller tool-use system preamble than
  a forced one.
- **`medium` buys nothing here** — same scores, 9× the thinking, +$0.09. Keep `low`.
- **Orientation arbiter** (plain-text call, runs at the model default `medium`): 12/12 on
  Timber Place — 6/6 shuffled trials of the page that once shipped upside down (p3,
  `rotated_90_ccw`) and 6/6 upright pages.
- **End-to-end `crr build --period 2026-06`**, local repository: five properties built, every
  page count equal to golden (Fort Grounds 8, Lolo Peak 8, Mullan Crossing 8, WayPointe 10,
  Timber Place 25), Timber Place p5 opened and checked right-side-up. **River Falls,
  Bridgewater and Salmon Crossing did not run**: the account hit its monthly API spend limit
  mid-build (`400 … You have reached your specified API usage limits. You will regain access
  on 2026-10-01`). Their classification is covered by the eval above; their composition on
  5.5 is not yet exercised. Re-run after 1 October (~$2.70).

Spend for this investigation: ≈ $19.

## Not changed, deliberately

- **Default model.** Production keeps `claude-opus-5` until someone decides otherwise.
- **Refusal fallbacks.** Review over guess (D-12) already handles a decline safely, and a
  fallback to the model being retired is no fallback.
- **The 1-hour cache TTL.** Still correct; unchanged economics.
