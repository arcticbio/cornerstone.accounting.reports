# Cornerstone Report Assembler — Technical Specification

Version 1.0 · September 2026 · Status: **authoritative for the v1 build**

This document is the contract for the system. `PLAN.md` says in what order to build it;
`DECISIONS.md` says why things are the way they are; `QUESTIONS.md` lists what is still open
and what to assume meanwhile. Where this document and the code disagree, this document wins
until it is amended by a commit that says so.

---

## 1. Purpose

Cornerstone Management Consulting sends quarterly investor report packages for eight rental
properties. Each package is assembled by hand from two upstream sources:

1. **The property manager's monthly export** — one PDF per property, from one of three managers,
   each with a different system and a different report set.
2. **Cornerstone's own entity-level accounting** — three single-page PDFs per property
   (Balance Sheet, P&L YTD Comparison, Investor Distribution Schedule) from QuickBooks Online and
   a spreadsheet.

The system replaces the hand assembly. It classifies every page of the manager's export into a
known section vocabulary, resolves an output definition into a page plan, and composes the final
PDF — deterministically, with a manifest that records exactly what was built from what.

The published June 2026 packages are a **soft target**: the output should resemble them, but where
they contain material that is not in any available source, that material is dropped, not
recreated (D-03).

Prior analysis, kept alongside this spec:

- `docs/ANALYSIS-component-structure-2026-06.md` — page-level anatomy of the published packages
- `docs/ANALYSIS-assembly-rules-2026-06.md` — what the manual process does to each source

---

## 2. Repository layout (target state after Phase 0)

```
.
├── CLAUDE.md                     Claude Code operating instructions (short; points here)
├── HANDOFF.md                    Human runbook: launching and steering the build
├── PROGRESS.md                   Phase/task checklist — the build's persistent state
├── pyproject.toml                Python 3.12, uv, ruff, mypy, pytest
├── uv.lock
├── Dockerfile
├── .github/workflows/
│   ├── ci.yml                    lint + type-check + unit tests + offline eval on every PR
│   └── build-period.yml          workflow_dispatch: run a build for a period (fallback host)
├── .claude/settings.json         SessionStart hook → scripts/session_start.sh
├── scripts/
│   └── session_start.sh          uv sync; verify tesseract; print PROGRESS summary
├── config/
│   ├── properties.yaml           property registry (managers, entities, records, folders)
│   ├── schemas/*.yaml            one source schema per producing system
│   └── outputs/*.yaml            one output definition per property manager
├── data/
│   └── bundle/2026-06/           the golden June bundle (moved from "Report Assembly Bundle/")
├── eval/
│   └── golden/<pm>/<property>.json   page-level labels for every 2026-06 source document
├── docs/
│   ├── SPEC.md  PLAN.md  DECISIONS.md  QUESTIONS.md
│   ├── ANALYSIS-*.md
│   └── RUNBOOK.md                operating the deployed system (written in Phase 9)
├── infra/                        Bicep for Azure Container Apps Job (Phase 8)
├── src/crr/                      the package ("Cornerstone Report Runner")
│   ├── __init__.py
│   ├── cli.py                    Typer CLI: build, classify, eval, inspect, validate-config
│   ├── settings.py               pydantic-settings; all env vars documented here
│   ├── models/                   domain models (section 3)
│   ├── config/                   YAML loaders + validators for schemas/outputs/properties
│   ├── repository/               SourceRepository protocol; local_fs.py; google_drive.py
│   ├── preprocess/               render.py (pypdfium2), text.py (pypdf), ocr.py (ocrmypdf)
│   ├── classify/                 Classifier protocol; anthropic_classifier.py; golden_classifier.py; footer_check.py
│   ├── segment/                  run-length segmentation + cardinality validation
│   ├── resolve/                  address grammar parser + resolver
│   ├── compose/                  pypdf composer; bookmarks; rotation; metadata
│   ├── manifest/                 BuildManifest writer + JSON schema
│   ├── review/                   review-gate rules
│   └── pipeline.py               orchestrates one property build end to end
└── tests/
    ├── unit/                     no network, no API key
    ├── integration/              marked `api`; skipped without ANTHROPIC_API_KEY
    └── eval/                     the eval harness entry point
```

Package name `crr`; CLI executable `crr`.

---

## 3. Domain model

All models are pydantic v2, immutable where practical (`frozen=True`), with `model_config =
ConfigDict(extra="forbid")`.

