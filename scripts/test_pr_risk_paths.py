"""Path table of the pull request risk policy (scripts/pr_risk.py).

Every path class in #621 maps to its risk and names the matched rule. The
seam is ``classify_pull_request(context)``; the escalation rules and the CLI
are covered in ``test_pr_risk.py``.
"""

from __future__ import annotations

import pr_risk
import pytest
from test_pr_risk import file_entry, make_context

PATH_CASES = [
    # low
    ("MAINTENANCE.md", "low", "docs"),
    ("GLOSSARY.md", "low", "docs"),
    ("docs/guide.md", "low", "docs"),
    ("docs/a/b/c.md", "low", "docs"),
    ("docs/agents.md", "low", "docs"),
    ("maintenance/reports/weekly.md", "low", "maintenance-reports"),
    # medium
    ("skills/foo/SKILL.md", "medium", "skills"),
    ("skills/foo/references/guide.md", "medium", "skills"),
    ("instructions/10-core.md", "medium", "instructions"),
    ("docs/agents/pr-review.md", "medium", "agent-docs"),
    # medium: agent instruction files, wherever they sit
    ("AGENTS.md", "medium", "agent-docs"),
    ("CLAUDE.md", "medium", "agent-docs"),
    ("docs/guides/AGENTS.md", "medium", "agent-docs"),
    ("maintenance/reports/CLAUDE.md", "medium", "agent-docs"),
    # medium: documents that state repository policy, such as the merge rule
    ("README.md", "medium", "policy-docs"),
    ("docs/adr/0001-record-decisions.md", "medium", "adr"),
    ("docs/adr/README.md", "medium", "adr"),
    ("skills.json", "medium", "catalogue"),
    ("plugins/architecture/skills/x/SKILL.md", "medium", "plugins"),
    ("plugins/architecture/.claude-plugin/plugin.json", "medium", "plugins"),
    ("plugins/merge-guard.md", "medium", "plugins"),
    (".claude/skills/foo/SKILL.md", "medium", "claude-mirror"),
    (".claude/rules/x.md", "medium", "claude-mirror"),
    (".claude/settings.json.bak", "medium", "claude-mirror"),
    ("scripts/test_catalogue.py", "medium", "tests"),
    ("scripts/test_install.sh", "medium", "tests"),
    ("scripts/vendor_mattpocock_skills.py", "medium", "scripts"),
    ("scripts/skill_audit_select.py", "medium", "scripts"),
    # medium: the vendored maintenance scanner and its helpers, run by agents
    ("scripts/maintenance-scan.sh", "medium", "scripts"),
    ("scripts/maintenance-new-deps.py", "medium", "scripts"),
    ("scripts/maintenance-r-advisories.py", "medium", "scripts"),
    # medium: Bats tests and test fixtures
    ("test/install.bats", "medium", "tests"),
    ("test/install_helper.bash", "medium", "tests"),
    ("scripts/fixtures/mermaid/broken.md", "medium", "tests"),
    # medium: the marketplace manifest and the record of declined ideas
    (".claude-plugin/marketplace.json", "medium", "plugins"),
    (".out-of-scope/pr-description-skill.md", "medium", "agent-docs"),
    ("maintenance/scan.sh", "medium", "maintenance"),
    ("maintenance/reports.md", "medium", "maintenance"),
    # high: the triage automation itself
    ("scripts/pr_risk.py", "high", "triage-automation"),
    ("scripts/pr_github.py", "high", "triage-automation"),
    ("scripts/pr_review.py", "high", "triage-automation"),
    ("scripts/pr_review_prompt.md", "high", "triage-automation"),
    ("scripts/pr_publish.py", "high", "triage-automation"),
    ("scripts/pr_apply.py", "high", "triage-automation"),
    ("scripts/test_pr_risk.py", "high", "triage-automation"),
    ("scripts/test_pr_github.py", "high", "triage-automation"),
    ("scripts/test_pr_review.py", "high", "triage-automation"),
    ("scripts/test_pr_publish.py", "high", "triage-automation"),
    ("scripts/test_pr_apply.py", "high", "triage-automation"),
    ("scripts/test_pr_workflow.py", "high", "triage-automation"),
    (".github/workflows/pr-review.yml", "high", "workflow"),
    # high: workflows, installer, gates, guards, configuration
    (".github/workflows/ci.yml", "high", "workflow"),
    (".github/ISSUE_TEMPLATE/bug.md", "high", "workflow"),
    ("install.sh", "high", "installer"),
    ("scripts/check_all.sh", "high", "gate-script"),
    ("scripts/check_descriptions.py", "high", "gate-script"),
    ("scripts/check_all.requirements.txt", "high", "gate-script"),
    ("scripts/quick_validate.py", "high", "gate-script"),
    ("scripts/require_python.sh", "high", "gate-script"),
    ("scripts/catalogue.py", "high", "gate-script"),
    # gate helpers: imported by a check script or run as a check_all.sh check
    ("scripts/skill_frontmatter.py", "high", "gate-script"),
    ("scripts/instruction_fragments.py", "high", "gate-script"),
    ("scripts/vendor_repo_maintenance.py", "high", "gate-script"),
    ("scripts/vendoring.py", "high", "gate-script"),
    ("scripts/build_manifest.py", "high", "build-script"),
    ("scripts/pr_merge_guard.py", "high", "guard-script"),
    ("scripts/secret_read_guard.py", "high", "guard-script"),
    ("scripts/opencode/pr-merge-guard.js", "high", "hook-script"),
    ("scripts/hooks/check-file-tokens.sh", "high", "hook-script"),
    ("scripts/python_init_context.py", "high", "hook-script"),
    ("scripts/install/main.sh", "high", "installer"),
    ("scripts/plugin_agents.py", "high", "installer"),
    ("plugins/merge-guard/hooks/hooks.json", "high", "guard-script"),
    ("plugins/secret-guard/scripts/guard.py", "high", "guard-script"),
    ("plugins/architecture/hooks/hooks.json", "high", "hook-settings"),
    (".claude/settings.json", "high", "hook-settings"),
    (".pre-commit-config.yaml", "high", "hook-settings"),
    ("conftest.py", "high", "test-config"),
    ("ruff.toml", "high", "lint-config"),
    ("pyrightconfig.json", "high", "lint-config"),
    ("pyproject.toml", "high", "project-config"),
    ("package.json", "high", "dependency-pins"),
    ("package-lock.json", "high", "dependency-pins"),
    ("tools/dev.requirements.txt", "high", "dependency-pins"),
    (".gitmodules", "high", "dependency-pins"),
    ("test/bats/bats-core", "high", "dependency-pins"),
    ("vendor/repo-maintenance/lock.json", "high", "dependency-pins"),
    (".shellcheckrc", "high", "lint-config"),
    ("ty.toml", "high", "lint-config"),
    (".gitattributes", "high", "project-config"),
    (".gitignore", "high", "project-config"),
    # high: unknown paths
    ("scripts/random.py", "high", "unknown"),
    ("AGENTS.markdown", "high", "unknown"),
    ("skills.md", "high", "unknown"),
    ("documentation/guide.md", "high", "unknown"),
    ("site/app.js", "high", "unknown"),
]


@pytest.mark.parametrize(("path", "risk", "rule"), PATH_CASES)
def test_every_path_class_maps_to_its_documented_risk(path, risk, rule):
    decision = pr_risk.classify_pull_request(make_context([file_entry(path)]))

    assert decision["risk"] == risk
    assert decision["reasons"] == [f"{rule}: {path}"]
    assert decision["auto_merge_eligible"] is (risk == "low")


def test_path_classes_do_not_depend_on_file_order():
    forward = pr_risk.classify_pull_request(
        make_context([file_entry("README.md"), file_entry("scripts/pr_risk.py")])
    )
    backward = pr_risk.classify_pull_request(
        make_context([file_entry("scripts/pr_risk.py"), file_entry("README.md")])
    )

    assert forward["risk"] == "high"
    assert backward["risk"] == "high"
    assert set(forward["reasons"]) == set(backward["reasons"])
