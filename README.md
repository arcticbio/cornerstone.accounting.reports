# Cornerstone Report Runner (`crr`)

Cornerstone Management Consulting sends quarterly investor report packages for eight rental
properties. Each package was assembled by hand from two upstream sources: the property
manager's monthly export, and Cornerstone's own entity-level accounting. This assembles them.

A vision model labels every page of every source document — which report it belongs to, whether
it continues the previous page, which property record it is for, which way up it is. Everything
after that is deterministic: a page plan resolved from a per-manager output definition, composed
with `pypdf`, and a manifest recording exactly what was built from what. When a page is
ambiguous the package goes to a review queue rather than to investors.

## Quickstart

```bash
uv sync                                                   # Python 3.12 toolchain
uv run crr validate-config                                # schemas, outputs, properties
uv run crr build --period 2026-06 --classifier golden     # build the eight golden packages
uv run crr eval --classifier golden --gate                # score the classifier, gate on it
uv run crr inspect --repo gdrive --period 2026-09         # what a Drive period holds
```

`crr build` exits **0** when every package built, **2** when any package needs review, **1** when
any property failed. Outputs, the manifest and `REVIEW.md` land beside the inputs.

## Where things are

| | |
|---|---|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | how to run a quarter, work the review queue, add a property or a manager |
| [`docs/SETUP-CREDENTIALS.md`](docs/SETUP-CREDENTIALS.md) | where each secret goes, and which copy does what |
| [`docs/SETUP-AZURE.md`](docs/SETUP-AZURE.md) | one-time Azure setup, end to end (CLI) |
| [`docs/SETUP-AZURE-PORTAL.md`](docs/SETUP-AZURE-PORTAL.md) | the same setup, click by click in the Azure portal |
| [`docs/SPEC.md`](docs/SPEC.md) | the technical contract: interfaces, formats, invariants |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | why it is built this way |
| [`docs/PLAN.md`](docs/PLAN.md) · [`PROGRESS.md`](PROGRESS.md) | the build plan and where it got to |
| `config/` | the whole product surface: schemas, output definitions, the property registry |
| `src/crr/` | the runner |
| `eval/golden/` | page-level ground truth for June 2026, and the offline classifier |
| `data/bundle/2026-06/` | the June 2026 bundle — a read-only fixture, not an archive |

Adding a property or a property manager is a config change, not a code change. `docs/RUNBOOK.md`
has both procedures.

## Hosting

The same container runs everywhere. GitHub Actions is the host today — *Actions → Build a period
→ Run workflow*. For the scheduled Azure Container Apps Job, follow
[`docs/SETUP-AZURE.md`](docs/SETUP-AZURE.md) (CLI, starts with `./infra/bootstrap.sh`) or
[`docs/SETUP-AZURE-PORTAL.md`](docs/SETUP-AZURE-PORTAL.md) (portal).
