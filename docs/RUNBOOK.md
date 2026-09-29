# Runbook — operating the Cornerstone Report Runner

How the system runs day to day, what the people who upload files and the people who collect
reports need to know, what to do when something is held or needs review, and how to change the
system when the inputs change. `docs/SPEC.md` says how the system works (continuous intake is
§18); this file says how to work it.

## Contents

- One-time setup: [credentials](SETUP-CREDENTIALS.md) · [Google Drive](SETUP-GOOGLE-DRIVE.md) · Azure [by CLI](SETUP-AZURE.md) or [in the portal](SETUP-AZURE-PORTAL.md)
- [How it works](#how-it-works)
- [For uploaders — one page](#for-uploaders--one-page)
- [For reviewers — reading the status](#for-reviewers--reading-the-status)
- [The folders in Drive](#the-folders-in-drive)
- [Running it on demand from GitHub Actions](#running-it-on-demand-from-github-actions)
- [Running it on Azure](#running-it-on-azure)
- [Failure modes and what to do about them](#failure-modes-and-what-to-do-about-them)
- [Adding a property](#adding-a-property)
- [Adding a property manager](#adding-a-property-manager)
- [Changing a prompt](#changing-a-prompt)
- [When a model is deprecated](#when-a-model-is-deprecated)

---

## How it works

Nobody starts a build. Every 30 minutes `crr reconcile` looks at every property's open months in
Drive. For each one it asks: is every required file here, has nothing changed for an hour, and
does the newest report already reflect exactly these files? When the answers are yes, yes, no,
it builds the next version and writes it into that month's `output/` folder beside the earlier
ones. Whatever the answer, it rewrites one status file whose **name** says where things stand.

- **Each property is built as soon as its own files are ready**, independently of the others.
- **A file changed after a build produces a new version.** Code and config changes do not; a
  forced rebuild does ([below](#running-it-on-demand-from-github-actions)).
- **Release is not part of the system.** It produces reports for people to review and send.
- **A month is watched until 42 days after it ends** (September → 11 November), then closed.

---

## For uploaders — one page

*Written to be forwarded as it is to anyone asked to put a file in Drive.*

1. Open the shared drive, then the **property manager**, then the **property**, then the
   **month the report covers** — for example `Fort Grounds › 2026-09 September`. Quarterly
   reports go in the quarter's last month (September for July–September).
2. Inside are numbered folders, one per document:

   ```
   1 - Property Manager Report
   2 - Balance Sheet
   3 - Profit and Loss
   4 - Distribution Schedule      (only for properties that use one)
   output                         (the finished reports — don't put anything here)
   ```

3. **Put the PDF in the folder with its name.** Any filename is fine. One document per folder.
4. **To replace a file, upload the new one into the same folder.** You do not need to delete the
   old one: the newest upload is used, and the older one is renamed `SUPERSEDED - …`.
5. **To go back to an older file, delete the newer one.** The older one is used again.
6. That is all. A report is built about an hour after the last upload. Open `output/` to see
   the status file, whose name says what is happening.

Only PDFs are used. Photos, Word or Excel files are ignored (and the status says so). If a PDF
is password-protected, the status will say that too.

---

## For reviewers — reading the status

Each month's `output/` holds the reports — `Fort Grounds - Investor Report - September 2026 -
v2.pdf` and every earlier version — and **one** status file. Read its name first:

| Status file name | What it means | What to do |
|---|---|---|
| `STATUS - Built v2 (current).txt` | v2 was built from exactly the files now in the folders | Collect v2 |
| `STATUS - Needs review (v2).txt` | v2 was built, but something was ambiguous and the system declined to guess | Read `REVIEW - v2.md`, check the pages it names — [below](#handling-a-review) |
| `STATUS - Waiting for Balance Sheet, Profit and Loss.txt` | a required document has not arrived | Nothing, or chase whoever owes it |
| `STATUS - Waiting for uploads to settle.txt` | something was uploaded in the last hour | Nothing; it builds on its own |
| `STATUS - Ready - building on the next run.txt` | everything is here and settled; the last run was busy and ran out of time | Nothing; the next run, within 30 minutes, builds it |
| `STATUS - Held - Balance Sheet cannot be opened.txt` | a file is not a readable PDF, or is password-protected | Ask for a readable PDF in that folder |
| `STATUS - Held - would cost about $4.10, over the $3.00 limit.txt` | a file is far longer than it should be — usually the wrong document | Check each folder holds the right file |
| `STATUS - Built v2 - newer files waiting.txt` | v2 stands; newer files are waiting (missing or settling) | v2 is still usable; the next version is coming |
| `STATUS - Built v2 - newer files held.txt` | v2 stands; a newer file is held (see the body) | As for *Held* above |
| `STATUS - Built v2 - newer files ready, building next run.txt` | v2 stands; the newer files are ready and the next run builds them | v2 is still usable; the next version comes within 30 minutes |
| `STATUS - Failed (attempt 1 of 3), will retry.txt` | the build raised an error; it retries every 30 minutes | Nothing yet |
| `STATUS - Failed 3 times, stopped retrying.txt` | it failed three times on the same files | See [failure modes](#failure-modes-and-what-to-do-about-them) |
| `STATUS - Closed 2026-11-11 (v4 is final).txt` | the month is no longer watched; later changes are ignored | Nothing |
| `STATUS - Could not be checked - will retry.txt` | the last run could not read this month; nothing was built or changed, and the other months were checked as usual | Nothing if it clears within the hour; if it stays, see [failure modes](#failure-modes-and-what-to-do-about-them) |

The file's **body** lists, for each document, the file that was used and when it was uploaded,
anything set aside or ignored and why, and a version history — `v2 - … - Balance Sheet
replaced (uploaded …)`. Every version's manifest is in `output/manifests/`.

**At the top of the shared drive**, `_STATUS - All properties.txt` has one line per property
for its newest month with any files. Its last line, *Last checked …*, changes on every run: **if
it is more than an hour old, the job has stopped running** — see
[failure modes](#failure-modes-and-what-to-do-about-them).

### Handling a review

1. Read `REVIEW - v2.md`. It names each finding in plain language and lists the pages.
2. Open `… - v2 - NEEDS REVIEW.pdf` and look at those pages.
3. If the package is right, use it as it is. Nothing else is needed.
4. If a document in a numbered folder is wrong, upload the right one: the next version builds
   on its own.
5. If a page is labelled wrongly, the fix belongs in config, not in the PDF:
   - a page in the wrong section → sharpen that section's `visual_cues` or `description` in
     `config/schemas/<schema>.yaml`;
   - a section that should not be in the package → add it to `drop` in
     `config/outputs/<output>.yaml`;
   - a section that should be in the package → add it to `flow`.

   Run `crr eval` before merging the change, then force a rebuild of that month
   ([below](#running-it-on-demand-from-github-actions)) — a config change does not trigger one
   on its own.

---

## The folders in Drive

```
<shared drive root>/
  _STATUS - All properties.txt
  Missoula Property Management/
    Fort Grounds/
      2026-09 September/
        1 - Property Manager Report/     ← one PDF each, any filename
        2 - Balance Sheet/
        3 - Profit and Loss/
        4 - Distribution Schedule/
        output/
          STATUS - Built v2 (current).txt
          Fort Grounds - Investor Report - September 2026 - v1.pdf
          Fort Grounds - Investor Report - September 2026 - v2.pdf
          manifests/   v1.json  v2.json  state.json
  McCathren Management and Real Estate Services/ …
  Cobalt Properties Group/ …
```

- **The system creates the folders**: the current month and the next one, for every property,
  on every run. Nobody needs to prepare a period. A quarterly property simply leaves two months
  in three empty, and an empty month shows no status.
- **Manager and property folder names are contractual**: they must match `config/properties.yaml`.
  The numbered folder names come from `component_folders` in the same file.
- **Which documents a property needs** comes from its manager's output definition —
  `required: false` makes a document optional, and the report is built without it. A property
  can override that under `components:` in `config/properties.yaml`, e.g.
  `components: {cornerstone_distribution_schedule: not_used}` — a `not_used` document gets no
  folder at all.
- **Nothing a person put there is deleted, moved or overwritten.** The only change the system
  makes to anyone's file is the `SUPERSEDED - ` prefix, added and removed as the newest upload
  changes. Its own files — the status, `state.json`, the root summary — are rewritten in place.
- The v1 `inputs/` folders of earlier periods are ignored by `reconcile`; `crr build` still
  reads them.
- **Two system files sit at the root**: `_STATUS - All properties.txt`, the summary, and
  `_LEASE - reconcile run (do not edit).json`, which says which run is working, so that only
  one does at a time. Neither is anyone's to edit.
- **The shared drive's Trash collects one `.crr-preflight-…` file per run that builds.**
  Before its first build, such a run proves it can write by uploading a 3-byte file to the
  root and trashing it (SPEC §6.1, §18.9): the service account may trash files but not delete
  them. A run with nothing to build writes none. Drive deletes each for good after 30 days.
  Leave them there.

### Rehearsing without touching a real month

Never rehearse in the production root: every month in it is either closed or live, and a file
left in a live month is built into the next real version as if someone had uploaded it. The
shared drive holds a second root for this, beside the production one —
`Cornerstone Reports - REHEARSAL (test data, not for investors)`, folder id
`1eGZGlv5IGVd7OGM0-_2jcDfa56FkwAlz`. Point `CRR_GDRIVE_ROOT_FOLDER_ID` at it for the run
(locally, or in a scratch environment); the runner then prepares and builds there exactly as
it would in production. It holds the Phase 10 rehearsal, Fort Grounds / 2026-09 v1–v6, as it
stood; its record in git is `eval/reports/rehearsal-2026-09-fort-grounds/`.

### Access

The runner authenticates as a Google service account (`GOOGLE_SERVICE_ACCOUNT_B64`) and sees
only what is shared with it. The root must live in a **shared drive**, with the service account
as **Content manager** — step by step in [`SETUP-GOOGLE-DRIVE.md`](SETUP-GOOGLE-DRIVE.md).
Property managers can be given access to their own property folders for direct upload; the
CPA and Cornerstone representatives to the whole drive.

> **Why a shared drive.** A service account has no storage quota of its own, so in an
> Editor-shared *My Drive* folder it can create folders but fails the moment it writes a PDF
> (`403 storageQuotaExceeded`). `crr preflight --repo gdrive` writes one byte and removes it —
> the only check that proves a report could be delivered — and every `reconcile` and `build`
> runs it before spending anything. Background: `docs/QUESTIONS.md` → **B-09**.

---

## Running it on demand from GitHub Actions

Actions runs the identical container with the secrets already in the repository (D-13). It is
safe to run at any time, including while Azure is running: only one run works at a time. A run
that finds another holding the run lease prints `nothing done: another run (<host>) holds the
lease until <time>` and exits green — run it again after that time.

**Mind the half hour.** The lease covers every property, so a manual run that takes it in the
minutes before :00 or :30 makes that scheduled run stand down for *all* eight properties, and
their builds wait another 30 minutes (the live test of 2026-09-29 did this on purpose: a forced
build of one property at 08:59 held back five builds until 09:30). Start a manual run once the
half-hour run has finished — the root summary's *Last checked* line moves when it does — and
not in the last few minutes before the next one.

1. **Actions** → **Build a period** → **Run workflow**.
2. Fill in:

   | Input | What to put | Default |
   |---|---|---|
   | **command** | `reconcile` — do exactly what the schedule does, now · `reconcile --force` — also rebuild months whose files have *not* changed (after a config or code change) · `build` — the v1 command over the v1 `inputs/` layout | `reconcile` |
   | **period** | limit to one month, `2026-09`; blank for every open month (required for `build`) | blank |
   | **property** | limit to one property id; blank for all eight | blank |
   | **repo** | `gdrive` for real; `local` for a scratch run in the checkout | `gdrive` |
   | **classifier** | `anthropic` for real; `golden` replays the June labels | `anthropic` |
   | **image_tag** | which GHCR image to run | `build-v1` |

3. **Run workflow**. For `reconcile`, the log prints one line per month — its status headline —
   and the job is green unless the run itself could not proceed. Each month's real outcome is
   its status file in Drive.

`reconcile --force` still waits for required files and for uploads to settle; it only drops the
"nothing changed" and "failed three times" checks. It recomposes with the current code but
re-uses the page labels of every document that has not changed, so it costs almost nothing in
model calls; only a schema, prompt-version or model change re-classifies. Narrow it with
**period** and **property** anyway: every forced month becomes a new version.

### What the run needs to exist

| Kind | Name | Why |
|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | the classifier |
| Secret | `GOOGLE_SERVICE_ACCOUNT_B64` | Drive access, base64 of the service-account JSON |
| Variable | `CRR_GDRIVE_ROOT_FOLDER_ID` | the Drive folder holding the manager folders |

Set them under **Settings → Secrets and variables → Actions**.

---

## Running it on Azure

The Azure Container Apps Job is the production host. It runs **the same image** with the same
secrets: `crr reconcile --repo gdrive --classifier anthropic`, no other arguments. One-time
setup is [`SETUP-AZURE.md`](SETUP-AZURE.md).

**The schedule.** Every 30 minutes, `*/30 * * * *`: armed on 2026-09-29, when the owner
cleared PLAN Phase 10's STOP. A run with nothing to build, measured on Azure that day, is ~60 s
of process and ~100 s of execution: ~35 s of Azure starting the replica, then preflight, lease
and 16 open months checked. It does not grow with history. At 48 runs a day that is between $0
and ≈ $3.25 a month, depending on whether Azure bills the replica's start (A-15).

**To change the cadence**, change the `cronExpression` default in `infra/main.bicep`, merge, and
run *Deploy to Azure* with *Preview* unticked. Every deploy applies that default, including the
restore *Run the Azure job* performs, so a hand edit in the portal lasts only until the next
one. An hourly cron, `0 * * * *`, stays inside the free grant whatever Azure bills; after the
60-minute settle a build then waits up to an hour rather than half an hour. **To pause it**, run
*Deploy to Azure* with *Arm the schedule* unticked: the cron parks on 31 February, manual starts
still work, and *Run the Azure job* keeps it paused.

### Starting it by hand

**Actions → Run the Azure job → Run workflow.**

| Input | What it does | Cost |
|---|---|---|
| **version** | prints `crr 1.0.0` and exits | nothing |
| **validate-config** | lists 4 schemas, 3 output definitions, 8 properties | nothing |
| **scheduled (the job's own arguments, one reconcile run)** | one `reconcile` run, exactly what the schedule does | only what is ready to build |
| **wait_minutes** | how long to wait before giving up on the execution | `20` |

The first two set the job's arguments, start it, print its logs and then **put the scheduled
arguments back by re-deploying the template**; the third mutates nothing. `az containerapp job
update --args` cannot carry a multi-token argument list (A-13), which is why a forced rebuild
lives in *Build a period* instead.

### Reading the result

`reconcile` exits 0 unless the run itself could not proceed — bad config, missing credentials,
an unwritable drive — or a month could not be checked, so a **Failed** execution is a real
incident. A month that could not be checked never stops the others: they are all checked, the
root summary is written with the problem listed under *Could not be checked on this run*, and
only then does the run exit 1. Outcomes per month are in Drive, not in the exit code. Logs are
in the portal: the resource group → `crr-logs` → **Logs**. Every line is JSON, and page text,
tenant names and secrets are never among them.

---

## Failure modes and what to do about them

| What you see | What it means | What to do |
|---|---|---|
| `nothing done: another run (<host>) holds the lease until <time>` | Another run is working; only one works at a time | Nothing: run again after that time. A run that crashed leaves its lease to lapse at that time (30 minutes at most). |
| *Last checked* in `_STATUS - All properties.txt` is more than an hour old | Runs are not finishing | Look at the job's executions first. **Failed** ones: read their logs — the last lines say why. None at all: Actions → *Run the Azure job* → `version`; if that fails, the job or its credentials are broken (`SETUP-AZURE.md`). A `version` that succeeds proves only the job and its image, not a `reconcile` run: meanwhile *Build a period* → `reconcile` does the same work and prints the same error. |
| `Could not be checked - will retry` on a month, or under *Could not be checked on this run* in the root summary, for more than an hour | Reading that month raises on every run. The log line `intake.month_failed` names the property, the month and the error class | `ValidationError` almost always means `output/manifests/state.json` was edited or replaced: restore its previous version in Drive (*Manage versions*), or delete it — the next run then builds the month again as its next version. Otherwise it is usually Drive itself; the other months are unaffected meanwhile. |
| `Held - … cannot be opened` / `is password-protected` / `has no pages` | A file in that folder is not a usable PDF | Upload a readable PDF into the same folder; it becomes the newest and the build proceeds. |
| `Held - would cost about $X, over the $3.00 limit` | The pages to classify exceed the per-build ceiling (`CRR_MAX_BUILD_USD`) | Almost always a wrong or oversized document in a folder. Replace it. If the document really is that long, raise `CRR_MAX_BUILD_USD` for the job. |
| `Failed (attempt n of 3), will retry` | The build raised: API unavailable, OCR could not run, a PDF that opens but cannot be processed | Nothing yet — it retries every run. |
| `Failed 3 times, stopped retrying` | Three failures on the same files | Read the job logs for the error. If it was an outage that has passed, *Build a period* → `reconcile --force` with the period and property. A new upload also retries. |
| A report never appears though every file is there | Uploads keep arriving, or the month is closed | The status says which: *settle* or *Closed*. A closed month (42 days after month end) is never rebuilt — use `build` over a v1 `inputs/` folder if it truly must be. |
| *(v1 `crr build`)* `NOT READY` for a property in `crr inspect` | The PM source is not in `inputs/`, or its filename does not match | Check the filename against `config/properties.yaml` byte for byte — a renamed file is invisible to the runner. Otherwise chase the manager. |
| *(v1 `crr build`)* Job red, manifest says `PM source … is missing` | Same, discovered during the build | As above. The other properties still built. |
| Job red, `OcrError` | `ocrmypdf` or tesseract could not run in the container | Almost always the image, not the data. Re-run on a known-good `image_tag`; check the CI `image` job is green. Never "skip OCR to get it through" — a McCathren package without a text layer is not the product. |
| Job red, `PdfReadError` / `unreadable` | A source PDF is corrupt or truncated | Ask for a fresh export. Do not repair the PDF by hand: the manifest's sha256 is the audit trail. |
| *Needs review:* `unknown_page` | The classifier could not place a page | The manager probably added a report the schema does not know. Add a section to `config/schemas/<schema>.yaml`, or add the page's section to `drop` if it should not ship. |
| *Needs review:* `low_confidence` | A label was chosen but the model was unsure | Look at the page. If the label is right, sharpen that section's `visual_cues` so the next quarter is confident. If it is wrong, the same fix applies. |
| *Needs review:* `footer_disagrees` | The printed report name and the label disagree | One of them is wrong; look at the page. The footer never overrides the model (D-05), so this always comes to a human. |
| *Needs review:* `unmapped_section` | A section was found that is in neither `flow` nor `drop` | Decide which, and add it. The system will not guess. |
| *Needs review:* `missing_required` | A required flow item or source resolved to nothing | If the source is genuinely gone, mark that flow item `required: false`. If it should be there, chase it. |
| *Needs review:* `unresolved_record` | A `Property:` header matches no record | The manager renamed a property. Update `pm_name` in `config/properties.yaml`. |
| *Needs review:* `cardinality_violation` | A once-only section appeared twice | Look at the pages. If it is now legitimately two reports, change the section's `cardinality`, or address a specific instance with `#n` in the flow. |
| *Needs review:* `page_count_drift` | The export changed size by more than half | Usually a manager changing their export settings. Compare against the previous period's manifest before shipping. |

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
   If the property does not use a document its manager's output definition expects, say so:
   `components: {cornerstone_distribution_schedule: not_used}` (or `optional`, or `required`).
3. Merge. The next run creates its month folders in Drive — nobody prepares them.
4. Once its files are in, build just that property first: *Build a period* → `reconcile`, with
   **property** set to `new-property`.
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
`CRR_MODEL` (default `claude-opus-5-5`; `claude-opus-5` before 2026-09-26), and every manifest
records the exact model that produced its labels. The classifier chooses between a forced tool
call and `auto` from the model id (A-16), so a model that rejects forcing needs no code change;
it does need a row in the price table, or every cost estimate reads $0.

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
