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