```python
PeriodId = str                # "2026-06"

class PropertyRecord(BaseModel):
    id: str                   # "default" | "waypointe-ah-lp" | ...
    pm_name: str | None       # exact "Property:" value in the PM system, if any

class Property(BaseModel):
    id: str; name: str; folder: str
    property_manager: str     # pm id
    owning_entity: str
    records: list[PropertyRecord]   # order = output order

class SourceDocument(BaseModel):
    role: str                 # "pm_source" | "cornerstone_balance_sheet" | ...
    schema_id: str
    path: Path                # local path after fetch
    sha256: str
    page_count: int
    has_text_layer: bool      # true if ≥ 90 % of pages yield non-trivial text

class Orientation(StrEnum):
    UPRIGHT = "upright"; ROT_90_CW = "rotated_90_cw"; ROT_90_CCW = "rotated_90_ccw"; ROT_180 = "rotated_180"

class PageClassification(BaseModel):
    doc_role: str
    page: int                 # 1-based
    section_id: str           # a schema section id, or "unknown"
    is_continuation: bool
    record_qualifier: str | None
    orientation: Orientation
    confidence: float         # 0..1
    evidence: str             # one sentence from the model
    footer_label: str | None  # from footer_check, if a text layer exists
    footer_agrees: bool | None
    classifier: str           # "anthropic:<model>:<prompt_version>" | "golden"

class ResolvedSection(BaseModel):
    doc_role: str
    section_id: str
    record_id: str | None     # mapped from record_qualifier via properties.yaml
    pages: list[int]          # 1-based, contiguous, in document order
    orientation_fixes: dict[int, Orientation]

class PlanItem(BaseModel):
    output_page: int
    doc_role: str
    source_page: int
    section_id: str
    record_id: str | None
    transforms: list[str]     # ["copy"] | ["ocr", "rotate:90"] ...
    bookmark: str | None      # set on the first page of each section

class BuildStatus(StrEnum):
    BUILT = "built"; NEEDS_REVIEW = "needs_review"; FAILED = "failed"

class BuildManifest(BaseModel):   # full schema in section 10
    ...
```

---

## 4. Configuration formats

### 4.1 Source schema (`config/schemas/<schema_id>.yaml`)

Field reference. Required unless marked optional.

| Field | Meaning |
|---|---|
| `schema_id` | unique id, kebab-case |
| `version` | integer; bump on any change to `sections` |
| `producer`, `system` | documentation |
| `text_layer` | `always` \| `never` \| `sometimes` — drives OCR (section 6.2) |
| `fingerprint.description` | prose the classifier prompt includes |
| `fingerprint.footer_regex` | optional; enables `footer_check` (section 7.4) |
| `fingerprint.page_size_hint`, `fingerprint.ocr_quality_note` | optional; documentation, included in the classifier prompt |
| `record_scope.header_regex` | optional; regex with one capture group that extracts the `Property:` value from page text |
| `sections[]` | ordered list; order is informational only |
| `sections[].id` | snake_case, unique within the schema |
| `sections[].semantic` | cross-manager tag from the controlled list in section 4.4 |
| `sections[].cardinality` | `one` \| `per_record` |
| `sections[].typical_pages` | string or integer, documentation and a soft sanity check |
| `sections[].optional` | optional, default false. A required section absent from a source → `NEEDS_REVIEW` (`missing_required`), unless the output definition lists it in `drop` (then absence is fine) |
| `sections[].not_in_standard_export` | optional, documentation |
| `sections[].description`, `visual_cues[]`, `text_cues[]` | **These are the classifier's label definitions.** Keep them visually precise |
| `sections[].footer_label` | optional; exact footer report name for `footer_check` |
| `sections[].continuation_note` | optional; appended to the prompt for that section |

Validation (`crr validate-config`): ids unique; `semantic` in controlled list; `cardinality`
valid; at least one of `visual_cues`/`text_cues`; every `footer_label` distinct within a schema.

### 4.2 Output definition (`config/outputs/<output_id>.yaml`)

| Field | Meaning |
|---|---|
| `output_id`, `version`, `property_manager` | as above |
| `title_template` | Python format string; variables `property`, `period`, `period_label`, `owning_entity` |
| `sources` | map alias → `{schema, role, required?}`; `required` defaults true |
| `flow[]` | ordered flow items (below) |
| `unmapped_policy` | only `explicit_drop` is implemented in v1 |
| `drop[]` | addresses of PM sections that must be discarded |
| `transforms.ocr_if_no_text` | run OCR on documents whose `has_text_layer` is false |
| `transforms.autorotate` | apply `orientation_fixes` when composing |
| `transforms.add_bookmarks` | write a PDF outline entry per section |

