# Investor Report Component Structure — June 2026 baseline

Page-level anatomy of the eight June 2026 investor report packages (the *published targets*),
grouped by reporting property manager. Derived from the source PDFs; page ranges verified against
printed footers. 135 pages total.

## Sources

Four distinct producing organizations. Three are third-party property managers; the fourth is
Cornerstone's own books, which contributes the same front matter to every package.

| Target property | Owning entity | Reporting PM | Property name in PM system | Pages | PM section |
|---|---|---|---|---|---|
| Fort Grounds | Fort Grounds Apartment Homes LP | Missoula PM | Fort Grounds Apartment Homes | 9 | 4–9 |
| Lolo Peak Village | Lolo Peak Village LP | Missoula PM | Lolo Peak Village LP | 9 | 4–9 |
| Mullan Crossing | Mullan Crossing Apartment Homes LP | Missoula PM | The Vantage — 2370 Clark Fork Ln | 9 | 4–9 |
| WayPointe | WayPointe Apartment Homes LP | Missoula PM | WayPointe AH LP *and* 128 S. 5th Street West | 12 | 1–9 |
| Timber Place | Timber Place Apartment Homes LP | McCathren | Timber Place by the Lake (1000) | 25 | 3–25 |
| River Falls | River Falls Opportunity Zone Fund LLC | McCathren | River Falls Apartments (0312) | 29 | 4–29 |
| Bridgewater | Bridgewater Apartment Homes LP Et Al | Cobalt | 411 — Bridgewater, 61580 Brosterhous Rd, Bend OR | 24 | 4–24 |
| Salmon Crossing | Salmon Crossing Opportunity Zone LLC | Cobalt | 405 — Salmon Crossing, 2000 SW Salmon Ave, Redmond OR | 18 | 4–18 |

## Cornerstone Management Consulting — shared front matter

QuickBooks Online (accrual) plus one spreadsheet export. Entity-level, not property-level.
Page geometry 619×802 pt portrait; distribution schedule 792×612 landscape.

Standard block, pages 1–3:

1. **Balance Sheet** — as of Jun 30, 2026, accrual, full LP/LLC balance sheet including mortgage and fixed assets.
2. **Profit and Loss YTD Comparison** — Apr–Jun 2026 vs Jan–Jun 2026, accrual, ends at Net Income after depreciation and interest.
3. **Investor Distribution Schedule** — landscape spreadsheet, Jan–Dec grid by investor profile ID and ownership %.

Deviations:

- **Timber Place** has no distribution schedule — only pages 1–2.
- **WayPointe** places the block last and reversed: p10 distribution schedule, p11 Balance Sheet, p12 P&L YTD Comparison.
- **Mullan Crossing** carries three ownership-% columns (restated as of 4/1/2026 and 6/1/2026).

Front matter names the owning entity; manager pages name the physical property.

## Missoula Property Management (Rent Manager)

Rent Manager rev.12.2605, cash basis. Footers read `rentmanager.com`. Covers Fort Grounds, Lolo Peak Village, Mullan Crossing, WayPointe.

**Fort Grounds (9 pp)** — 1–3 Cornerstone · 4 Profit & Loss Comparison · 5 Unit Availability Listing · 6 Unit Availability Summary by Unit Type · 7–8 Owner Statement · 9 Balance Sheet (cash basis)

**Mullan Crossing (9 pp)** — identical.

**Lolo Peak Village (9 pp)** — identical, except p6 is a footer-only continuation.

**WayPointe (12 pp)** — two records, manager section first: 1 P&L — 128 S. 5th · 2–3 Unit Availability — 128 S. 5th · 4 P&L — WayPointe · 5–6 Unit Availability — WayPointe · 7 Owner Statement (combined) · 8 Balance Sheet — 128 S. 5th · 9 Balance Sheet — WayPointe · 10–12 Cornerstone, reversed

## McCathren Management & Real Estate Services

Property-accounting suite, cash book. Pages are scanned; text extraction is lossy. Covers Timber Place, River Falls.

**Timber Place (25 pp)** — 1–2 Cornerstone (no distribution schedule) · 3 cover letter · 4 Manager's Report — Market Property · 5 Financial Aged Receivable · 6–7 Rent Roll with Lease Charges · 8 Budget Variance Report · 9–10 Budget Comparison Cash Flow · 11 Operating Statement — Summary · 12–14 Cash Flow Statement · 15–16 Balance Sheet · 17–18 Trial Balance · 19–25 General Ledger

**River Falls (29 pp)** — 1–3 Cornerstone · 4 cover letter · 5 Manager's Report · 6–9 Rent Roll · 10 Budget Variance Report · 11–12 Budget Comparison Cash Flow · 13 Operating Statement — Summary · 14–16 Cash Flow Statement · 17–18 Balance Sheet · 19–20 Trial Balance · 21–29 General Ledger

River Falls carries no aged-receivable page; Timber Place does.

## Cobalt Properties Group

Bend, OR. Cash basis. Every page footed "Created on 07/15/2026" plus the report name. Covers Bridgewater, Salmon Crossing.

**Bridgewater (24 pp)** — 1–3 Cornerstone · 4–12 Owner Statement ("Page n of 9") · 13–16 Cash Flow — 12 Month · 17–19 Rent Roll · 20 Balance Sheet · 21–24 Annual Budget — Comparative

**Salmon Crossing (18 pp)** — 1–3 Cornerstone · 4–8 Owner Statement ("Page n of 5") · 9–12 Cash Flow — 12 Month · 13 Rent Roll · 14 Balance Sheet · 15–18 Annual Budget — Comparative

## Splitting signals

- **Page geometry** — 619×802 QuickBooks; 792×612 landscape for distribution schedules and Cobalt comparatives; 612×792 Rent Manager.
- **Footer fingerprints** — `rentmanager.com`, `Created on 07/15/2026 Page n`, `Page n of m`.
- **Naming split** — entity name on Cornerstone pages; property name or internal ID (0312, 1000, 411, 405, 2370, 2550) on manager pages.
- **Accounting basis** — front matter is accrual; every manager section is cash basis. The two will not reconcile; do not build validation that assumes they should.

## Implications

- "Balance Sheet" appears in all four sources and means something different in each — component types need a source qualifier.
- Rent rolls range from 1 to 9 pages.
- WayPointe and Timber Place break positional assumptions.
- Cover letters are the only narrative content; Missoula supplies none.
- General Ledger detail is McCathren-only (16 of 135 pages).
