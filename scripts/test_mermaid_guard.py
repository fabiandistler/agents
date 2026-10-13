"""Guardrail sync for Mermaid validation (#476, #477).

CI runs one pinned browserless command; the C4 guide documents that same
command as its first validation option and keeps the legacy mmdc variant
with its browser prerequisite. These tests pin that sync so the two
cannot drift apart.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GUIDE = REPO_ROOT / "skills" / "c4-modeling" / "references" / "mermaid-c4-guide.md"
FIXTURES = REPO_ROOT / "scripts" / "fixtures" / "mermaid"

# Pinned browserless validator: mermaid.parse via jsdom, no Puppeteer/Chrome.
# mermaid is pinned too, since mmdlint only declares a ^11 range for it.
PINNED_COMMAND = "npx -y -p @sysid/mmdlint@0.1.1 -p mermaid@11.17.0 mmdlint"


def _mermaid_job() -> dict:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert "mermaid" in workflow["jobs"], "CI lost its mermaid job"
    return workflow["jobs"]["mermaid"]


def _validation_section() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    marker = "## Validating diagrams"
    assert marker in text, "guide lost its validation section"
    return text.split(marker, 1)[1]


def test_ci_runs_pinned_browserless_validator():
    job = _mermaid_job()
    assert job["env"]["MMDLINT"] == PINNED_COMMAND, (
        "CI mermaid job does not run the pinned mmdlint command"
    )
    job_text = yaml.safe_dump(job).lower()
    assert "puppeteer" not in job_text, "CI validator must not pull in Puppeteer"
    assert "chromium" not in job_text, "CI validator must not download a browser"
    assert any("setup-node" in step.get("uses", "") for step in job["steps"]), (
        "CI needs Node to run the browserless validator"
    )


def test_ci_proves_validator_rejects_broken_fixture():
    runs = "\n".join(step.get("run", "") for step in _mermaid_job()["steps"])
    for fixture in ("valid.md", "broken.md"):
        assert (FIXTURES / fixture).is_file(), f"fixture {fixture} missing"
        assert f"scripts/fixtures/mermaid/{fixture}" in runs, (
            f"CI mermaid job does not check fixture {fixture}"
        )
    assert "':!:scripts/fixtures/'" in runs, "repo-wide scan must exclude the broken fixture"


def test_guide_first_option_is_ci_command():
    section = _validation_section()
    first_option = re.search(r"^1\.\s+(.*)$", section, re.MULTILINE)
    assert first_option is not None, "guide has no numbered first validation option"
    assert PINNED_COMMAND in first_option.group(1), (
        "guide's first validation option is not the CI command"
    )


def test_guide_stays_repo_agnostic():
    # The guide ships inside a skill installed into other repositories,
    # which have no `mermaid` CI job to point at.
    section = _validation_section()
    assert "`mermaid` job" not in section, "guide must not name this repo's CI job"


def test_guide_legacy_mmdc_names_browser_prerequisite():
    section = _validation_section()
    assert "mmdc" in section, "guide lost its legacy mmdc variant"
    assert "browser" in section.lower(), "legacy mmdc variant must state its browser prerequisite"
