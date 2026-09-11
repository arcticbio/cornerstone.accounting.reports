# Runbook — operating the Cornerstone Report Runner

How to run a quarterly build, what to do when one comes back for review, and how to change the
system when the inputs change. `docs/SPEC.md` says how the system works; this file says how to
work it.

## Contents

- One-time setup: [credentials](SETUP-CREDENTIALS.md) · Azure [by CLI](SETUP-AZURE.md) or [in the portal](SETUP-AZURE-PORTAL.md)
- [The quarterly checklist](#the-quarterly-checklist)
- [Preparing a period in Drive](#preparing-a-period-in-drive)
- [Running a build from GitHub Actions](#running-a-build-from-github-actions)
- [Failure modes and what to do about them](#failure-modes-and-what-to-do-about-them)
- [Adding a property](#adding-a-property)
- [Adding a property manager](#adding-a-property-manager)
- [Changing a prompt](#changing-a-prompt)
- [When a model is deprecated](#when-a-model-is-deprecated)

---

## The quarterly checklist

1. **Collect the inputs.** Each manager sends their monthly export; Cornerstone produces the
   three components per property. Drop them into each property's `inputs/` folder in Drive,
   named exactly as [Preparing a period in Drive](#preparing-a-period-in-drive) lists.
2. **Check the period is ready.** `uv run crr inspect --repo gdrive --period 2026-09`, or read
   the folders. Every property should say `ready`.
3. **Dispatch the build.** Actions → *Build a period* → **Run workflow**, with the period id.
   See [Running a build from GitHub Actions](#running-a-build-from-github-actions).
4. **Check the status.** Green with no annotation: done, packages are in `output/`. Green with
   a *Review needed* annotation: work the review queue. Red: read the failure below.
5. **Work the review queue.** For each package in `review/`, read `REVIEW.md`, look at the pages
   it names, then either move the package to `output/` or fix the config and re-run.
6. **Record what happened.** If a fix was needed, the config change goes through a PR with a
   fresh `crr eval` result in it. That is how the next quarter gets easier.

---

## Preparing a period in Drive

A build reads one folder per property per period. The runner never invents folders during a
build, so the folders have to exist before the inputs can be dropped in.

### The layout

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
        output/     ← the runner writes here when the build is clean
        review/     ← the runner writes here instead when something needs a human
```

**The names are contractual.** Manager folders, property folders and input filenames must match
`config/properties.yaml` byte for byte. A renamed folder does not produce a warning; it produces
a property with no inputs. Period folders are `YYYY-MM Month` — `2026-09 September`.

The three managers, and the PM source filename each one delivers:

| Manager folder | PM source filename |
|---|---|
| `Missoula Property Management` | `05 PM Source - Missoula PM Baseline.pdf` |
| `McCathren Management and Real Estate Services` | `05 PM Source - McCathren Baseline.pdf` |
| `Cobalt Properties Group` | `05 PM Source - Cobalt Baseline.pdf` |

The three Cornerstone components are named identically for every property:
`01 Cornerstone - Balance Sheet.pdf`, `02 Cornerstone - Profit and Loss YTD Comparison.pdf`,
`03 Cornerstone - Investor Distribution Schedule.pdf`.

### Creating the folders

Either create them by hand in the Drive UI, matching the layout above, or let the runner do it:

```bash
uv run python -c "
import os; from pathlib import Path
from crr.config import load_config
from crr.repository.drive_client import GoogleDriveApi
from crr.repository.google_drive import GoogleDriveRepository
bundle = load_config(Path('config'))
repo = GoogleDriveRepository(
    GoogleDriveApi.from_b64(os.environ['GOOGLE_SERVICE_ACCOUNT_B64']),
    os.environ['CRR_GDRIVE_ROOT_FOLDER_ID'], bundle.properties)
for entry in bundle.properties.properties:
    repo.ensure_period_skeleton(entry.to_domain(), '2026-09')
"
```

It creates folders only, never files, and is safe to re-run: an existing folder is reused.

### What "ready" means

A period is **ready to build** for a property when `inputs/` holds that manager's PM source
file. Everything else is optional in the mechanical sense:

- A missing Cornerstone component is recorded in the manifest and skipped. Timber Place has had
  no distribution schedule since June 2026, and that is not an error (D-06).
- A missing **PM source** is a hard failure for that property. The other seven still build.

Check what a period holds before you dispatch a build:

```bash
uv run crr inspect --repo gdrive --period 2026-09
```

```
period 2026-09 via gdrive
  fort-grounds         ready
  timber-place         ready       missing: cornerstone_distribution_schedule (optional)
  river-falls          NOT READY   missing: pm_source
  ...
6/8 propert(ies) ready to build
```

`NOT READY` means the PM source is absent — chase the manager, or check the filename.

### Access

The runner authenticates as a Google service account (`GOOGLE_SERVICE_ACCOUNT_B64`) and only
sees what has been shared with it. **Share the root folder with the service account's email
address** — Editor — and nothing else. The account needs no other access, and the runner never
deletes or overwrites: a second publish of the same name lands beside the first as
`… (build 2).pdf`.

> **Sharing alone is not enough to publish. The root folder must live in a shared drive.**
> A service account has no storage quota of its own, and a file written into someone's *My
> Drive* has to be owned by whoever uploaded it. So an Editor-shared My Drive folder lets the
> runner read inputs and create `inputs/`, `output/` and `review/` — folders cost no quota — and
> then fails the moment it writes a PDF:
>
> ```
> 403 storageQuotaExceeded: Service Accounts do not have storage quota.
> Leverage shared drives, or use OAuth delegation instead.
> ```
>
> Because folder creation succeeds, the setup looks correct until the first publish. Move the
> root folder into a **shared drive** and add the service account as **Content manager**: files
> there are owned by the drive rather than the uploader. No code change is needed — the client
> already sets `supportsAllDrives`. The alternative, domain-wide delegation, does need one. See
> `docs/QUESTIONS.md` → **B-09**.

---

## Running a build from GitHub Actions

Actions is the host (D-13): it runs the identical container the Azure job would, with the
secrets already in the repository, and nothing to provision.

### Dispatching a run

1. Open the repository on GitHub and click **Actions** in the top bar.
2. In the left-hand list of workflows, click **Build a period**.
3. A blue banner appears above the run list: *This workflow has a `workflow_dispatch` event
   trigger.* Click **Run workflow** on the right of it.
4. A small panel drops down with the branch selector and four inputs:

   | Input | What to put | Default |
   |---|---|---|
   | **period** | the period id, `2026-09` | — (required) |
   | **property** | one property id to build just that one; leave blank for all eight | blank |
   | **repo** | `gdrive` for a real run; `local` builds the June bundle in the checkout | `gdrive` |
   | **classifier** | `anthropic` for a real run; `golden` replays the June labels | `anthropic` |
   | **image_tag** | which GHCR image to run | `build-v1` |

5. Click the green **Run workflow** button. The run appears at the top of the list within a few
   seconds; click it, then click the **crr build** job to watch the log.

### Reading the result

The job's own status is the headline, and it follows the exit codes in SPEC §6.8:

- **Green tick** — every property built. The packages are in each property's `output/` folder in
  Drive, with `build-manifest.json` beside each one.
- **Green tick with a yellow annotation** at the top of the run, *"Review needed"* — at least one
  package went to `review/` instead. This is a normal outcome, not a failure: something was
  ambiguous and the system declined to guess (D-12).
- **Red cross** — at least one property failed outright: a missing PM source, an unreadable PDF,
  or the API unavailable after retries. Nothing was published for that property.

Every run uploads a **manifests-\<period\>** artifact — the link is at the bottom of the run
summary page, under *Artifacts*. It holds one `build-manifest.json` per property, plus a
`REVIEW.md` for any package that needs review. Download it to see what happened without opening
Drive.

### Handling the review queue

For each package in `review/`:

1. Read `REVIEW.md` next to it. It names each finding in plain language and lists the page.
2. Open the PDF beside it and look at those pages.
3. If the package is right, move it from `review/` to `output/` in Drive. Nothing else is needed.
4. If a page is wrong, the fix belongs in config, not in the PDF:
   - a page in the wrong section → sharpen that section's `visual_cues` or `description` in
     `config/schemas/<schema>.yaml`;
   - a section that should not be in the package → add it to `drop` in
     `config/outputs/<output>.yaml`;
   - a section that should be in the package → add it to `flow`.

   Then re-run `crr eval` before merging the change, and dispatch the build again. The runner
   never overwrites, so the second package lands as `… (build 2).pdf` beside the first.

### What the run needs to exist

| Kind | Name | Why |
|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | the classifier |
| Secret | `GOOGLE_SERVICE_ACCOUNT_B64` | Drive access, base64 of the service-account JSON |
| Variable | `CRR_GDRIVE_ROOT_FOLDER_ID` | the Drive folder holding the manager folders |

Set them under **Settings → Secrets and variables → Actions**: the two secrets on the
**Secrets** tab, the folder id on the **Variables** tab.

### The quarterly schedule

`build-period.yml` carries a commented `schedule:` block — `0 6 20 1,4,7,10 *`, which is 06:00
UTC on the 20th of January, April, July and October. Uncomment it once a period has been run by
hand and the review queue is understood. A scheduled run uses the workflow's default inputs, so
it builds every property from Drive with the real classifier.

---

## Failure modes and what to do about them

| What you see | What it means | What to do |
|---|---|---|
| `NOT READY` for a property in `crr inspect` | The PM source is not in `inputs/`, or its filename does not match | Check the filename against `config/properties.yaml` byte for byte — a renamed file is invisible to the runner. Otherwise chase the manager. |
| Job red, manifest says `PM source … is missing` | Same, discovered during the build | As above. The other properties still built. |
| Job red, `OcrError` | `ocrmypdf` or tesseract could not run in the container | Almost always the image, not the data. Re-run on a known-good `image_tag`; check the CI `image` job is green. Never "skip OCR to get it through" — a McCathren package without a text layer is not the product. |
| Job red, `PdfReadError` / `unreadable` | A source PDF is corrupt or truncated | Ask for a fresh export. Do not repair the PDF by hand: the manifest's sha256 is the audit trail. |
| Warning annotation, `unknown_page` | The classifier could not place a page | The manager probably added a report the schema does not know. Add a section to `config/schemas/<schema>.yaml`, or add the page's section to `drop` if it should not ship. |
| Warning, `low_confidence` | A label was chosen but the model was unsure | Look at the page. If the label is right, sharpen that section's `visual_cues` so the next quarter is confident. If it is wrong, the same fix applies. |
| Warning, `footer_disagrees` | The printed report name and the label disagree | One of them is wrong; look at the page. The footer never overrides the model (D-05), so this always comes to a human. |
| Warning, `unmapped_section` | A section was found that is in neither `flow` nor `drop` | Decide which, and add it. The system will not guess. |
| Warning, `missing_required` | A required flow item or source resolved to nothing | If the source is genuinely gone, mark that flow item `required: false`. If it should be there, chase it. |
| Warning, `unresolved_record` | A `Property:` header matches no record | The manager renamed a property. Update `pm_name` in `config/properties.yaml`. |
| Warning, `cardinality_violation` | A once-only section appeared twice | Look at the pages. If it is now legitimately two reports, change the section's `cardinality`, or address a specific instance with `#n` in the flow. |
| Warning, `page_count_drift` | The export changed size by more than half | Usually a manager changing their export settings. Compare against the previous period's manifest before shipping. |

**The general rule:** a review outcome is the system working (D-12). The remedy is almost always
a config change — a schema cue, a `flow` entry, a `drop` entry — never an edit to a PDF and
never a code change.

---

## Adding a property

A new property under an *existing* manager is config only.

1. Add it to `properties:` in `config/properties.yaml`:

   ```yaml
     - id: new-property                     # kebab-case, used everywhere
       name: New Property                   # appears in the output filename and title
       folder: "New Property"               # the Drive folder name, byte for byte
       property_manager: missoula           # an existing manager id
       owning_entity: New Property Homes LP
       records:
         - {id: default, pm_name: "New Property Apartments"}   # the PM system's name
   ```

   `pm_name` must match the `Property:` header the manager's reports print, after whitespace
   normalisation. Get it from a real export, not from a contract.

2. `uv run crr validate-config` — it will tell you if anything is inconsistent.
3. Create the Drive folders for the period ([Preparing a period](#preparing-a-period-in-drive)).
4. Build just that property first: dispatch with **property** set to `new-property`.
5. Expect a review outcome on the first run, and read it carefully. That is the system telling
   you what it does not yet know about this property.

A property with **two records** (like WayPointe) lists both under `records:`, in the order they
should appear in the output. Order there is output order (D-07).

---

## Adding a property manager

A new manager is a new schema, a new output definition, golden labels and an eval — but still no
code (D-02).

1. **Get one real export** and look at every page.
2. **Write `config/schemas/<schema_id>.yaml`.** One section per distinct report. The
   `description`, `visual_cues` and `text_cues` are the classifier's entire definition of that
   label — write them as you would describe the page to someone over the phone. Set
   `cardinality: per_record` for reports run once per property record, `one` otherwise. If the
   pages carry a footer naming the report, set `fingerprint.footer_regex` and a `footer_label`
   per section: that gives you a free cross-check on every page forever.
3. **Write `config/outputs/<output_id>.yaml`.** `sources` names the files; `flow` is the output
   order; every section the source can contain must be in `flow` or `drop`.
4. **Register the manager** in `property_managers:` in `config/properties.yaml`, with its folder
   name and PM source filename.
5. **Add a prompt directory:** `src/crr/classify/prompts/<schema_id>/v1.md` containing
   `{% include "_shared/system_body.md" %}`. Diverge from the shared body only when this
   manager needs something the others do not.
6. **Label a period by hand** into `eval/golden/<pm>/<property>.json` — every page of every
   document. This is the ground truth and the few-shot source; it is worth the hour.
7. **Run the eval:** `uv run crr eval --classifier anthropic --pm <pm_id>`. Below 0.98? Read the
   confusion pairs and sharpen the cues of the sections that get mixed up. Re-run.
8. **Build it:** `uv run crr build --period <p> --property <id> --classifier anthropic`, and
   compare the output against what the manager's package should look like.

---

## Changing a prompt

Prompts are versioned per schema: `src/crr/classify/prompts/<schema_id>/v<N>.md`.

1. Copy `v1.md` to `v2.md` and edit it.
2. Run the eval on both, on the same documents:

   ```bash
   uv run crr eval --classifier anthropic --pm missoula --report eval/reports/before.md
   # point the classifier at v2, then:
   uv run crr eval --classifier anthropic --pm missoula --report eval/reports/after.md
   ```

3. **Both reports go in the PR.** A prompt change without an eval is a guess, and the manifest
   records `prompt_version` for every page ever built — a change nobody measured is a change
   nobody can explain later.
4. Merge only if accuracy holds or improves for *every* manager the prompt touches.

The same rule applies to changing a schema's `visual_cues` or `description`: those are prompt
content, and `crr eval` is how you find out whether the change helped.

---

## When a model is deprecated

Anthropic announces model deprecations with a retirement date. The runner pins its model in
`CRR_MODEL` (default `claude-opus-5`), and every manifest records the exact model that produced
its labels.

1. **Set the new model in a branch:** `CRR_MODEL=<new-model>`.
2. **Run the full eval on both models** over all 31 golden documents, and put both reports in
   the PR. Page accuracy and boundary F1 per manager are the numbers that matter.
3. **If accuracy holds,** merge, and re-run the last built period with the new model to compare
   the manifests' page plans. They should be identical.
4. **If accuracy drops,** the fix is the prompt or the cues, not the gate. Iterate as in
   [Changing a prompt](#changing-a-prompt), and only lower a threshold with a written reason in
   `docs/DECISIONS.md`.
5. **Update the price table** if the new model prices differently — `CRR_PRICE_TABLE_JSON`
   overrides the built-in estimate without a code change.

Do this before the retirement date, not on it: a quarterly job that fails on a retired model
fails at the worst possible moment, three months after anyone last looked at it.
