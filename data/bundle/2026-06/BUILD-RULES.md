# Assembly rules, derived from the June 2026 examples

Every rule below was derived by matching pages between the PM baselines and the
targets — by normalized text where a text layer exists, by embedded image hash
where it does not. Page counts reconcile exactly in all eight cases.

## Front matter placement

Cornerstone's components lead the package in seven of eight cases:

| Target pages | Order | Properties |
|---|---|---|
| 1, 2, 3 | Balance Sheet, P&L YTD, Distribution Schedule | all except Timber Place, WayPointe |
| 1, 2 | Balance Sheet, P&L YTD | Timber Place (no distribution schedule exists) |
| 10, 11, 12 | Distribution Schedule, Balance Sheet, P&L YTD | WayPointe — **last, and reversed** |

WayPointe is the only package where the manager's section leads and the
Cornerstone block trails. Placement cannot be assumed from position.

---

## Pattern: `passthrough`

**Bridgewater, Salmon Crossing** — Cobalt Properties Group.

PM source page *n* → target page *n + 3*. All 21 / 15 pages kept, order
preserved, content byte-identical. Cornerstone contributes only the front matter.

This is the trivial case and the right one to implement first.

---

## Pattern: `passthrough-ocr`

**Timber Place, River Falls** — McCathren Management.

Same page-for-page mapping as `passthrough` (offset by 2 and 3 respectively),
but the pages are not byte-identical:

| | PM baseline | Target |
|---|---|---|
| Producer | `Adobe PSL 1.3e for Canon` | `Adobe Acrobat (32-bit) 26.1` |
| Creator | `Canon iR-ADV C3826 PDF` | `Adobe Acrobat (32-bit) 26.1` |
| Images | JPEG + PNG layers | JPEG2000, re-encoded |
| Text layer | **none — 0 of 23/26 pages** | **present on every page** |

The baselines come straight off a Canon multifunction as flat scans with no text
at all. The published targets carry a searchable text layer on every page. So
the current process runs these through Acrobat OCR before assembly.

**Implication:** the pipeline needs an OCR stage for this manager, and OCR
quality is the accuracy ceiling for anything downstream that reads these pages.
The extracted text in the targets is visibly degraded (`limber Place by the
Lake`, `Net Chanae=S00.00`), so do not build content-based rules on it.

---

## Pattern: `missoula-subset`

**Fort Grounds, Lolo Peak Village, Mullan Crossing, WayPointe** — Missoula
Property Management (Rent Manager).

The baseline contains 15–17 pages across 9 distinct Rent Manager reports. Five
survive. The mapping is identical across all four properties:

| Target position | PM source | Report |
|---|---|---|
| 1st | source p3 | Profit & Loss Comparison |
| 2nd | source p4 | Unit Availability Listing, page 1 |
| 3rd | source p5 | Unit Availability Listing, page 2 |
| 4th | source p1 | Owner Statement, page 1 |
| 5th | source p2 | Owner Statement, page 2 |
| 6th | **no source** | Balance Sheet (cash basis) |

Note the reordering: the Owner Statement leads the baseline but trails in the
target.

### Always dropped

Every one of these reports is discarded in all four packages:

- Financial Statement (2 pp)
- Rent Roll Analysis (2–3 pp)
- General Ledger (1 p)
- Actual/Budget Fiscal Year Analysis (3 pp)
- Rent Roll – Bank (1–2 pp)
- Delinquency (Detail) (1–2 pp)

That is 9–12 of every ~16 pages. The selection is by **report identity**, not
page position — page counts vary by property, so a rule keyed on page numbers
will break.

### The unsourced Balance Sheet

Each target ends with a Rent Manager Balance Sheet that appears nowhere in the
PM baseline. It is a different report from the baseline's Financial Statement and
carries different figures:

| Fort Grounds | Bank account |
|---|---|
| Baseline p6, Financial Statement, run 07/01/26 08:00 | 126,666.93 |
| Target p9, Balance Sheet, run 07/10/26 09:11 | 109,979 |

All four Balance Sheets in the targets were run 07/10–07/13, over a week after
the baseline export. **This report must be added to the input set** — as it
stands, these four properties cannot be reproduced from the bundle.

### WayPointe

Same rules, applied to a two-property package. The baseline orders WayPointe AH
LP first and 128 S. 5th Street West second; the target reverses that, running 128
S. 5th Street West's P&L and Unit Availability first. The single combined Owner
Statement follows, then two separately-run Balance Sheets — one per property,
both unsourced.

---

## Summary

| Property | Manager | Target | PM source | Used | Dropped | Unsourced target pages |
|---|---|---|---|---|---|---|
| Bridgewater | Cobalt | 24 | 21 | 21 | 0 | — |
| Salmon Crossing | Cobalt | 18 | 15 | 15 | 0 | — |
| Timber Place | McCathren | 25 | 23 | 23 | 0 | — |
| River Falls | McCathren | 29 | 26 | 26 | 0 | — |
| Fort Grounds | Missoula | 9 | 16 | 5 | 11 | p9 |
| Lolo Peak Village | Missoula | 9 | 15 | 5 | 10 | p9 |
| Mullan Crossing | Missoula | 9 | 17 | 5 | 12 | p9 |
| WayPointe | Missoula | 12 | 16 | 7 | 9 | p8, p9 |

## Open questions for the build

1. **Is the Missoula drop list a standing rule or a monthly judgment call?** One
   period of evidence shows it is perfectly consistent across four properties,
   which suggests a rule — but it cannot be distinguished from a habit until a
   second period is available.
2. **Who runs the Missoula Balance Sheet, and can it be exported with the rest?**
   Adding it to the baseline export would remove the only genuine gap in the
   bundle.
3. **Can McCathren deliver a digital export instead of scans?** That would remove
   the OCR stage and its error floor entirely.
4. **Is WayPointe's reversed front matter intentional?** It is the only such case,
   and it is the kind of thing that reads as an assembly slip rather than a rule.
