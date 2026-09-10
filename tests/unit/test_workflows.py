"""The shipped workflows and Dockerfile, checked structurally.

CI cannot run in this environment (B-02) and there is no Docker daemon (B-03), so these
tests hold the shape: the image must not carry tenant data, the dispatch inputs must exist,
and the exit-code contract must be interpreted rather than swallowed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS = Path(".github/workflows")
DOCKERFILE = Path("Dockerfile").read_text()
DOCKERIGNORE = Path(".dockerignore").read_text()


def _workflow(name: str) -> dict:
    # `on:` parses as the boolean True in YAML 1.1; read it back under that key.
    return yaml.safe_load((WORKFLOWS / name).read_text())


class TestDockerfile:
    def test_it_is_multi_stage_from_the_spec_base(self) -> None:
        assert DOCKERFILE.count("FROM python:3.12-slim") == 2
        assert "AS builder" in DOCKERFILE
        assert "AS runtime" in DOCKERFILE

    def test_the_ocr_toolchain_is_installed(self) -> None:
        for package in (
            "tesseract-ocr",
            "tesseract-ocr-eng",
            "tesseract-ocr-osd",
            "ocrmypdf",
            "ghostscript",
        ):
            assert package in DOCKERFILE, package

    def test_it_runs_as_a_non_root_user(self) -> None:
        assert "useradd" in DOCKERFILE
        assert DOCKERFILE.rstrip().index("USER crr") < DOCKERFILE.index('ENTRYPOINT ["crr"]')

    def test_the_healthcheck_is_crr_version(self) -> None:
        assert "HEALTHCHECK" in DOCKERFILE
        assert 'CMD ["crr", "version"]' in DOCKERFILE

    def test_the_bundle_never_enters_the_image(self) -> None:
        """SPEC §14, §16: tenant data is mounted, never baked in."""
        assert "data/" in DOCKERIGNORE.splitlines()
        assert "work/" in DOCKERIGNORE.splitlines()
        copies = [line for line in DOCKERFILE.splitlines() if line.startswith("COPY")]
        assert not any("data/" in line for line in copies)

    def test_config_and_golden_labels_are_in_the_image(self) -> None:
        """The runner needs its config; the golden labels are the offline classifier."""
        assert "config/ /app/config/" in DOCKERFILE
        assert "eval/golden/ /app/eval/golden/" in DOCKERFILE


class TestCiWorkflow:
    def setup_method(self) -> None:
        self.ci = _workflow("ci.yml")
        self.jobs = self.ci["jobs"]

    def test_the_check_job_runs_the_whole_gate(self) -> None:
        steps = " ".join(str(s.get("run", "")) for s in self.jobs["check"]["steps"])
        for command in (
            "ruff check .",
            "ruff format --check .",
            "mypy src",
            "pytest -q",
            "crr validate-config",
            "crr eval --classifier golden --gate",
        ):
            assert command in steps, command

    def test_the_image_job_proves_the_bundle_is_not_baked_in(self) -> None:
        steps = " ".join(str(s.get("run", "")) for s in self.jobs["image"]["steps"])
        assert "[ -e /app/data ]" in steps

    def test_the_image_job_runs_a_golden_build_in_the_container(self) -> None:
        steps = " ".join(str(s.get("run", "")) for s in self.jobs["image"]["steps"])
        assert "CRR_BUNDLE_ROOT=/data/bundle/2026-06" in steps
        assert "build --period 2026-06 --classifier golden --repo local" in steps

    def test_ghcr_publishing_needs_packages_write(self) -> None:
        assert self.jobs["image"]["permissions"]["packages"] == "write"

    def test_tags_follow_the_spec(self) -> None:
        steps = " ".join(str(s.get("run", "")) for s in self.jobs["image"]["steps"])
        assert ":build-v1" in steps
        assert ":latest" in steps
        assert "sha-" in steps


class TestBuildPeriodWorkflow:
    def setup_method(self) -> None:
        self.workflow = _workflow("build-period.yml")
        self.trigger = self.workflow[True]  # `on:`

    def test_it_is_dispatchable_with_the_spec_inputs(self) -> None:
        inputs = self.trigger["workflow_dispatch"]["inputs"]
        assert set(inputs) == {"period", "property", "repo", "classifier", "image_tag"}
        assert inputs["period"]["required"] is True
        assert inputs["property"]["required"] is False
        assert inputs["repo"]["default"] == "gdrive"
        assert set(inputs["repo"]["options"]) == {"gdrive", "local"}
        assert inputs["image_tag"]["default"] == "build-v1"

    def test_the_quarterly_cron_is_present_but_commented(self) -> None:
        text = (WORKFLOWS / "build-period.yml").read_text()
        assert "# schedule:" in text
        assert '- cron: "0 6 20 1,4,7,10 *"' in text
        assert "schedule" not in self.trigger

    def test_it_passes_the_secrets_the_runner_needs(self) -> None:
        job = self.workflow["jobs"]["build"]
        env = next(s for s in job["steps"] if s.get("id") == "build")["env"]
        assert "secrets.ANTHROPIC_API_KEY" in env["ANTHROPIC_API_KEY"]
        assert "secrets.GOOGLE_SERVICE_ACCOUNT_B64" in env["GOOGLE_SERVICE_ACCOUNT_B64"]
        assert "vars.CRR_GDRIVE_ROOT_FOLDER_ID" in env["CRR_GDRIVE_ROOT_FOLDER_ID"]

    def test_it_uploads_the_manifests_even_when_the_build_fails(self) -> None:
        job = self.workflow["jobs"]["build"]
        upload = next(s for s in job["steps"] if "upload-artifact" in str(s.get("uses", "")))
        assert upload["if"] == "always()"

    def test_the_exit_code_contract_is_interpreted(self) -> None:
        """SPEC §6.8: 0 built, 2 review (a warning annotation), anything else fails the job."""
        job = self.workflow["jobs"]["build"]
        interpret = next(s for s in job["steps"] if str(s.get("name", "")).startswith("Interpret"))[
            "run"
        ]
        assert "::warning" in interpret
        assert "::error" in interpret
        assert "exit 1" in interpret

    def test_pulling_from_ghcr_needs_packages_read(self) -> None:
        assert self.workflow["jobs"]["build"]["permissions"]["packages"] == "read"
