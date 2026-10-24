# Runner environment and recovery

## Supported environment

Start the loop from a terminal in a separately provisioned container or VM,
with the repository and its Git metadata writable and the runner installed.
For Codex, this environment must be suitable for the documented
`danger-full-access` task flags: it provides the isolation around the runner.
A KVM guest alone is insufficient if the calling process is already sandboxed.
Ask the environment owner to provision a suitable session; keep the restrictions
of the current session intact. Changing mounts, socket-directory modes or
permission flags to escape that session is not a recovery step.

The preflight runs before branch creation and task attempts. It asks the runner
to execute an actual shell command, probe writes to the Git directory, shared
Git directory, objects and branch refs, and create a fresh proof file. It uses
the task's runner flags, including `POC_AGENT_FLAGS` overrides, and times out
after 45 seconds. Exit 4 means infrastructure failed; no task attempt was used.
The last probe output is in `.git/poc-loop/preflight.log` (in the worktree's
Git directory for linked worktrees); stderr shows at most its final 4,000 bytes.

For example, Codex may start and exit successfully while its shell reports:

```text
error building bubblewrap command: app-server socket directory must be a user-owned directory with mode 0700
```

Treat this as a sandbox infrastructure failure. Provision the new environment
and rerun the same loop command there. The preflight must pass before work
starts. A successful probe establishes current access, not future availability.

## Human-approved retry of one blocked item

Items already blocked by an older run retain their state: restarting does not
reset them. After repairing the environment, obtain human approval naming the
single item to retry, then:

1. Switch to the existing `poc/*` branch recorded in `plans/prd.json`; start
   with a clean tree. Inspect that item's failure and confirm it has
   `passes: false` and `attempts: 3`.
2. Edit only that item's `attempts` to `0` in `plans/prd.json`. Keep its id,
   dependencies, check and all other item states unchanged.
3. In `plans/BLOCKED.md`, remove only the section starting with
   `## prd-NN —` for the approved id, ending immediately before the next
   `## ` heading (or end of file). Delete the file if it is now empty.
   Leave every other blocked section intact, so the final PR reflects them.
4. Review `git diff -- plans/prd.json plans/BLOCKED.md`. Commit just those
   two paths as `chore(plans): approve retry of prd-NN`, recording the human
   approval in the commit body. Do not reset the branch or recreate the PRD.
5. Rerun `POC_AGENT=<runner> bash <skill-dir>/assets/loop.sh`. The same
   preflight runs again; failure leaves even the reset attempt count at zero.

The retry follows the normal dependency selection and three-attempt limit.
Other blocked items and completed items remain untouched. An existing PR may
need its body updated manually after a resumed run; the committed full body is
`plans/PR.md`.
