# Contributing

This page is the end-to-end checklist for changing this repository. The rules
behind each step are in [`AGENTS.md`](../AGENTS.md); this page only puts them in
order. Vocabulary lives in [`GLOSSARY.md`](../GLOSSARY.md), and the records of
why the repo is shaped this way are in the [ADR index](adr/README.md).

## Contents

- [Add a skill](#add-a-skill)
- [Change an instruction or plugin](#change-an-instruction-or-plugin)
- [Regenerate generated files](#regenerate-generated-files)
- [Run checks](#run-checks)
- [Open the pull request](#open-the-pull-request)

## Add a skill

1. **Create the skill directory and its frontmatter.** `name` must match the
   directory, `category` must be one of the six values in `CATEGORIES`
   (`scripts/catalogue.py`; `scripts/quick_validate.py` mirrors the list), and
   `description` must fit the budget described in `AGENTS.md`. The other
   frontmatter fields (`activation`, `when_to_use`, `environments`, `targets`,
   `metadata.version`, `argument-hint`, `compatibility`) are documented there
   too.

   ```bash
   mkdir skills/<name>
   $EDITOR skills/<name>/SKILL.md
   ```

2. **Add eval prompts for an auto or router skill.** `skills/<name>/evals.json`
   needs at least three `should_trigger` prompts and one `should_not_trigger`
   prompt, plus an optional `expected_behavior`. Command skills are exempt and
   may skip the file.

3. **Mark a command skill in every runtime.** Set `activation: command` and
   `disable-model-invocation: true`, add the opencode metadata, and commit the
   Codex sidecar:

   ```yaml
   activation: command
   disable-model-invocation: true
   metadata:
     opencode/slash: "true"
     opencode/autoinvoke: "false"
   ```

   ```yaml
   # skills/<name>/agents/openai.yaml
   policy:
     allow_implicit_invocation: false
   ```

   Add `argument-hint` when the command takes an argument.

4. **Link a new top-level skill into its plugin.** For a skill that is not a
   router member, create the relative symlink:

   ```bash
   ln -s ../../../skills/<name> plugins/<category>/skills/<name>
   ```

   Skip this when `targets:` excludes `claude`: the plugins are the Claude
   distribution, and `scripts/check_plugins.py` knows that rule.

5. **Do not link a router member.** A member stays a normal directory under
   `skills/` and carries the router's `category`. Membership is selected by
   `category` plus `activation: auto`: every auto skill in that category is
   nested, while command skills in the same category stay top-level.
   `scripts/build_routers.py` creates `skills/<router>/members/<name>` and the
   generated member table, so do not create either by hand, and do not add a
   plugin symlink for the member.

6. **Register a new router or category everywhere.** Create the router skill
   named after the category with `activation: router` and the
   `<!-- BEGIN generated:members -->` / `<!-- END generated:members -->`
   markers that `build_routers.py` fills; add the category to `CATEGORIES` in
   `scripts/catalogue.py`, the mirrored list in `scripts/quick_validate.py`,
   and the `CATEGORIES` string in `install.sh`; then add
   `plugins/<category>/.claude-plugin/plugin.json`, its `skills/` directory,
   and the marketplace entry.

7. **Add the catalogue rows.** Append the skill to both tables in
   `README.md` and `AGENTS.md` under the section matching its `category`, with
   identical text. With a new category, add the section to both tables first.
   Router skills get no row; their members do. CI enforces parity with
   `scripts/check_docs.py`.

8. **Update plugin descriptions when the scope changed.** The description in
   `plugins/<category>/.claude-plugin/plugin.json` and the matching entry in
   `.claude-plugin/marketplace.json` are separate hand-written copies. Keep
   them identical. No check compares the prose.

9. **Regenerate the generated files.** Run the three generators in the order in
   [Regenerate generated files](#regenerate-generated-files).

10. **Check and stage.** Run the skill-related subset, then stage the generated
    files as well as the source:

    ```bash
    scripts/check_all.sh --only manifest,routers,descriptions,frontmatter,docs,plugins,evals,project-claude,skill-refs,skill-paths
    git status
    ```

## Change an instruction or plugin

- **Instruction fragments** live in `instructions/`, named `NN-slug.md` and
  ordered by the numeric prefix. The 70 and 85 payloads live in
  `instructions/on-demand/`; 80's payload lives in
  `skills/llm-application-engineering/references/agent-pipelines.md`. Edit the
  source the pointer names, regenerate the `.claude/` mirror, then run
  `scripts/check_all.sh --only instructions,project-claude`. The on-demand
  payloads are not validated by `check_instructions.py`, so keep the pointer and
  the payload consistent by hand.
- **Plugins** are one directory per category plus the two hook-only plugins.
  The manifest is `.claude-plugin/marketplace.json`; each plugin has
  `.claude-plugin/plugin.json`, its `skills/` symlinks and optional `agents/`.
  `merge-guard` and `secret-guard` ship only `hooks/hooks.json` and must carry
  no skills or agents. After a change, run
  `scripts/check_all.sh --only plugins,project-claude`.
- **Plugin subagents** need YAML frontmatter with `name` matching the filename
  stem and a `description`. `install.sh` renders them into the Codex and
  opencode agent directories, and `build_project_claude.py` mirrors them into
  `.claude/agents/`.

## Regenerate generated files

Run these from the repo root, in this order:

```bash
python3 scripts/build_manifest.py
python3 scripts/build_routers.py
python3 scripts/build_project_claude.py
```

`build_manifest.py` writes `skills.json`; `build_routers.py` writes the router
member symlinks and member tables; `build_project_claude.py` writes the
`.claude/` mirror. The prek commit hooks do the same on a commit that touches a
`SKILL.md`, an instruction fragment or a plugin subagent. A deletion does not
trigger them, so regenerate by hand after removing a skill. Each generator has
a `--check` form, which is what CI runs.

## Run checks

`scripts/check_all.sh --list` shows every check and the tools it needs. The
fast loop for a docs or plugin change is:

```bash
scripts/check_all.sh --only docs,plugins
```

Run the whole list before opening a pull request:

```bash
scripts/check_all.sh
```

That script is the check list CI runs from `ci.yml`. The PR-only gates,
`pr-issue-links` and `maintenance-gate`, run as separate workflows. A missing
tool reports `MISSING` and exits 3; set `PYTHON=` to a 3.11+ interpreter if the
default is older.

## Open the pull request

Commit subjects follow Conventional Commits; the `commit-msg` hook runs
`scripts/check_commit_msg.py`. Keep a refactor in its own commit, and include
tests with the change they cover.

The PR body names its issue with `Closes #n`. When there is no issue, say so
explicitly. Open the PR ready for review: only the human merges.
