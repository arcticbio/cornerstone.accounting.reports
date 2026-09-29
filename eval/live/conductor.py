"""Conductor for the overnight live test of 2026-09-29 (plan: eval/live/plan.py).

Plays the stakeholders into a Drive root at the planned minutes — uploads, new versions,
renames, moves, deletions, folders made by hand — and after every Azure run snapshots what the
system did. It never runs the reconciler: the Azure schedule does all the processing, exactly
as it will for real uploads.

    uv run python eval/live/conductor.py run --base 2026-09-29T06:30:00Z
    uv run python eval/live/conductor.py snapshot [--root ID] [--tag NAME]
    uv run python eval/live/conductor.py smoke --root <rehearsal root id>

Restartable: every action and snapshot is appended to `events.jsonl`, and a restart skips what
is already done. Logs file names, ids, statuses and counts only — never page text (§16).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan

from crr.config import load_config
from crr.intake.lease import LEASE_FILE, parse
from crr.intake.state import STATE_FILE
from crr.intake.status import ROOT_SUMMARY, headline_of, is_status_filename
from crr.intake.store import MANIFESTS
from crr.repository.drive_client import RETRIES, DriveFile, GoogleDriveApi
from crr.repository.google_drive import OUTPUT
from crr.settings import Settings

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eval" / "reports" / "live-test-2026-09-29"
WORK = REPO / "work" / "livetest"
BUNDLE = REPO / "data" / "bundle" / "2026-06"
CONFIG = load_config(REPO / "config")
END_OFFSET = 450  # the last tick whose run is observed
BUDGET_USD = 95.0  # stop starting new scenarios here; the owner's cap is $100


def now() -> datetime:
    return datetime.now(UTC)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class Log:
    def __init__(self, out: Path) -> None:
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        (out / "snapshots").mkdir(exist_ok=True)
        self.path = out / "events.jsonl"

    def write(self, kind: str, **fields: Any) -> None:
        record = {"at": iso(now()), "kind": kind, **fields}
        with self.path.open("a") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        print(json.dumps(record, default=str)[:400], flush=True)

    def read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


# -- files --------------------------------------------------------------------------------


def _inputs(prop: str) -> Path:
    entry = CONFIG.properties.property(prop)
    manager = CONFIG.properties.manager(entry.property_manager).folder
    return BUNDLE / manager / entry.folder / "2026-06 June" / "inputs"


def _bundle_file(prop: str, key: str) -> Path:
    prefix = {"pm": "05", "bs": "01", "pl": "02", "ds": "03"}[key]
    return next(p for p in sorted(_inputs(prop).iterdir()) if p.name.startswith(prefix))


def source(prop: str, key: str) -> Path:
    """The local file an action uploads, made on first use under work/ (never committed)."""
    from pypdf import PdfReader, PdfWriter

    if "@" in key:
        key, prop = key.split("@")
    if key in ("pm", "bs", "pl", "ds"):
        return _bundle_file(prop, key)
    ext = {"docx": "docx", "jpg": "jpg"}.get(key, "pdf")
    dest = WORK / "files" / prop / f"{key}.{ext}"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = key.split("-")[0]
    if key in ("bs-corrected", "bs-corrected-2", "bs-reissued", "pl-corrected"):
        writer = PdfWriter(clone_from=str(_bundle_file(prop, base)))
        writer.add_metadata({"/Subject": f"{key} (live test)", "/Keywords": key})
        writer.write(str(dest))
    elif key in ("pm-part1", "pm-part2"):
        reader = PdfReader(str(_bundle_file(prop, "pm")))
        half = len(reader.pages) // 2
        pages = range(half) if key == "pm-part1" else range(half, len(reader.pages))
        writer = PdfWriter()
        for i in pages:
            writer.add_page(reader.pages[i])
        writer.write(str(dest))
    elif key == "bs-protected":
        writer = PdfWriter(clone_from=str(_bundle_file(prop, "bs")))
        writer.encrypt(user_password="cornerstone", owner_password="cornerstone-owner")
        writer.write(str(dest))
    elif key == "text-as-pdf":
        dest.write_text("Corrected figures to follow - see email.\n")
    elif key == "unrelated-120":
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(dest), pagesize=letter)
        for i in range(120):
            c.drawString(72, 720, f"Unrelated scanned material - page {i + 1} of 120")
            c.showPage()
        c.save()
    elif key == "docx":
        dest.write_bytes(b"PK\x03\x04 live-test placeholder for a Word document\n")
    elif key == "jpg":
        import pypdfium2 as pdfium

        page = pdfium.PdfDocument(str(_bundle_file(prop, "bs")))[0]
        page.render(scale=0.5).to_pil().convert("RGB").save(dest, "JPEG")
    else:
        raise ValueError(f"unknown source {key!r}")
    return dest


# -- Drive --------------------------------------------------------------------------------


class Drive:
    def __init__(self, root: str) -> None:
        settings = Settings()
        self.api = GoogleDriveApi.from_b64(settings.google_service_account_b64 or "")
        self.svc = self.api._service
        self.root = root

    def children(self, folder_id: str) -> list[DriveFile]:
        return self.api.list_children(folder_id)

    def child(self, folder_id: str, name: str, *, folder: bool | None = None) -> DriveFile | None:
        for f in self.children(folder_id):
            if f.name == name and (folder is None or f.is_folder == folder):
                return f
        return None

    def ensure(self, parent: str, name: str) -> str:
        found = self.child(parent, name, folder=True)
        return found.id if found else self.api.create_folder(parent, name).id

    def property_id(self, prop: str) -> str:
        entry = CONFIG.properties.property(prop)
        manager = CONFIG.properties.manager(entry.property_manager).folder
        m = self.child(self.root, manager, folder=True)
        if m is None:
            raise RuntimeError(f"no manager folder {manager!r}")
        p = self.child(m.id, entry.folder, folder=True)
        if p is None:
            raise RuntimeError(f"no property folder {entry.folder!r}")
        return p.id

    @staticmethod
    def month_name(period: str) -> str:
        if period.startswith("folder:"):
            return period.split(":", 1)[1]
        return CONFIG.properties.period_folder(period)

    def month_id(self, prop: str, period: str) -> str:
        found = self.child(self.property_id(prop), self.month_name(period), folder=True)
        if found is None:
            raise RuntimeError(f"no month folder {self.month_name(period)!r} for {prop}")
        return found.id

    @staticmethod
    def component_name(prop: str, role: str) -> str:
        return next(c.folder for c in CONFIG.components_for(prop) if c.role == role)

    def place_id(self, prop: str, period: str, role: str | None, place: str | None) -> str:
        if place == "property":
            return self.property_id(prop)
        month = self.month_id(prop, period)
        if place == "month" or (role is None and place is None):
            return month
        if place == "output":
            return self.ensure(month, OUTPUT)
        found = self.child(month, self.component_name(prop, role or ""), folder=True)
        if found is None:
            raise RuntimeError(f"no component folder for {role} in {prop} {period}")
        return found.id

    def find(self, folder_id: str, contains: str) -> DriveFile:
        files = [f for f in self.children(folder_id) if not f.is_folder and contains in f.name]
        if not files:
            raise RuntimeError(f"no file containing {contains!r}")
        return sorted(files, key=lambda f: f.created_time or "")[-1]

    def move(self, file_id: str, src: str, dst: str) -> None:
        self.svc.files().update(
            fileId=file_id, addParents=dst, removeParents=src, supportsAllDrives=True, fields="id"
        ).execute(num_retries=RETRIES)

    def create_meta(self, body: dict[str, Any]) -> str:
        made = (
            self.svc.files()
            .create(body=body, supportsAllDrives=True, fields="id")
            .execute(num_retries=RETRIES)
        )
        return str(made["id"])

    def read_text(self, file_id: str) -> str:
        dest = WORK / "tmp" / f"{file_id}.txt"
        self.api.download(file_id, dest)
        text = dest.read_text(errors="replace")
        dest.unlink(missing_ok=True)
        return text


def perform(drive: Drive, act: plan.Act) -> dict[str, Any]:
    """Do one stakeholder action; return what was done, by id."""
    op = act.op
    if op == "upload":
        path = source(act.prop, act.src or "")
        dest = drive.place_id(act.prop, act.period, act.role, act.extra.get("place"))
        made = drive.api.upload(dest, path, act.name)
        return {"file_id": made.id, "mime": made.mime_type, "name": made.name}
    if op == "update":
        folder = drive.place_id(act.prop, act.period, act.role, None)
        target = drive.child(folder, act.name or "", folder=False)
        if target is None:
            raise RuntimeError(f"no file named {act.name!r} to update")
        drive.api.update_content(target.id, source(act.prop, act.src or ""))
        return {"file_id": target.id, "name": target.name}
    if op in ("trash", "trash_output"):
        place = "output" if op == "trash_output" else None
        folder = drive.place_id(act.prop, act.period, act.role, place)
        target = drive.find(folder, act.name or "")
        drive.api.trash(target.id)
        return {"file_id": target.id, "name": target.name}
    if op == "rename":
        folder = drive.place_id(act.prop, act.period, act.role, None)
        target = drive.find(folder, act.name or "")
        drive.api.rename(target.id, act.extra["new_name"])
        return {"file_id": target.id, "from": target.name, "to": act.extra["new_name"]}
    if op == "move":
        if act.extra.get("from_place") == "month":
            src = drive.month_id(act.prop, act.period)
        else:
            src = drive.place_id(act.prop, act.period, act.role, None)
        target = drive.find(src, act.name or "")
        if "to_period" in act.extra:
            dst = drive.place_id(act.prop, act.extra["to_period"], act.role, None)
        else:
            dst = drive.place_id(act.prop, act.period, act.extra["to_role"], None)
        drive.move(target.id, src, dst)
        return {"file_id": target.id, "name": target.name}
    if op == "mkdir":
        month = drive.ensure(drive.property_id(act.prop), drive.month_name(act.period))
        made = {"folder_id": month}
        if act.extra.get("with_components"):
            for c in CONFIG.components_for(act.prop):
                drive.ensure(month, c.folder)
            made["components"] = "made"
        return made
    if op == "gdoc":
        folder = drive.place_id(act.prop, act.period, act.role, None)
        doc = drive.create_meta(
            {
                "name": act.name,
                "mimeType": "application/vnd.google-apps.document",
                "parents": [folder],
            }
        )
        return {"file_id": doc}
    if op == "shortcut":
        folder = drive.place_id(act.prop, act.period, act.role, None)
        target_folder = drive.place_id(act.prop, act.period, act.extra["target_role"], None)
        pdfs = [f for f in drive.children(target_folder) if f.mime_type == "application/pdf"]
        target = sorted(pdfs, key=lambda f: f.created_time or "")[-1]
        sc = drive.create_meta(
            {
                "name": act.name,
                "mimeType": "application/vnd.google-apps.shortcut",
                "shortcutDetails": {"targetId": target.id},
                "parents": [folder],
            }
        )
        return {"file_id": sc, "target": target.id}
    if op == "manual":
        return {"manual": act.note}
    raise ValueError(f"unknown op {op!r}")


# -- observation --------------------------------------------------------------------------


def lease(drive: Drive) -> dict[str, Any] | None:
    found = drive.child(drive.root, LEASE_FILE, folder=False)
    if found is None:
        return None
    parsed = parse(drive.read_text(found.id))
    if parsed is None:
        return {"damaged": True}
    return {
        "host": parsed.host,
        "acquired": iso(parsed.acquired_at),
        "released": iso(parsed.released_at) if parsed.released_at else None,
        "expires": iso(parsed.expires_at),
    }


def _file(f: DriveFile) -> dict[str, Any]:
    return {
        "name": f.name,
        "id": f.id,
        "mime": f.mime_type,
        "md5": f.md5,
        "created": f.created_time,
        "modified": f.modified_time,
        "size": f.size,
    }


def _pdf_facts(path: Path) -> dict[str, Any]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))

    def count(items: Any) -> int:
        return sum(count(i) if isinstance(i, list) else 1 for i in items)

    title = reader.metadata.title if reader.metadata else None
    return {"pages": len(reader.pages), "bookmarks": count(reader.outline), "title": title}


def _manifest_facts(text: str) -> dict[str, Any]:
    data = json.loads(text)
    cost = data.get("cost") or {}
    return {
        "status": data.get("status"),
        "usd": cost.get("usd_estimate"),
        "calls": cost.get("api_calls"),
        "model": (data.get("classifier") or {}).get("model"),
        "reused": [
            i.get("role") for i in data.get("inputs") or [] if i.get("reused_classification")
        ],
        "review_codes": [r.get("code") for r in data.get("review_reasons") or []],
        "omitted": data.get("omitted_optional"),
        "timings_ms": data.get("timings_ms"),
        "error": data.get("error"),
    }


class Observer:
    def __init__(self, drive: Drive, log: Log) -> None:
        self.drive = drive
        self.log = log
        self.seen: set[str] = set()
        for e in log.read():
            if e["kind"] == "version":
                self.seen.add(e["key"])
        self.spent = sum(e.get("usd") or 0.0 for e in log.read() if e["kind"] == "version")

    def month(self, folder: DriveFile, prop: str) -> dict[str, Any]:
        out: dict[str, Any] = {"components": {}, "loose": [], "output": None, "state": None}
        component_names = {c.folder for c in CONFIG.components_for(prop)}
        for child in self.drive.children(folder.id):
            if not child.is_folder:
                out["loose"].append(_file(child))
            elif child.name == OUTPUT:
                out["output"] = self.output(child, prop, folder.name)
            elif child.name in component_names:
                out["components"][child.name] = [_file(f) for f in self.drive.children(child.id)]
            else:
                out.setdefault("other_folders", []).append(child.name)
        if out["output"]:
            out["state"] = out["output"].pop("_state", None)
        return out

    def output(self, folder: DriveFile, prop: str, month: str) -> dict[str, Any]:
        files = self.drive.children(folder.id)
        res: dict[str, Any] = {
            "status": [headline_of(f.name) for f in files if is_status_filename(f.name)],
            "pdfs": sorted(f.name for f in files if f.name.endswith(".pdf")),
            "reviews": sorted(f.name for f in files if f.name.startswith("REVIEW")),
            "other": sorted(
                f.name
                for f in files
                if not f.is_folder
                and not is_status_filename(f.name)
                and not f.name.endswith(".pdf")
                and not f.name.startswith("REVIEW")
            ),
        }
        manifests = next((f for f in files if f.is_folder and f.name == MANIFESTS), None)
        if manifests is None:
            return res
        mfiles = {f.name: f for f in self.drive.children(manifests.id)}
        if STATE_FILE in mfiles:
            try:
                res["_state"] = json.loads(self.drive.read_text(mfiles[STATE_FILE].id))
            except Exception as exc:
                res["_state"] = {"unreadable": type(exc).__name__}
        state = res.get("_state") or {}
        pdf_ids = {f.name: f.id for f in files if f.name.endswith(".pdf")}
        for v in state.get("versions", []) if isinstance(state, dict) else []:
            key = f"{prop}|{month}|v{v['version']}"
            if key in self.seen:
                continue
            facts: dict[str, Any] = {
                "key": key,
                "prop": prop,
                "month": month,
                "version": v["version"],
                "state_status": v.get("status"),
                "built_at": v.get("built_at"),
                "file": v.get("output_file"),
            }
            try:
                if v.get("output_file") in pdf_ids:
                    dest = WORK / "tmp" / f"{prop}-v{v['version']}.pdf"
                    self.drive.api.download(pdf_ids[v["output_file"]], dest)
                    facts.update(_pdf_facts(dest))
                    dest.unlink(missing_ok=True)
                name = f"v{v['version']}.json"
                if name in mfiles:
                    facts.update(_manifest_facts(self.drive.read_text(mfiles[name].id)))
            except Exception as exc:
                facts["error"] = f"{type(exc).__name__}: {exc}"[:200]
            self.seen.add(key)
            self.spent += facts.get("usd") or 0.0
            self.log.write("version", **facts)
        return res

    def snapshot(self, tag: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        snap: dict[str, Any] = {"tag": tag, "taken": iso(now()), **(extra or {})}
        snap["lease"] = lease(self.drive)
        summary = self.drive.child(self.drive.root, ROOT_SUMMARY, folder=False)
        snap["summary"] = self.drive.read_text(summary.id).splitlines() if summary else None
        snap["root_files"] = sorted(f.name for f in self.drive.children(self.drive.root))
        snap["properties"] = {}
        for entry in CONFIG.properties.properties:
            prop_id = self.drive.property_id(entry.id)
            record: dict[str, Any] = {"months": {}, "loose": []}
            for child in self.drive.children(prop_id):
                if child.is_folder:
                    record["months"][child.name] = self.month(child, entry.id)
                else:
                    record["loose"].append(_file(child))
            snap["properties"][entry.id] = record
        snap["spent_usd"] = round(self.spent, 4)
        (self.log.out / "snapshots" / f"{tag}.json").write_text(json.dumps(snap, indent=1))
        brief = {
            p: {
                m: [(v["output"] or {}).get("status"), len((v["output"] or {}).get("pdfs", []))]
                for m, v in r["months"].items()
            }
            for p, r in snap["properties"].items()
        }
        self.log.write(
            "snapshot", tag=tag, lease=snap["lease"], spent_usd=snap["spent_usd"], brief=brief
        )
        return snap


# -- the run ------------------------------------------------------------------------------


def run(base: datetime, root: str) -> None:
    log = Log(OUT)
    drive = Drive(root)
    observer = Observer(drive, log)
    events = log.read()
    done_acts = {e["index"] for e in events if e["kind"] in ("act", "act_failed", "act_skipped")}
    done_ticks = {e["tag"] for e in events if e["kind"] == "snapshot"}
    acts = sorted(enumerate(plan.ACTS), key=lambda ia: ia[1].at)
    ticks = [base + timedelta(minutes=30 * k) for k in range(END_OFFSET // 30 + 1)]
    log.write(
        "start",
        base=iso(base),
        root=root,
        acts=len(plan.ACTS),
        pending_acts=len(plan.ACTS) - len(done_acts),
        pid=os.getpid(),
    )
    missed = 0
    while True:
        t = now()
        stalled = missed >= 2
        for index, act in acts:
            if index in done_acts or t < base + timedelta(minutes=act.at):
                continue
            due = base + timedelta(minutes=act.at)
            if stalled or observer.spent > BUDGET_USD:
                reason = "stalled" if stalled else "budget"
                log.write("act_skipped", index=index, sid=act.sid, reason=reason)
                done_acts.add(index)
                continue
            try:
                result = perform(drive, act)
                log.write(
                    "act",
                    index=index,
                    sid=act.sid,
                    op=act.op,
                    prop=act.prop,
                    period=act.period,
                    role=act.role,
                    src=act.src,
                    name=act.name,
                    who=act.who,
                    due=iso(due),
                    late_s=round((t - due).total_seconds()),
                    note=act.note,
                    result=result,
                )
            except Exception as exc:
                log.write(
                    "act_failed",
                    index=index,
                    sid=act.sid,
                    op=act.op,
                    prop=act.prop,
                    error=f"{type(exc).__name__}: {exc}"[:300],
                )
            done_acts.add(index)
        for tick in ticks:
            tag = tick.strftime("%Y%m%d-%H%M")
            if tag in done_ticks or t < tick + timedelta(seconds=30):
                continue
            try:
                current = lease(drive)
            except Exception as exc:
                log.write("lease_error", error=f"{type(exc).__name__}: {exc}"[:200])
                break
            acquired = parse_iso(current["acquired"]) if current and "acquired" in current else None
            finished = (
                bool(current and current.get("released"))
                and acquired is not None
                and (acquired >= tick - timedelta(seconds=5))
            )
            waited_out = t > tick + timedelta(minutes=27)
            if not finished and not waited_out:
                break  # this tick's run is still going (or not started): look again shortly
            offset = int((tick - base).total_seconds() // 60)
            try:
                observer.snapshot(
                    tag, {"tick": iso(tick), "offset": offset, "run_observed": finished}
                )
            except Exception:
                log.write("snapshot_failed", tag=tag, error=traceback.format_exc()[-600:])
                time.sleep(20)
                break
            missed = 0 if finished else missed + 1
            if not finished:
                log.write("no_run", tag=tag, offset=offset, lease=current, missed=missed)
            done_ticks.add(tag)
            break
        (OUT / "heartbeat.json").write_text(
            json.dumps(
                {
                    "at": iso(now()),
                    "pid": os.getpid(),
                    "acts_done": len(done_acts),
                    "acts_total": len(plan.ACTS),
                    "ticks_done": len(done_ticks),
                    "ticks_total": len(ticks),
                    "spent_usd": round(observer.spent, 4),
                    "stalled": stalled,
                }
            )
        )
        if len(done_ticks) >= len(ticks) and len(done_acts) >= len(plan.ACTS):
            log.write("finished", spent_usd=round(observer.spent, 4))
            return
        time.sleep(15)


def smoke(root: str) -> None:
    """Every operation once, in the rehearsal root's October folders; then tidy up."""
    log = Log(WORK / "smoke")
    drive = Drive(root)
    prop, period = "fort-grounds", plan.OCT
    steps = [
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.PM, "pm", "smoke report.pdf"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.BS, "bs-protected", "smoke p.pdf"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.PL, "text-as-pdf", "smoke t.pdf"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.PM, "docx", "smoke.docx"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.PM, "jpg", "smoke.jpg"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.DS, "unrelated-120", "smoke u.pdf"),
        plan.Act(0, "smoke", "t", "upload", prop, period, plan.BS, "pm-part1", "smoke half.pdf"),
        plan.Act(
            0,
            "smoke",
            "t",
            "upload",
            prop,
            period,
            None,
            "ds",
            "smoke m.pdf",
            extra={"place": "month"},
        ),
        plan.Act(
            0, "smoke", "t", "update", prop, period, plan.PM, "bs-corrected", "smoke report.pdf"
        ),
        plan.Act(
            0,
            "smoke",
            "t",
            "rename",
            prop,
            period,
            plan.PM,
            name="smoke report",
            extra={"new_name": "smoke renamed.pdf"},
        ),
        plan.Act(0, "smoke", "t", "gdoc", prop, period, plan.PL, name="smoke doc"),
        plan.Act(
            0,
            "smoke",
            "t",
            "shortcut",
            prop,
            period,
            plan.DS,
            name="smoke sc",
            extra={"target_role": plan.PM},
        ),
        plan.Act(
            0,
            "smoke",
            "t",
            "move",
            prop,
            period,
            None,
            name="smoke m",
            extra={"from_place": "month", "to_role": plan.PL},
        ),
        plan.Act(
            0,
            "smoke",
            "t",
            "mkdir",
            prop,
            "folder:2026-07 July (smoke)",
            extra={"with_components": "yes"},
        ),
    ]
    made: list[str] = []
    for act in steps:
        result = perform(drive, act)
        log.write("smoke", op=act.op, src=act.src, result=result)
        made += [v for k, v in result.items() if k in ("file_id", "folder_id")]
    Observer(drive, log).snapshot("smoke")
    for file_id in dict.fromkeys(made):
        drive.api.trash(file_id)
    log.write("smoke_done", trashed=len(set(made)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "snapshot", "smoke"])
    parser.add_argument("--base")
    parser.add_argument("--root", default=Settings().gdrive_root_folder_id)
    parser.add_argument("--tag", default=None)
    args = parser.parse_args()
    if args.command == "run":
        run(parse_iso(args.base), args.root)
    elif args.command == "smoke":
        smoke(args.root)
    else:
        log = Log(OUT if args.root == Settings().gdrive_root_folder_id else WORK / "adhoc")
        Observer(Drive(args.root), log).snapshot(args.tag or now().strftime("adhoc-%H%M%S"))


if __name__ == "__main__":
    main()