A **flow item** is one of:

```yaml
- {address: "<address>", bookmark: "<template>", required: <bool, default true>, order: source}
- for_each_record: [ <flow items whose addresses contain "{record}"> ]
```

`order` is only meaningful with `section_ref = "*"`; `source` is the only value in v1 and the
default. A required Cornerstone source file that is absent → `NEEDS_REVIEW` (`missing_required`);
an optional one is recorded in the manifest and skipped.

`address: "pm:*"` with `order: source` expands to every section found in the PM source, in the
order of their first page. Sections listed in `drop` are excluded from the expansion.

**Invariant (enforced at build time):** every section the classifier found in the PM source must
be consumed by `flow` or listed in `drop`. Anything else → `NEEDS_REVIEW` with reason
`unmapped_section`.

### 4.3 Property registry (`config/properties.yaml`)

See the file; it is self-describing. Folder names are contractual — they must match the bundle
and the Drive layout byte for byte.

### 4.4 Controlled `semantic` vocabulary

`balance_sheet`, `income_statement`, `budget_variance`, `owner_statement`, `rent_roll`,
`occupancy`, `delinquency`, `general_ledger`, `trial_balance`, `distribution_schedule`,
`narrative`. Add to this list by amending this section.

---

## 5. Address grammar

```
address     := source_alias ":" section_ref [ "@" record ] [ "#" occurrence ]
source_alias:= identifier                     # key in output.sources
section_ref := section_id | "*"
record      := record_id | "{record}"         # "{record}" only inside for_each_record
occurrence  := integer ≥ 1                    # disambiguates repeated one-cardinality sections
identifier  := [A-Za-z0-9_-]+                 # section_id, record_id and source_alias all use this
```

Resolution rules (`crr.resolve`):

1. `source:section` on a `cardinality: one` section → exactly one `ResolvedSection`, else error
   `ambiguous_section` (more than one) or `missing_section` (zero, unless the flow item or the
   schema marks it optional).
2. `source:section` on a `per_record` section **without** `@record` → all records, in
   `properties.yaml` record order. Records missing from the source are skipped silently only when
   the flow item is `required: false`; otherwise `missing_record`.
3. `source:section@record` → the one instance whose `record_qualifier` maps to that record id.
   Mapping is exact string match on `pm_name` after whitespace normalisation, case-insensitive.
   **For a property with exactly one record, a `record_qualifier` that is null *or* matches that
   record's `pm_name` maps to that record's id.** (Single-record sources often print no
   `Property:` header, and golden labels store `record: null` for them.) For a multi-record
   property a null qualifier on a `per_record` section is a review reason (`unresolved_record`).
4. `source:*` → every resolved section in source order, minus `drop`.
5. `#n` selects the n-th occurrence in document order and is only legal on `cardinality: one`
   sections that the segmenter found more than once (a data-quality escape hatch, not a normal path).

Addresses are parsed by a small hand-written parser with tests for every production above.

Resolver outcomes map onto the review codes in §6.8: `ambiguous_section` → `cardinality_violation`;
`missing_section` and `missing_record` on a required item → `missing_required`; an unmapped
qualifier → `unresolved_record`.

---

## 6. Pipeline

`crr build --period 2026-06 [--property <id>] [--classifier anthropic|golden] [--dry-run]`

For each property in scope, in sequence (properties are independent; documents within a property may be classified in parallel per §7.3):

```
fetch → preprocess → classify → segment → resolve → plan → compose → manifest → review → publish
```

Each stage is a pure function of its inputs plus the settings object, and writes its artefacts to
`work/<period>/<property_id>/` so a failed build can be inspected and resumed.

### 6.1 Fetch (`crr.repository`)

```python
class SourceRepository(Protocol):
    def list_periods(self, property: Property) -> list[PeriodId]: ...
    def fetch_inputs(self, property: Property, period: PeriodId, dest: Path) -> list[SourceDocument]: ...
    def publish(self, property: Property, period: PeriodId, files: list[Path], status: BuildStatus) -> None: ...
```

