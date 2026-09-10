# Runbook — operating the Cornerstone Report Runner

How to run a quarterly build, what to do when one comes back for review, and how to change the
system when the inputs change. `docs/SPEC.md` says how the system works; this file says how to
work it.

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
address** — Editor, so it can write `output/` and `review/` — and nothing else. The account
needs no other access, and the runner never deletes or overwrites: a second publish of the same
name lands beside the first as `… (build 2).pdf`.

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
