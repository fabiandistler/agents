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

The preflight runs before branch creation and task attempts. The driver first
creates its log directory and a preflight directory under `.git/poc-loop/` and
probes writes to the Git directory, shared Git directory, objects and branch
refs itself; if any of that fails, the runner is not started. Then it asks the
runner to execute the same probe as an actual shell command and create a fresh
proof file. The runner probe uses the task's runner flags, including
`POC_AGENT_FLAGS` overrides, and times out after 45 seconds. Exit 4 means
infrastructure failed; no task attempt was used. The last probe output is in
`.git/poc-loop/preflight.log` (in the worktree's Git directory for linked
worktrees); stderr shows at most its final 4,000 bytes.

For example, Codex may start and exit successfully while its shell reports:

```text
error building bubblewrap command: app-server socket directory must be a user-owned directory with mode 0700
```

Treat this as a sandbox infrastructure failure. Provision the new environment
and rerun the same loop command there. The preflight must pass before work
starts. A successful probe establishes current access, not future availability.

## Restart after exit 4

Every exit 4, from the driver's own write checks or from the runner probe,
prints the same guidance on stderr, with the actual paths filled in and quoted:

```sh
cd <repo>
POC_AGENT=codex bash <skill-dir>/assets/loop.sh
```

Run these from an independently started terminal in the supported environment
above, not from the restricted session: an already restricted calling process
stays restricted, and runner flags cannot grant it filesystem access. The
message names the runner that was set, and the restart uses that runner's
default flags. Three states stay separate:

1. **Infrastructure stop.** Exit 4 changed nothing: task attempts,
   `plans/prd.json` and the branch are as before, and nothing was repaired.
2. **Restored infrastructure.** Only a preflight that passes in the new
   environment shows this. The loop then continues with the items that are
   still selectable.
3. **Retry of an old blocked item.** Restored infrastructure does not unblock
   it. It needs separate human approval naming the item, then the procedure
   below.

## Human-approved retry of one blocked item

Items already blocked by an older run retain their state: restarting does not
reset them. Once a preflight has passed in the restored environment, obtain
human approval naming the single item to retry, then:

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
