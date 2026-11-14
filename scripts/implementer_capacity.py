"""The implementer's capacity gate: how many other implementer runs work ahead of this one.

It reads the Actions API, whose run and job listings are the only record of
which runs are working. The caller passes a client holding the job token
(ACTIONS_READ_TOKEN), because the App token cannot be shown to have Actions
read (ADR-0014). The ordering itself is ``agent_run_capacity``'s, shared with
the Rework gate.

Standard library only.
"""

from __future__ import annotations

import agent_run_capacity
from implementer_setup import ImplementerSetup
from pr_github_client import ReadClient

MAX_WORKING_RUNS = 1


def runs_working_ahead(client: ReadClient, repo: str, run_id: int, setup: ImplementerSetup) -> int:
    """How many other working runs of the setup's workflow and job come before this one."""
    return agent_run_capacity.runs_working_ahead(
        client, repo, run_id, setup.workflow_file, (setup.job_name,)
    )
