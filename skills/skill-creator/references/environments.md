# Runtime environments

The skill-creator's core loop (draft → test → review → improve → repeat) is the same everywhere, but the mechanics differ by runtime. Find your environment below and apply its adaptations. If you're in Claude Code, no adaptations are needed — everything in SKILL.md works as written.

## Contents

- [Claude.ai](#claudeai)
- [Cowork](#cowork)
- [Codex CLI](#codex-cli)
- [OpenCode](#opencode)

---

## Claude.ai

In Claude.ai, the core workflow is the same, but because Claude.ai doesn't have subagents, some mechanics change. Here's what to adapt:

**Running test cases**: No subagents means no parallel execution. For each test case, read the skill's SKILL.md, then follow its instructions to accomplish the test prompt yourself. Do them one at a time. This is less rigorous than independent subagents (you wrote the skill and you're also running it, so you have full context), but it's a useful sanity check — and the human review step compensates. Skip the baseline runs — just use the skill to complete the task as requested.

**Reviewing results**: If you can't open a browser (e.g., Claude.ai's VM has no display, or you're on a remote server), skip the browser reviewer entirely. Instead, present results directly in the conversation. For each test case, show the prompt and the output. If the output is a file the user needs to see (like a .docx or .xlsx), save it to the filesystem and tell them where it is so they can download and inspect it. Ask for feedback inline: "How does this look? Anything you'd change?"

**Benchmarking**: Skip the quantitative benchmarking — it relies on baseline comparisons which aren't meaningful without subagents. Focus on qualitative feedback from the user.

**The iteration loop**: Same as before — improve the skill, rerun the test cases, ask for feedback — just without the browser reviewer in the middle. You can still organize results into iteration directories on the filesystem if you have one.

**Description optimization**: This requires a coder CLI on `$PATH`. The backend is selected via `$CODER_CLI` (default: `claude`; also supports `codex`, `opencode`). Skip it if you're on Claude.ai or anywhere else without a CLI installed.

**Blind comparison**: Requires subagents. Skip it.

**Packaging**: The `package_skill.py` script works anywhere with Python and a filesystem. On Claude.ai, you can run it and the user can download the resulting `.skill` file.

**Updating an existing skill**: The user might be asking you to update an existing skill, not create a new one. In this case:
- **Preserve the original name.** Note the skill's directory name and `name` frontmatter field -- use them unchanged. E.g., if the installed skill is `research-helper`, output `research-helper.skill` (not `research-helper-v2`).
- **Copy to a writeable location before editing.** The installed skill path may be read-only. Copy to `/tmp/skill-name/`, edit there, and package from the copy.
- **If packaging manually, stage in `/tmp/` first**, then copy to the output directory -- direct writes may fail due to permissions.

---

## Cowork

If you're in Cowork, the main things to know are:

- You have subagents, so the main workflow (spawn test cases in parallel, run baselines, grade, etc.) all works. (However, if you run into severe problems with timeouts, it's OK to run the test prompts in series rather than parallel.)
- You don't have a browser or display, so when generating the eval viewer, use `--static <output_path>` to write a standalone HTML file instead of starting a server. Then proffer a link that the user can click to open the HTML in their browser.
- For whatever reason, the Cowork setup seems to disincline the agent from generating the eval viewer after running the tests, so just to reiterate: whether you're in Cowork or in Claude Code, after running tests, you should always generate the eval viewer for the human to look at examples before revising the skill yourself and trying to make corrections, using `generate_review.py` (not writing your own boutique html code). Sorry in advance but I'm gonna go all caps here: GENERATE THE EVAL VIEWER *BEFORE* evaluating inputs yourself. You want to get them in front of the human ASAP!
- Feedback works differently: since there's no running server, the viewer's "Submit All Reviews" button will download `feedback.json` as a file. You can then read it from there (you may have to request access first).
- Packaging works — `package_skill.py` just needs Python and a filesystem.
- Description optimization (`run_loop.py` / `improve_description.py`) should work in Cowork just fine since it uses the configured `$CODER_CLI` via subprocess, not a browser, but please save it until you've fully finished making the skill and the user agrees it's in good shape. Note: trigger detection (`run_eval.py`) fully supports only the `claude` backend; `codex` is experimental and `opencode` is unsupported.
- **Updating an existing skill**: The user might be asking you to update an existing skill, not create a new one. Follow the update guidance in the Claude.ai section above.

---

## Codex CLI

Codex supports the same SKILL.md format natively, so the skills you create here work in Codex unchanged. What to adapt when you (the skill-creator) are running *inside* Codex:

**Where skills live**: Codex reads skills from `$CODEX_HOME/skills` (default `~/.codex/skills`), from `.agents/skills/` in the current repo (scanned from the working directory up to the repo root), from `~/.agents/skills/`, and from `/etc/codex/skills`. Symlinked skill folders are followed. Create new skills wherever the user wants them versioned (usually the repo), and install/symlink into one of these locations to activate them.

**Triggering**: Skills appear in Codex's initial skills list (name + description) and trigger implicitly when the task matches the description, or explicitly via a `$skill-name` mention or `/skills`. Note that Codex ships its own built-in system skill also named `skill-creator` — if both are installed, both appear in the selector, so the user may need to pick this one explicitly via the `$` mention.

**Running test cases**: There's no subagent/task tool. Run each with-skill and baseline pair as `codex exec` subprocesses instead: stage the skill in a throwaway project's `.agents/skills/<name>/` directory, run `codex exec --skip-git-repo-check --cd <that-dir> "<eval prompt>"` for the with-skill run and the same command from a skill-less directory for the baseline, saving outputs per the workspace layout in SKILL.md. If subprocesses aren't practical, fall back to the inline approach from the Claude.ai section (and skip baselines).

**Grading and analysis**: Run the grader/comparator/analyzer roles inline — read the corresponding `agents/*.md` file and follow it yourself — or delegate each to a `codex exec` subprocess.

**Reviewing results**: On a local machine `generate_review.py` can open a browser as usual. In a sandboxed or headless setup, use `--static <output_path>` and hand the user the file path.

**Description optimization**: Set `CODER_CLI=codex` (or pass `--backend codex`) and use a Codex model ID for `--model`. The rewrite half is fully supported; trigger detection via `run_eval.py --backend codex` is EXPERIMENTAL — it parses `codex exec --json` events, whose schema may drift across Codex releases. For the most faithful trigger numbers, run the loop with the `claude` backend if the `claude` CLI is available.

**Packaging**: `package_skill.py` just needs Python and a filesystem — works fine.

**Updating an existing skill**: Follow the update guidance in the Claude.ai section above.

---

## OpenCode

OpenCode's skill support is very close to Claude Code's: skills are listed in the native `skill` tool's `<available_skills>` and loaded on demand. Skills you create here work in OpenCode unchanged, with one caveat on frontmatter below.

**Where skills live**: `.opencode/skills/<name>/SKILL.md` (project) and `~/.config/opencode/skills/<name>/SKILL.md` (global). OpenCode also auto-loads Claude-compatible locations (`.claude/skills/`, `~/.claude/skills/`) and agent-compatible ones (`.agents/skills/`, `~/.agents/skills/`) — so a skill installed for Claude Code is already visible to OpenCode.

**Frontmatter caveat**: OpenCode recognizes only `name`, `description`, `license`, `compatibility`, and `metadata` (a string-to-string map). Unknown fields are ignored, so extra keys don't break anything — but don't put load-bearing information in fields OpenCode won't read, and keep `metadata` values plain strings.

**Running test cases**: If subagents are unavailable, run test prompts as `opencode run "<eval prompt>"` subprocesses (staging the skill in the project's `.opencode/skills/`), or fall back to the inline approach from the Claude.ai section.

**Description optimization**: `CODER_CLI=opencode` works for the description-rewrite half (`improve_description.py`); use `provider/model`-style model IDs. Trigger detection (`run_eval.py`) is NOT supported for opencode — it exposes no machine-readable tool-call event stream. Run the trigger evals with the `claude` backend (or experimentally with `codex`) if either CLI is available; otherwise skip trigger evals and rely on manual spot checks.

**Packaging**: `package_skill.py` works fine.

**Updating an existing skill**: Follow the update guidance in the Claude.ai section above.
