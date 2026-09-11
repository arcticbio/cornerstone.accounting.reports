# Setting up Google Drive so the runner can publish

> **Done on this account on 2026-09-11**, and verified: `crr preflight --repo gdrive` passes and
> a real build published `Fort Grounds - Investor Report - June 2026.pdf` into `output/`. What
> follows is the procedure, kept for the next Drive root, the next environment, or whoever has
> to understand why it is arranged this way.

**Why this matters:** without it, everything else works — the runner reads inputs from Drive,
classifies, composes and produces correct packages — and it cannot put a single file back.

Budget **20 minutes**, almost all of it clicking in the Drive web UI. One optional step needs a
terminal, and it is the verification step at the end.

---

## The problem, in one paragraph

The runner signs in as a **service account** — a robot identity, not a person. A service account
has **no Google Drive storage of its own**. In Google Drive, a file in someone's *My Drive* must
be owned by whoever uploaded it, so when the robot tries to upload, Drive has nowhere to put the
file and refuses:

```
403 storageQuotaExceeded: Service Accounts do not have storage quota.
Leverage shared drives, or use OAuth delegation instead.
```

**Folders are exempt** — they take up no space — so the robot can happily create
`2026-09 September/inputs/` and the whole tree looks healthy. Nothing goes wrong until the first
*byte*. That is why this was not caught earlier, and it is why sharing the folder more
generously does not help: it is not a permissions problem. The runner already has
`canAddChildren: true` on the folder today, and still cannot write to it.

**The fix is to give the files an owner that is not a person.** That is exactly what a **shared
drive** is: files in a shared drive are owned by the *drive*, not by whoever uploaded them, so
the robot's lack of storage stops mattering.

---

## Before you start

