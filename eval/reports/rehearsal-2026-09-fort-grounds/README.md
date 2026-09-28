# Continuous-intake rehearsal — Fort Grounds, September 2026 (v1–v6)

The record of PLAN Phase 10's live-drive rehearsal (2026-09-26, `PROGRESS.md` → Phase 10): an
uploader played through the Drive API with June files under new names, and the reconciler took
the month through waiting, settling, six built versions, a held file, a revert and two
real-model builds.

The rehearsal was left in the live `2026-09 September` month, where a real September upload
would have been combined with its June statements, so it was moved out of the production root
on 2026-09-28. This directory keeps what git may hold. The originals — PDFs included — are in
Drive, unchanged and with the same file ids; `inventory.json` lists them.

| Here | What it is |
|---|---|
| `inventory.json` | every file and folder as it stood: Drive id, size, md5, times; and for each input, how to rebuild it byte for byte from `data/bundle/2026-06` |
| `output/STATUS - Built v6 (current).txt` | the status file, as the reviewer saw it |
| `output/manifests/state.json` | the month's index: v1–v6, their fingerprints and inputs |
| `output/manifests/v1.json` … `v6.json` | the build manifests. v1–v4 used golden labels; v5 and v6 used the real model (`claude-opus-5`, prompt v1). Their `evidence` — a model-written sentence about each page — is replaced by a marker, as the eval predictions files omit it; every other field is as built, and each file still validates as a `BuildManifest`. |

Not here: the six report PDFs and the five input PDFs (PDFs are never committed outside
`data/bundle/`). The inputs are June bundle files — four byte-identical, and the "revised"
P&L is the June P&L with `\n%revised\n` appended — so `inventory.json` is enough to rebuild
them. The reports are the composer's deterministic output from those inputs and the labels in
the manifests.
