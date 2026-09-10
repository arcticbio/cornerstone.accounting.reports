# Investor Report Assembly — training bundle, June 2026

Eight worked examples for a system that assembles investor report packages from
two upstream sources. Each property folder holds the **inputs**, the **target
output**, and a **build spec** that maps every target page back to the input page
it came from.

## Layout

```
<Property Manager>/
  <Property>/
    2026-06 June/
      inputs/
        05 PM Source - <Manager> Baseline.pdf        ← property manager's monthly export
        01 Cornerstone - Balance Sheet.pdf           ← Cornerstone additive component
        02 Cornerstone - Profit and Loss YTD Comparison.pdf
        03 Cornerstone - Investor Distribution Schedule.pdf
      target/
        TARGET - 06 June 2026 - <Property> - Investor Reports.pdf
      reference/
        04 Target PM Section (as published).pdf      ← the PM half of the target, extracted
      build-spec.json
```

`inputs/` is what the system is given. `target/` is what it must produce.
`reference/` is derived from the target and exists only for scoring — it is **not
an input**, and a build that reads from it is cheating.

`index.json` at the root summarizes all eight; `build-spec.json` in each folder
carries the page-by-page plan.

## The two input streams

**Property manager source** — the manager's own monthly export, unmodified. This
is the bulk of the package.

**Cornerstone additive components** — entity-level accounting produced by
Cornerstone in QuickBooks plus a spreadsheet export. One page each:

| File | Basis | Content |
|---|---|---|
| `01` Balance Sheet | Accrual | Full LP/LLC balance sheet incl. mortgage and fixed assets |
| `02` Profit and Loss YTD Comparison | Accrual | Quarter vs. YTD, through Net Income |
| `03` Investor Distribution Schedule | — | Landscape, monthly grid by investor profile ID |

Timber Place has no `03`; its front matter is two pages.

## The three assembly patterns

See `BUILD-RULES.md` for the full derivation. In short:

| Pattern | Properties | What happens to the PM source |
|---|---|---|
| `passthrough` | Bridgewater, Salmon Crossing | Every page kept, in order, unmodified |
| `passthrough-ocr` | Timber Place, River Falls | Every page kept in order, but re-encoded with an OCR text layer added |
| `missoula-subset` | Fort Grounds, Lolo Peak Village, Mullan Crossing, WayPointe | Only 5 of ~16 pages kept, **reordered**, and one report appears in the target that is not in the source at all |

## The hard part

`missoula-subset` is where the work is. Two-thirds of the PM source is discarded,
the surviving pages are resequenced, and each target carries a **Balance Sheet
that has no source page in the bundle** — it was run separately out of Rent
Manager on a later date, with different figures than the Financial Statement in
the baseline. Those pages are listed as `unsourced_target_pages` in every spec.
A system built only from the files here cannot reproduce them; that report has to
be added to the input set before these four properties can be built end to end.

## Scoring a build

For `passthrough`, page equality against the target is exact. For
`passthrough-ocr` the raster content matches but the byte stream does not — the
targets were rebuilt in Acrobat with JPEG2000 re-encoding — so compare rendered
pages, not bytes. For `missoula-subset`, compare page sequence and per-page report
identity; exact byte equality is only achievable on the pages copied from the
baseline.