- `LocalFsRepository(root, publish_root=root)` — reads
  `<root>/<pm.folder>/<property.folder>/<period folder>/inputs/`, publishes the same layout
  under `publish_root` into `.../output/` (or `.../review/` when status is `NEEDS_REVIEW`).
  `publish_root` defaults to `root`, but the CLI sets it from `CRR_PUBLISH_ROOT`, which itself
  defaults to `<work_dir>/published`: the local repository root is normally the June bundle,
  and the bundle is a read-only fixture (D-08). Point `CRR_PUBLISH_ROOT` at the repository root
  to publish beside the inputs.
- `GoogleDriveRepository(root_folder_id, service_account_json)` — identical layout on Drive.
  Uses `google-api-python-client` with a service account; lists by folder name; downloads to
  `dest`; uploads outputs with `supportsAllDrives=True`. Never deletes. Never overwrites: a
  second publish for the same period writes `<name> (build N).pdf`.

Input files are matched by the exact filenames in `properties.yaml`. A PM source file that is
missing is a hard failure for that property; a missing optional Cornerstone file is recorded.

### 6.2 Preprocess (`crr.preprocess`)

1. **Text layer probe**: `has_text_layer` = pages with ≥ 40 non-whitespace characters / page_count ≥ 0.9.
2. **OCR** (when `transforms.ocr_if_no_text` and not `has_text_layer`):
   `ocrmypdf --skip-text --rotate-pages --optimize 1 --output-type pdf in.pdf out.pdf`.
   The OCR'd file replaces the source for all later stages *and* is what gets composed, so the
   published package is searchable. Record the ocrmypdf version and whether `--rotate-pages`
   changed any page in the manifest. (`--rotate-pages` is a first pass at orientation; the
   classifier's orientation label is authoritative and the composer applies any remaining fix.)
3. **Render**: `pypdfium2`, 150 DPI, RGB, PNG, one file per page in `work/.../pages/`. Long edge
   capped at 1568 px (Anthropic's resize threshold) so the model sees exactly what is stored.
4. **Text**: `pypdf` `extract_text()` per page, whitespace-normalised, capped at 6 000 characters.

### 6.3 Classify (`crr.classify`) — see section 7.

Every input document is classified, including the three single-page Cornerstone files. That costs
three extra calls per property and buys a uniform pipeline plus a check that each file is what its
name claims (a mis-filed PDF surfaces as `unknown` or a wrong section, not as a wrong page in an
investor package).

### 6.4 Segment (`crr.segment`)

Group consecutive `PageClassification`s into `ResolvedSection`s:

- A new section starts when `section_id` changes, **or** `record_qualifier` changes, **or**
  `is_continuation` is false while the previous page had the same `section_id` (two back-to-back
  instances).
- A continuation page whose `record_qualifier` is null inherits the previous page's qualifier
  (footer-only continuation pages carry no `Property:` header).
- Pages labelled `unknown` are never merged into a neighbour. Each is its own review item.
- After grouping, validate against the schema: a `cardinality: one` section appearing more than
  once, or a required section absent, is recorded as a warning that the review gate evaluates.

### 6.5 Resolve and plan (`crr.resolve`)

Expand `flow` into `PlanItem`s using the grammar in section 5. Assign bookmarks: the flow item's
`bookmark` template rendered with `record_name`, `section_title` (schema section id humanised:
`cash_flow_12_month` → "Cash Flow 12 Month", overridable by an optional `title` on the schema
section), `property`, `period_label`. Compute the transform list per page:
`copy`, plus `rotate:<deg>` when `autorotate` and the page's orientation ≠ upright, plus `ocr`
(informational — OCR already happened at document level). Orientation is the direction the
*content* is currently turned; the rotation applied is what brings it upright (pypdf's
`rotate(n)` turns the page clockwise):

| classifier orientation | meaning | `rotate:` |
|---|---|---|
| `rotated_90_cw` | content reads top-to-bottom down the right edge | 270 |
| `rotated_90_ccw` | content reads bottom-to-top up the left edge | 90 |
| `rotated_180` | upside down | 180 |

`record_name` renders as the record's `pm_name`; for a property with a single record the
bookmark template's ` - {record_name}` suffix is dropped entirely.

### 6.6 Compose (`crr.compose`)

`pypdf.PdfWriter`. For each `PlanItem`: `add_page(reader.pages[i-1])`, apply
`page.rotate(deg)` for rotation fixes, preserve the source page's mediabox. Outline entries at
each section's first page. Metadata: `/Title` from `title_template`, `/Producer`
`Cornerstone Report Runner <version>`, `/CreationDate` now (UTC). Output filename:
`"{property.name} - Investor Report - {period_label}.pdf"`.

The composer never reads a file under `reference/` in the bundle. Enforce with a test.

### 6.7 Manifest (`crr.manifest`) — see section 10.

### 6.8 Review gate (`crr.review`)

The build is `NEEDS_REVIEW` (never silently `BUILT`) when any of:

| Reason code | Condition |
|---|---|
| `unknown_page` | any page classified `unknown` |
| `low_confidence` | any page with confidence < `settings.min_confidence` (default 0.85) |
| `footer_disagrees` | `footer_agrees is False` on any page |
| `unmapped_section` | a found section is neither in `flow` nor `drop` |
| `missing_required` | a required flow item resolved to nothing, or a required source file is absent |
| `unresolved_record` | a `per_record` section on a multi-record property whose qualifier maps to no record |
| `cardinality_violation` | a `one` section found more than once and no `#n` in the flow |
| `page_count_drift` | PM source page count differs from the last built period for this property by more than 50 % (only when a prior manifest exists) |

`FAILED` is reserved for exceptions: unreadable PDF, missing PM source, API errors after retries.

Exit codes: 0 all `BUILT`; 2 any `NEEDS_REVIEW`; 1 any `FAILED`.

### 6.9 Publish

`BUILT` → `output/`; `NEEDS_REVIEW` → `review/` with the manifest and a `REVIEW.md` summarising
the reasons in plain language; `FAILED` → nothing published, manifest written to `work/`.

---

## 7. Classifier

### 7.1 Interface

```python
class Classifier(Protocol):
    name: str
    def classify(self, doc: SourceDocument, schema: SourceSchema, pages: list[PageInput]) -> list[PageClassification]: ...

@dataclass
class PageInput:
    page: int
    image_path: Path
    text: str | None          # extracted or OCR text; None when neither exists
```

Implementations:

- `AnthropicClassifier` — the production path (7.2–7.3).
- `GoldenClassifier` — returns labels from `eval/golden/`. Lets the entire pipeline run
  end-to-end with no API key, and is the composer's regression fixture.
- `FooterCheck` — not a classifier; a post-processor that fills `footer_label` / `footer_agrees`
  from page text when the schema has `footer_regex` (7.4).

### 7.2 Anthropic classifier — call structure

One request per page, sequential per document (prior-page context is a dependency). Model from
`settings.model` (default `claude-opus-5`; pin a dated snapshot if the API lists one and record
the exact id in the manifest). `max_tokens=400`.

`temperature` is **not sent**: it is rejected with a 400 on `claude-opus-5` (and on every model
in that family), so the v1 build cannot set `temperature=0` as earlier drafts of this section
said. Determinism comes instead from the forced tool with a closed `enum` on `section_id` and
`strict: true` on the tool schema. Thinking is left at the model's default (adaptive) and depth
is controlled with `output_config.effort`, which `settings.classifier_effort` sets to `low`:
classifying one page image against a fixed catalogue is a perceptual call, not a reasoning
problem, and disabling thinking outright on this model family has its own failure modes.

**Cached prefix (1-hour TTL, identical for every page of a document).** The Messages API's
`system` field carries text blocks only, so this prefix spans two places: the instruction block
(items 1–3, 5) is the `system` field, and the exemplar images (item 4) are the leading blocks of
the user turn. Each carries its own `cache_control` breakpoint; both are per-document constants,
so pages 2..N read both from cache.

1. Role: page classifier for property-management financial reports; label the page against the
   supplied schema; never invent sections; prefer `unknown` to guessing.
2. The schema's `fingerprint.description` and `record_scope.description`.
3. The section catalogue: for each section — id, cardinality, typical pages, description, visual
   cues, text cues, continuation note. Verbatim from YAML.
4. **Exemplars**: for each section, up to two labelled page images drawn from
   `eval/golden` for a *different* property of the same manager when one exists, otherwise the
   same property. Each exemplar is an image block followed by a one-line caption
   `"Exemplar: section_id=<id>, continuation=<bool>"`. (Exemplars from the property under test
   are excluded in eval runs to avoid leakage — `settings.exemplar_policy`.)
5. Rules: one label per page; continuation means "same section as the previous page, no new
   title block"; a page with only a footer and no body is a continuation of the previous page;
   record_qualifier must be copied exactly from a `Property:` header or be null (the segmenter
   inherits the previous page's qualifier for null continuation pages, so do not guess one);
   report orientation of the *content* (text reading direction), not the page box.

Mark the last block of each cached prefix with `cache_control: {"type": "ephemeral", "ttl":
"1h"}`. The exemplar images are cached; the per-page image and text are not.

**User turn (uncached):**

```
Previous page: section_id=<id or "none">, continuation=<bool>, record_qualifier=<value or null>
Page <n> of <N> of document role <role>.
[image block: this page]
Extracted text (may be OCR, may be empty):
<text, ≤ 6000 chars>
```

**Tool (forced via `tool_choice`):**

```json
{
  "name": "classify_page",
  "input_schema": {
    "type": "object",
    "properties": {
      "section_id":        {"type": "string", "enum": ["<every schema section id>", "unknown"]},
      "is_continuation":   {"type": "boolean"},
      "record_qualifier":  {"type": ["string", "null"]},
      "orientation":       {"type": "string", "enum": ["upright","rotated_90_cw","rotated_90_ccw","rotated_180"]},
      "confidence":        {"type": "number", "minimum": 0, "maximum": 1},
      "evidence":          {"type": "string", "maxLength": 300}
    },
    "required": ["section_id","is_continuation","record_qualifier","orientation","confidence","evidence"]
  }
}
```

Parse the tool input into `PageClassification` via pydantic; a validation failure is retried once
with the validation error appended to the user turn, then recorded as `unknown` with
`evidence="schema_violation"`. A response with `stop_reason: "refusal"` is treated the same way:
a safety decline is not a label, so the page becomes `unknown` and the build goes to review
(D-12) rather than being retried into a guess.

### 7.3 Retries, limits, cost

- `anthropic` SDK with `max_retries=4`; additionally catch `RateLimitError`/`APIStatusError ≥ 500`
  and back off 2→4→8→16 s.
- Record per call: input tokens, cache read tokens, cache write tokens, output tokens, latency.
  Sum into the manifest (`cost.tokens`) and estimate dollars from a price table in `settings`.
- Concurrency: documents may be classified in parallel (`settings.max_parallel_docs`, default 2);
  pages within a document are sequential.

### 7.4 Footer check

For schemas with `fingerprint.footer_regex`: extract the footer line from page text (the last
line matching the regex, or the line immediately before it when the regex matches only the vendor
string), then choose the **longest `footer_label` that is a case-insensitive prefix** of that
line ("Delinquency" matches "Delinquency (Detail)"; "Rent Roll - Bank" beats "Rent Roll"). Set
`footer_label`; set
`footer_agrees = (matched section id == classification.section_id)` when a match exists, else
`None`. Disagreement is a review reason, not an override (D-05).

### 7.5 Prompt versioning

Prompts live in `src/crr/classify/prompts/<schema_id>/v<N>.md` (Jinja2). `prompt_version` is
recorded per page and in the manifest. Changing a prompt requires re-running `crr eval` and
recording the result in `PROGRESS.md`.

---

## 8. Eval harness

`crr eval --classifier anthropic [--pm <id>] [--property <id>] [--report eval/reports/<ts>.md]`

For every golden document: preprocess exactly as `build` does (OCR first for `text_layer:
never` schemas, so the classifier sees the same page images a build would), run the classifier
(with `exemplar_policy=exclude_same_property`), compare to golden labels, and report:

- per-manager and overall **page accuracy** (section_id exact match)
- **continuation accuracy**
- **record_qualifier accuracy** (Missoula only)
- **orientation accuracy** on pages where golden carries an `orientation` key (optional per
  page; refers to the page *as the classifier sees it*, i.e. after OCR's `--rotate-pages`)
- **section-boundary F1** after segmentation
- confusion pairs (which sections get mistaken for which)
- tokens and estimated cost

Thresholds (`settings.eval_thresholds`): page accuracy ≥ 0.98 per manager, boundary F1 ≥ 0.98.
`crr eval --gate` exits non-zero below threshold. CI runs `crr eval --classifier golden` (a
self-consistency check of the harness itself, free) on every PR; the real model eval runs on
demand and before any prompt or model change is merged.

`crr eval` writes `eval/reports/<timestamp>-<model>-<prompt_version>.md` and updates
`eval/reports/LATEST.md`. Reports are committed.

---

## 9. Build invariants (tests must cover each)

1. Every page of every input document appears in exactly one of: the plan, the drop list's
   resolved pages, or the review reasons. No page is silently lost.
2. The plan's page count equals the output PDF's page count.
3. The composer never opens a path under `reference/` or `target/`.
4. Building the same inputs twice with `GoldenClassifier` produces byte-identical outputs
   except for `/CreationDate`.
5. `crr build --classifier golden --period 2026-06` for all eight properties completes with
   status `BUILT` and matches `eval/golden/*.json → expected_output` — this is the composer's
   acceptance test. `expected_output` is a list, one entry per output page, in order:
   `{"output_page": n, "doc_role": "...", "section": "...", "record": "<record id or null>",
   "source_page": n}`; its length equals `expected_output_page_count`. It is generated in Phase 2
   from the output definitions, reviewed by hand, and then frozen.
6. Config validation rejects each of these six: unknown `semantic` tag; duplicate section id;
   invalid `cardinality`; duplicate `footer_label` within a schema; a flow address whose source
   alias is undeclared; a `drop` entry naming a section not in the schema.

---

## 10. Build manifest

`work/<period>/<property>/build-manifest.json`, also published beside the output.

```jsonc
{
  "manifest_version": 1,
  "runner_version": "0.1.0",
  "built_at": "2026-10-03T14:02:11Z",
  "status": "built" | "needs_review" | "failed",
  "review_reasons": [{"code": "low_confidence", "doc_role": "pm_source", "page": 5, "detail": "0.71"}],
  "property": {"id": "waypointe", "name": "WayPointe", "property_manager": "missoula", "owning_entity": "..."},
  "period": "2026-06",
  "config": {
    "schema": {"id": "rentmanager-missoula", "version": 1, "sha256": "..."},
    "output": {"id": "missoula-investor-report", "version": 1, "sha256": "..."},
    "properties_sha256": "..."
  },
  "classifier": {"name": "anthropic", "model": "claude-opus-5", "prompt_version": "v1", "temperature": 0},
  "inputs": [{"role": "pm_source", "file": "...", "sha256": "...", "pages": 16, "has_text_layer": true, "ocr_applied": false}],
  "classifications": [ /* one PageClassification per input page */ ],
  "sections": [ /* ResolvedSection[] */ ],
  "dropped": [{"section_id": "general_ledger", "pages": [11]}],
  "plan": [ /* PlanItem[] */ ],
  "output": {"file": "WayPointe - Investor Report - June 2026.pdf", "sha256": "...", "pages": 10},
  "cost": {"tokens": {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}, "usd_estimate": 0.0, "api_calls": 19},
  "timings_ms": {"fetch": 0, "preprocess": 0, "classify": 0, "compose": 0, "publish": 0}
}
```

A JSON Schema for this file is generated from the pydantic model and committed at
`src/crr/manifest/schema.json`.

---

## 11. CLI

```
crr validate-config                       # schemas, outputs, properties; exit 1 on error
crr inspect <pdf>                         # page sizes, text-layer probe, footer lines
crr classify <pdf> --schema <id> [--classifier anthropic|golden] [--out json]
crr build --period 2026-06 [--property <id>]... [--classifier anthropic|golden]
          [--repo local|gdrive] [--dry-run] [--work-dir work/]
crr eval [--classifier anthropic|golden] [--pm <id>] [--gate]
crr version
```

All commands log structured JSON lines to stderr (`structlog`), human summary to stdout.
Never log page text or image bytes. Log document sha256s, not paths, at INFO.

---

## 12. Settings (`src/crr/settings.py`, pydantic-settings, env prefix `CRR_`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | required for `--classifier anthropic` (no prefix; SDK convention) |
| `CRR_MODEL` | `claude-opus-5` | classifier model id |
| `CRR_MIN_CONFIDENCE` | `0.85` | review gate |
| `CRR_RENDER_DPI` | `150` | |
| `CRR_MAX_PARALLEL_DOCS` | `2` | |
| `CRR_BUNDLE_ROOT` | `data/bundle/2026-06` | local repository root for golden data |
| `CRR_REPO` | `local` | `local` \| `gdrive` |
| `GOOGLE_SERVICE_ACCOUNT_B64` | — | base64 of the service-account JSON (one line, env-safe); no prefix |
| `CRR_GDRIVE_ROOT_FOLDER_ID` | — | Drive folder that contains the `<PM>/` folders |
| `CRR_WORK_DIR` | `work/` | |
| `CRR_PUBLISH_ROOT` | `<work_dir>/published` | where the local repository publishes; keeps builds out of the read-only bundle |
| `CRR_EXEMPLAR_POLICY` | `exclude_same_property` | `exclude_same_property` \| `any` |
| `CRR_CLASSIFIER_EFFORT` | `low` | `output_config.effort` for the classifier: `low`\|`medium`\|`high`\|`xhigh`\|`max` |
| `CRR_EVAL_MIN_PAGE_ACCURACY` | `0.98` | per-manager gate |
| `CRR_EVAL_MIN_BOUNDARY_F1` | `0.98` | per-manager gate |
| `CRR_PRICE_TABLE_JSON` | built-in | override `{model: {input, cache_read, cache_write, output}}` USD per MTok |
| `CRR_OCRMYPDF_BIN` | `ocrmypdf` | ocrmypdf entry point; an escape hatch for environments where the distribution's entry point is broken or off PATH |

---

## 13. Google Drive layout

Mirror of the repo bundle, without `target/` and `reference/`:

```
<root folder>/
  Missoula Property Management/
    Fort Grounds/
      2026-09 September/
        inputs/
          05 PM Source - Missoula PM Baseline.pdf
          01 Cornerstone - Balance Sheet.pdf
          02 Cornerstone - Profit and Loss YTD Comparison.pdf
          03 Cornerstone - Investor Distribution Schedule.pdf
        output/                       ← written by the runner
          Fort Grounds - Investor Report - September 2026.pdf
          build-manifest.json
        review/                       ← written instead of output/ when NEEDS_REVIEW
  McCathren Management and Real Estate Services/ ...
  Cobalt Properties Group/ ...
```

A period is "ready to build" when `inputs/` contains the PM source file. `crr build --period X`
with `--repo gdrive` skips properties whose `inputs/` is missing and reports them.

---

## 14. Hosting

**Container:** `python:3.12-slim` + `tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd ocrmypdf ghostscript`
+ `uv sync --frozen`. Entrypoint `crr`. **The image never contains `data/bundle/`** (tenant data);
in-container tests mount the checkout and set `CRR_BUNDLE_ROOT`. CI pushes
`ghcr.io/arcticbio/crr:build-v1` and `:sha-<short>` on every push to `build/v1`, `:latest` and
`:vX.Y.Z` on tags.

**Primary target — Azure Container Apps Job** (Phase 8, gated on Azure credentials):
scheduled trigger (cron, quarterly, also manual via `az containerapp job start`), secrets from
Key Vault (`ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_B64`), 2 vCPU / 4 GiB, timeout 3600 s.
Bicep in `infra/`; a `deploy.yml` workflow that needs `AZURE_CREDENTIALS`.

**Fallback host — GitHub Actions** (Phase 7, no extra credentials): `build-period.yml` with
`workflow_dispatch` inputs `period` and optional `property`, plus an optional cron. Secrets in
the repo. This runs the identical container. It is fully sufficient for a quarterly job and is
the path to use until Azure is provisioned.

---

## 15. Testing strategy

- `tests/unit` — pure logic: address parser, resolver, segmenter, config validation, composer
  with synthetic 1-page PDFs generated by `reportlab`, manifest schema. Must run in < 60 s
  without network.
- `tests/integration` (marker `api`) — one real classification per manager against a golden page;
  skipped when `ANTHROPIC_API_KEY` is unset.
- `tests/eval` — `crr eval --classifier golden` must be 100 % (harness self-consistency).
- Coverage target 85 % on `src/crr` excluding `google_drive.py` (mocked) and `cli.py`.

---

## 16. Security and data handling

- Input PDFs contain tenant names and financials. Never commit anything under `work/`. Never
  log page text. Never send page images anywhere except the configured Anthropic endpoint.
- Keys only via environment. `.env` is git-ignored. The Drive service account has access to the
  one shared root folder and nothing else.
- The repo holds the June 2026 golden bundle only. Future periods live in Drive; the repo is the
  test fixture, not the archive (D-08).

---

## 17. Non-goals for v1

- Extracting numbers from the reports, reconciling figures, or any financial validation.
- Editing page content (stamping, redaction, watermarking).
- Multi-period comparison or trend output.
- A web UI. The manifest and `REVIEW.md` are the review surface.
- Reproducing published-package features that have no source (D-03).
