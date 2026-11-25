"""Where an implementer run lives: the workflow file, the job, and the branch names.

The defaults are this repository's own implementer caller workflow. Called as a reusable
workflow from another repository, a run is a run of the caller's workflow file,
because "the github context is always associated with the caller workflow"
(GitHub docs, "Reusing workflow configurations"). That file is the target
repository's choice, so it comes from --workflow-file or GITHUB_WORKFLOW_REF.
The job matches by its plain name or, inside a called workflow, by its
composed name (`agent_run_capacity.is_job`). The caller's queue workflow, if
it has one, comes from --queue-workflow (implementer_waiting.py).

Every value here goes into an API path or a branch name, so each is checked
before the first call; a bad one is a FetchError, which fails the claim.

Standard library only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from factory_handoff import AGENT_BRANCH_PREFIX, IMPLEMENTER_WORKFLOW, agent_branch
from pr_github_client import FetchError

WORKFLOW_REF_VARIABLE = "GITHUB_WORKFLOW_REF"
IMPLEMENT_JOB = "implement"
BRANCH_PREFIX = AGENT_BRANCH_PREFIX

# A file name under .github/workflows/, never a path.
WORKFLOW_FILE_PATTERN = re.compile(r"[A-Za-z0-9._-]+\.ya?ml")
# GITHUB_WORKFLOW_REF: owner/repo/.github/workflows/<file>@<ref>.
WORKFLOW_REF_PATTERN = re.compile(r"[^/@]+/[^/@]+/\.github/workflows/(?P<file>[^/@]+)@.+")
BRANCH_PREFIX_PATTERN = re.compile(r"[A-Za-z0-9._/-]+/|[A-Za-z0-9._/-]+-")


@dataclass(frozen=True)
class ImplementerSetup:
    workflow_file: str = IMPLEMENTER_WORKFLOW
    job_name: str = IMPLEMENT_JOB
    branch_prefix: str = BRANCH_PREFIX

    def branch(self, issue: int) -> str:
        return agent_branch(issue, self.branch_prefix)


DEFAULT_SETUP = ImplementerSetup()


def workflow_file(option: str | None) -> str:
    """--workflow-file, else the file GITHUB_WORKFLOW_REF names, else IMPLEMENTER_WORKFLOW."""
    if option is not None:
        source, file_name = "--workflow-file", option
    else:
        workflow_ref = os.environ.get(WORKFLOW_REF_VARIABLE, "")
        if not workflow_ref:
            return IMPLEMENTER_WORKFLOW
        match = WORKFLOW_REF_PATTERN.fullmatch(workflow_ref)
        if match is None:
            raise FetchError(
                f"{WORKFLOW_REF_VARIABLE} is not owner/repo/.github/workflows/<file>@<ref>"
            )
        source, file_name = WORKFLOW_REF_VARIABLE, match["file"]
    return _plain_workflow_file(source, file_name)


def optional_workflow_file(source: str, value: str) -> str | None:
    """A caller's workflow file input, such as --queue-workflow: None for '' (it has none).

    The one parser of these inputs; implementer_follow_up.py uses it too.
    """
    if value == "":
        return None
    return _plain_workflow_file(source, value)


def _plain_workflow_file(source: str, file_name: str) -> str:
    """``file_name`` if it is a file name under .github/workflows/; ``source`` names its origin."""
    if not WORKFLOW_FILE_PATTERN.fullmatch(file_name):
        raise FetchError(f"{source} does not name a plain *.yml or *.yaml file")
    return file_name


def branch_prefix(value: str) -> str:
    if not BRANCH_PREFIX_PATTERN.fullmatch(value):
        raise FetchError("--branch-prefix must be letters, digits, ._/- and end in / or -")
    return value
