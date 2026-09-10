# Assembly Rules — derived from the June 2026 PM baselines vs. published targets

Derived by matching pages between the property managers' baseline exports and the published
investor reports — by normalized text where a text layer exists, by embedded image hash where it
does not. Page counts reconcile exactly in all eight cases.

## Front matter placement (in the published targets)

| Target pages | Order | Properties |
|---|---|---|
| 1, 2, 3 | Balance Sheet, P&L YTD, Distribution Schedule | all except Timber Place, WayPointe |
| 1, 2 | Balance Sheet, P&L YTD | Timber Place (no distribution schedule exists) |
| 10, 11, 12 | Distribution Schedule, Balance Sheet, P&L YTD | WayPointe — last, and reversed |

## Three assembly patterns

### `passthrough` — Bridgewater, Salmon Crossing (Cobalt)

PM source page *n* → target page *n+3*. All pages kept, order preserved, byte-identical.
Cornerstone contributes only front matter.

### `passthrough-ocr` — Timber Place, River Falls (McCathren)

Same page-for-page mapping (offset 2 and 3), but not byte-identical:

| | PM baseline | Target |
|---|---|---|
| Producer | `Adobe PSL 1.3e for Canon` | `Adobe Acrobat (32-bit) 26.1` |
| Creator | `Canon iR-ADV C3826 PDF` | `Adobe Acrobat (32-bit) 26.1` |
| Images | JPEG + PNG layers | JPEG2000, re-encoded |
| Text layer | none — 0 of 23/26 pages | present on every page |

The baselines are flat scans off a Canon multifunction with no text layer at all; the targets
carry searchable text on every page. The manual process runs these through Acrobat OCR before
assembly. **Also:** Timber Place's Financial Aged Receivable (baseline p3) is scanned sideways on
a portrait page and appears rotated upright (792×612) in the target — a rotation step exists too.

OCR of these scans is degraded (`limber Place by the Lake`, `Net Chanae=S00.00`). Do not build
content-based rules on OCR text.

### `missoula-subset` — Fort Grounds, Lolo Peak Village, Mullan Crossing, WayPointe

The baseline holds 15–17 pages across 9 Rent Manager reports. Five survive. The mapping is
identical across all four properties:

| Target position | PM source | Report |
|---|---|---|
| 1st | source p3 | Profit & Loss Comparison |
| 2nd | source p4 | Unit Availability Listing, page 1 |
| 3rd | source p5 | Unit Availability Listing, page 2 |
| 4th | source p1 | Owner Statement, page 1 |
| 5th | source p2 | Owner Statement, page 2 |
| 6th | **no source** | Balance Sheet (cash basis) |

The Owner Statement leads the baseline but trails in the target.

**Always dropped** (9–12 of every ~16 pages): Financial Statement, Rent Roll Analysis, General
Ledger, Actual/Budget Fiscal Year Analysis, Rent Roll – Bank, Delinquency (Detail). Selection is by
**report identity, not page position** — page counts vary by property.

**The unsourced Balance Sheet.** Each target ends with a Rent Manager Balance Sheet that appears
nowhere in the baseline. It is a different report from the baseline's Financial Statement and
carries different figures (Fort Grounds: baseline Financial Statement run 07/01/26 shows bank
126,666.93; target Balance Sheet run 07/10/26 shows 109,979). All four were run 07/10–07/13.
**Per D-03 the v1 output omits it.**

**WayPointe.** One owning entity, two Rent Manager property records ("WayPointe Apartment Homes
LP", "128 S. 5th Street West"). Some reports run once across both (Owner Statement, Financial
Statement, Rent Roll Analysis, General Ledger, Actual/Budget); some run per record (P&L Comparison,
Unit Availability, Delinquency); Rent Roll – Bank is WayPointe-only. The published target reversed
the record order; per D-07 the v1 output uses source order.

## Reconciliation

| Property | Manager | Target | PM source | Used | Dropped | Unsourced in target |
|---|---|---|---|---|---|---|
| Bridgewater | Cobalt | 24 | 21 | 21 | 0 | — |
| Salmon Crossing | Cobalt | 18 | 15 | 15 | 0 | — |
| Timber Place | McCathren | 25 | 23 | 23 | 0 | — |
| River Falls | McCathren | 29 | 26 | 26 | 0 | — |
| Fort Grounds | Missoula | 9 | 16 | 5 | 11 | p9 |
| Lolo Peak Village | Missoula | 9 | 15 | 5 | 10 | p9 |
| Mullan Crossing | Missoula | 9 | 17 | 5 | 12 | p9 |
| WayPointe | Missoula | 12 | 16 | 7 | 9 | p8, p9 |

## Expected v1 output page counts (soft target, D-03/D-06/D-07)

| Property | Front matter | PM pages kept | Total |
|---|---|---|---|
| Fort Grounds | 3 | 5 | 8 |
| Lolo Peak Village | 3 | 5 | 8 |
| Mullan Crossing | 3 | 5 | 8 |
| WayPointe | 3 | 7 | 10 |
| Timber Place | 2 | 23 | 25 |
| River Falls | 3 | 26 | 29 |
| Bridgewater | 3 | 21 | 24 |
| Salmon Crossing | 3 | 15 | 18 |
