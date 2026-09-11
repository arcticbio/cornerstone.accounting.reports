# Setting up Google Drive so the runner can publish

**Status: this is the one thing standing between the runner and production.** Everything else
works — it reads inputs from Drive, classifies, composes and produces correct packages. It
cannot put a single file back. This document fixes that.

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
| **What it is called today** | A **My Drive** folder named **Cornerstone Reports**, owned by a person. Its id is in `CRR_GDRIVE_ROOT_FOLDER_ID`. |

> **A note on the robot's address.** It is long and ends in
> `.iam.gserviceaccount.com`. That is correct — it is not an email you can send mail to, but
> Drive treats it as a person for sharing purposes, which is what we want.

---

## What you will be doing

| Part | Where | Roughly |
|---|---|---|
| 1 | Google Drive | Create a shared drive | 3 min |
| 2 | Google Drive | Add the runner to it as **Content manager** | 3 min |
| 3 | Google Drive | Move `Cornerstone Reports` into the shared drive | 5 min |
| 4 | Anywhere | Confirm the folder id did not change | 2 min |
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
   | Contributor | ⚠️ may be enough to upload, but not to remove the runner's own preflight probe. Don't pick it. |
   | **Content manager** | ✅ **choose this** — everything the runner does, nothing it doesn't |
   | Manager | also works, but additionally lets the robot change who has access. No reason to grant that. |

6. **Untick "Notify people"** if the option appears — nobody is going to read a robot's email.
7. Click **Send** / **Share**.

Check the member list now shows the `crr-runner@…` address with **Content manager** beside it.

---

# Part 3 — Move the reports folder in

> **Read this box before you drag anything.**
>
> Moving a folder into a shared drive **transfers ownership of everything inside it** to the
> shared drive. That is the point, and it is not reversible by dragging it back out — getting
> the files back into a person's My Drive afterwards is a manual, file-by-file job.
>
> It is a safe operation for this data: the contents are report inputs and outputs, and the
> people who can see them are the shared drive's members, who you control in Part 2. But do it
> deliberately rather than by accident.
>
> **Anything shared with people outside your Workspace domain may lose that sharing.** If an
> external accountant or investor has a link to a file in here, re-share it afterwards.

1. In the left sidebar, click **My Drive** and find the **Cornerstone Reports** folder.
2. Right-click it → **Organise** → **Move** (older UI: just **Move**).
3. Pick **Shared drives** → your new **Cornerstone Investor Reports** drive → **Move**.
4. Drive will warn you that ownership will transfer and sharing may change. Read it, then
   confirm.

Depending on how much is in the folder this may take a minute or two to settle. Refresh and
confirm **Cornerstone Reports** now appears *inside* the shared drive, and is gone from My
Drive.

---

# Part 4 — Confirm the folder id did not change

Google Drive keeps a folder's id when you move it, so `CRR_GDRIVE_ROOT_FOLDER_ID` should still
be correct and there is usually **nothing to do here**. Confirm it rather than assume it:

1. Open the **Cornerstone Reports** folder (now inside the shared drive).
2. Look at the browser address bar. It ends with the folder id:

   ```
   https://drive.google.com/drive/folders/1_tUMel............
                                          ^^^^^^^^^^^^^^^^^^ this is the id
   ```

3. Compare it to the value of `CRR_GDRIVE_ROOT_FOLDER_ID`. If they match — and they should —
   you are done with this part.

**If they differ** (you created a fresh folder instead of moving the old one, say), update the
value everywhere it is set:

| Where | How |
|---|---|
| GitHub Actions | repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** → `CRR_GDRIVE_ROOT_FOLDER_ID` |
| Azure | Key Vault → the secret of the same name → **+ New Version** (see `SETUP-AZURE-PORTAL.md`) |
| Claude Code | the cloud environment's variables |
| Your laptop | `.env` |

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
| `storageQuotaExceeded` | the root is still a My Drive folder | Part 3 did not take effect, or `CRR_GDRIVE_ROOT_FOLDER_ID` points at a different folder than the one you moved. Re-check Part 4. |
| `File not found` / `404` | the runner cannot see the folder at all | Part 2: the robot is not a member of the shared drive, or you added a different address. Check for a typo. |
| `insufficientFilePermissions` | the robot can read but not write | Part 2: the role is Viewer, Commenter or Contributor. Set it to **Content manager**. |
| `invalid_grant` / auth errors | the credentials are wrong or expired | Not this document's problem — see `SETUP-CREDENTIALS.md`. |

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
