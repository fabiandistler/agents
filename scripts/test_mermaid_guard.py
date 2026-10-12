"""Guardrail sync for Mermaid validation (#476, #477).

CI runs one pinned browserless command; the C4 guide documents that same
command as its first validation option and keeps the legacy mmdc variant
with its browser prerequisite. These tests pin that sync so the two
cannot drift apart.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GUIDE = REPO_ROOT / "skills" / "c4-modeling" / "references" / "mermaid-c4-guide.md"

# Pinned browserless validator: mermaid.parse via jsdom, no Puppeteer/Chrome.
PINNED_COMMAND = "npx -y @sysid/mmdlint@0.1.1"


def _validation_section() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    marker = "## Validating diagrams"
    assert marker in text, "guide lost its validation section"
    return text.split(marker, 1)[1]


def test_ci_runs_pinned_browserless_validator():
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    assert PINNED_COMMAND in ci, "CI does not run the pinned mmdlint command"
    lowered = ci.lower()
    assert "puppeteer" not in lowered, "CI validator must not pull in Puppeteer"
    assert "chromium" not in lowered, "CI validator must not download a browser"
    assert "setup-node" in ci, "CI needs Node to run the browserless validator"


def test_guide_first_option_is_ci_command():
    section = _validation_section()
    assert PINNED_COMMAND in section, "guide does not document the CI command"
    first_option = re.search(r"^1\.\s+(.*)$", section, re.MULTILINE)
    assert first_option is not None, "guide has no numbered first validation option"
    assert PINNED_COMMAND in first_option.group(1), (
        "guide's first validation option is not the CI command"
    )


def test_guide_legacy_mmdc_names_browser_prerequisite():
    section = _validation_section()
    assert "mmdc" in section, "guide lost its legacy mmdc variant"
    assert "browser" in section.lower(), "legacy mmdc variant must state its browser prerequisite"