| | |
|---|---|
| **You need** | Google **Workspace** (Business Standard or above). Shared drives do not exist on free/personal Google accounts. |
| **You need to be** | able to create a shared drive. If your admin has restricted this, see [If you cannot create a shared drive](#if-you-cannot-create-a-shared-drive). |
| **The robot's address** | `crr-runner@cornerstone-reports-508208.iam.gserviceaccount.com` — copy it now, you will paste it in Part 2. |
| **What exists today** | A **My Drive** folder named **Cornerstone Reports** (id in `CRR_GDRIVE_ROOT_FOLDER_ID`) containing 29 empty folders — all of them created by, and owned by, the runner. No input files are staged in Drive yet. |

> **A note on the robot's address.** It is long and ends in
> `.iam.gserviceaccount.com`. That is correct — it is not an email you can send mail to, but
> Drive treats it as a person for sharing purposes, which is what we want.

---

## What you will be doing

| Part | Where | Roughly |
|---|---|---|
| 1 | Google Drive | Create a shared drive | 3 min |
| 2 | Google Drive | Add the runner to it as **Content manager** | 3 min |
| 3 | Google Drive | Create a fresh `Cornerstone Reports` root inside it | 3 min |
| 4 | Wherever it is configured | Update `CRR_GDRIVE_ROOT_FOLDER_ID` | 5 min |
| 5 | A terminal | Verify with `crr preflight` | 2 min |

---

# Part 1 — Create the shared drive

1. Go to <https://drive.google.com> and sign in as the account that owns **Cornerstone
   Reports** today.
2. In the left sidebar, click **Shared drives**.
   - **Don't see it?** You are on a personal account, or your admin has turned shared drives
     off. Jump to [If you cannot create a shared drive](#if-you-cannot-create-a-shared-drive).
3. Click **+ New** (top left) — or right-click in the empty area and choose **New shared
   drive**.
4. Name it something that will still make sense to someone else in two years. **`Cornerstone
   Investor Reports`** is a reasonable choice. Click **Create**.

You now have an empty shared drive. It is a container that owns its own files — that is the
whole trick.

---

# Part 2 — Let the runner in

**Do this before moving anything**, so the robot has access the moment the files arrive.

1. Open the new shared drive.
2. Click its name at the top, then **Manage members**. (Or click the 👥 icon in the toolbar.)
3. Paste the robot's address into the **Add people** box:

   ```
   crr-runner@cornerstone-reports-508208.iam.gserviceaccount.com
   ```

4. Drive may show it as an unfamiliar address with no profile picture. That is expected — it is
   a robot. Select it.
5. **Set the role to `Content manager`.** This is the important part:

   | Role | |
   |---|---|
   | Viewer, Commenter | ✗ read only — the runner could fetch inputs but not publish |
   | Contributor | ⚠️ not tested here. Don't pick it; there is no upside. |
   | **Content manager** | ✅ **choose this** — verified end to end on this drive, 2026-09-11 |
   | Manager | also works, but additionally lets the robot change who has access. No reason to grant that. |

   > **Why not Manager, given it can do more?** Because Content manager is enough, and the
   > difference is the runner's ability to change the drive's membership. One thing does need
   > saying: in a shared drive, **only a Manager may permanently delete a file.** A Content
   > manager can trash. The runner is built for that — its preflight *trashes* its probe rather
   > than deleting it — so Content manager leaves nothing behind. (This was a real bug: the
   > first version used permanent delete and left one probe file per run on a correctly
   > configured drive.)

6. **Untick "Notify people"** if the option appears — nobody is going to read a robot's email.
7. Click **Send** / **Share**.

Check the member list now shows the `crr-runner@…` address with **Content manager** beside it.

---

# Part 3 — Give the runner a root inside the shared drive

> ### Don't try to move the existing folder. You can't, and you don't need to.
>
> The obvious move — drag `Cornerstone Reports` from My Drive into the shared drive — **fails**,
> and the reason is worth understanding because it is the same trap as the quota itself.
>
> Every folder under `Cornerstone Reports` was created by *the runner*, not by a person.
> `ensure_period_skeleton` makes the `<manager>/<property>/<period>/inputs/` tree, and folder
> creation is the one write a service account **can** do — folders consume no quota. So the
> robot owns them. **Drive will not let you move items you do not own**, and ownership cannot be
> transferred from a service account to a user in another domain.
>
> Checked on this Drive on 2026-09-11: **29 folders, 0 files, 0 bytes, all 29 owned by
> `crr-runner@…`.** The tree is empty scaffolding. There is nothing in it to preserve, so the
> answer is not to fight the move — it is to point the runner somewhere new.

## 3.1 Create a fresh root inside the shared drive

1. Open your new shared drive (**Shared drives** → **Cornerstone Investor Reports**).
2. Click **+ New** → **New folder**.
3. Name it **`Cornerstone Reports`** — the same name as before, so nothing else reads
   differently. It is a *different folder*; that is fine and intended.

Because it was created inside a shared drive, this folder is owned by the **drive**. So is
everything the runner ever puts in it. That is the whole fix.

## 3.2 Leave the old folder alone for now

The old My Drive `Cornerstone Reports` and its 29 empty folders are now unused. They are
harmless. Delete them once a real run has published successfully and you are confident — not
before, and there is no hurry.

> **If your tree is not empty** — you are reading this later and real input files are staged —
> then the files themselves are owned by whoever uploaded them, usually a person, and *those*
> can be moved. Move the **files** into the new tree (Drive lets you move items you own), and
> let the runner recreate the folders. The robot-owned folders stay behind either way.

---

# Part 4 — Update `CRR_GDRIVE_ROOT_FOLDER_ID`

The new folder is a new folder, so its id is **different**. This step is required, not a
formality.

1. Open the new **Cornerstone Reports** folder inside the shared drive.
2. Copy the id out of the browser address bar — everything after `/folders/`:

   ```
   https://drive.google.com/drive/folders/1AbCdEf...................
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^ this is the id
   ```

3. Set `CRR_GDRIVE_ROOT_FOLDER_ID` to it **everywhere it is configured**:

> **It is not a secret, and it is not in Key Vault.** A folder id is an opaque identifier that
> is useless without credentials, and `infra/main.bicep` reflects that: `ANTHROPIC_API_KEY` and
> `GOOGLE_SERVICE_ACCOUNT_B64` reach the container as `secretRef`s backed by the vault, while
> `CRR_GDRIVE_ROOT_FOLDER_ID` is a plain `value:` on a Bicep parameter. Putting it in the vault
> would hide it from the people checking their work without protecting anything.

| Where | How |
|---|---|
| **GitHub Actions** *(this is also how Azure gets it)* | repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → `CRR_GDRIVE_ROOT_FOLDER_ID` → **edit** → paste the new id → **Save**. Variables, not Secrets. |
| **Azure** | Nothing to set by hand. `deploy.yml` reads that same repository variable and passes it as the `gdriveRootFolderId` Bicep parameter, which becomes the job's `CRR_GDRIVE_ROOT_FOLDER_ID` environment variable. **Re-run the deploy workflow** after changing it: Actions → **Deploy to Azure** → **Run workflow**. Until you do, the deployed job keeps the old id. |
| **Claude Code** | the cloud environment's variables |
| **Your laptop** | `.env` |

Miss one and that host keeps failing against the old folder — and the symptom is confusing
precisely because the *others* will have started working.

> **In a hurry?** You can edit the value directly on the Container App Job in the portal
> (**Containers** → **Edit and deploy** → the container → **Environment variables**). It takes
> effect on the next execution — but the next run of `deploy.yml` overwrites it from the
> repository variable, so change the variable too or you will be debugging this twice.

---

# Part 5 — Verify

This is the only step that proves anything. Everything above can look right and still not work,
which is precisely how this problem stayed hidden.

```bash
uv run crr preflight --repo gdrive
```

**What you want to see:**

```
ok    gdrive accepted a test write, and it was cleaned up.
```

That is the runner writing one byte to the root folder and deleting it again — the exact
operation that was failing. If it passes, publishing works.

**If it still fails,** the message tells you which problem you have:

| Message contains | What it means | Fix |
|---|---|---|
| `storageQuotaExceeded` | the id still points at a **My Drive** folder | The most likely cause is Part 4: the variable was not updated, or was updated in one place and not another. Confirm the id in the address bar of the folder *inside the shared drive* matches the one the failing host is using. |
| `File not found` / `404` | the runner cannot see the folder at all | Part 2: the robot is not a member of the shared drive, or you added a different address. Check for a typo. |
| `insufficientFilePermissions` | the robot can read but not write | Part 2: the role is Viewer, Commenter or Contributor. Set it to **Content manager**. |
| `invalid_grant` / auth errors | the credentials are wrong or expired | Not this document's problem — see `SETUP-CREDENTIALS.md`. |

**Still stuck?** Ask the runner what it can see:

```bash
uv run crr inspect --repo gdrive --period 2026-09
```

If that lists folders, authentication and read access are fine and the problem is squarely the
write path — which narrows it to Part 2 (role) or Part 4 (wrong folder).

`crr build` runs this same check before it does anything else, so a real run will now stop in
about a second rather than spending a full run's classification (~$4.72 across eight
properties) and failing at the last step.

---

## If you cannot create a shared drive

Two situations, two answers.

### Your admin has disabled shared drives

Ask them to enable it, or to create one for you and add
`crr-runner@cornerstone-reports-508208.iam.gserviceaccount.com` as **Content manager**. The
admin setting is **Admin console → Apps → Google Workspace → Drive and Docs → Sharing settings
→ Shared drive creation**.

### You are not on Google Workspace at all

Shared drives require Workspace. Without it there is one alternative, **domain-wide
delegation**, where the service account impersonates a real user and the files are owned by
that person:

- It **also requires a Workspace admin**, so it does not help a personal account.
- It needs a **code change** — a `subject=` argument when the credentials are built in
  `src/crr/repository/drive_client.py` — which is not written yet.
- It grants the robot the ability to act as a real user, which is a meaningfully larger
  permission than membership of one shared drive.

If neither is available, the runner cannot publish to Drive, and `--repo local` with some other
means of moving files is the honest fallback. Say so and it can be planned properly rather than
discovered at the end of a run.

---

## What this does not change

- **Reading inputs still works exactly as before.** It always did; only writing was broken.
- **`--repo local` is unaffected**, which is why every test and CI build has been passing.
- **No code changes.** The Drive client already sends `supportsAllDrives=true` on every call, so
  it can work with a shared drive without modification.

---

*Background: recorded as B-09 in [`QUESTIONS.md`](QUESTIONS.md). The preflight that catches it is
SPEC §6.1.*
