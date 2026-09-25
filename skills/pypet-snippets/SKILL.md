---
name: pypet-snippets
category: workflow
description: Curate pypet command snippets — create, find, edit, run and alias them on request, or propose one for recurring terminal commands.
environments: coding
---

# Pypet Snippets

Curate [pypet](https://github.com/fabiandistler/pypet) command snippets
through its CLI. pypet is a small, archived snippet manager: it stores named
shell commands with descriptions, tags and parameters as plain TOML. Only
call its CLI — never modify its package and never hand-edit its store.

## When to use

- Someone asks to save a command as a snippet ("save this as a snippet",
  "create a snippet").
- Someone calls a command annoying or recurring — offer to turn it into a
  snippet.
- The same long command obviously repeats — drop at most a single hint
  offering a snippet. Never create one uninvited, never nag twice for the
  same command.

## Workflow

1. **Dedup first**: run `pypet search "<keyword>"` and `pypet list` before
   proposing anything. If a matching snippet exists, point at it instead of
   creating one.
2. **Propose and wait**: show the command, a one-line description,
   lowercase comma-separated tags, and parameters with defaults where the
   command varies (ports, paths, image names). Redact literal tokens,
   passwords or keys into a `{{param}}` with no default or an `$ENV_VAR`
   and call this out in the proposal. Do nothing until the person
   confirms — this holds for edits too.
3. **Mutate on yes only**:
   `pypet new "<command>" -d "<description>" -t "<tag1,tag2>" -p "name=default:description,..." -a <alias>`
   The `-d`, `-t`, `-p` and `-a` flags are all optional. Use `{{name}}` for
   required and `{{name=default}}` for optional placeholders in the command.
4. **Offer next steps**: a shell alias (`pypet alias list` first to rule
   out a name conflict, then `pypet alias add <id> <name>`, then
   `source ~/.config/pypet/aliases.sh` to activate) for frequent use, or
   show `pypet exec <id> -p -P k=v` for the person to run themselves —
   never execute on their behalf.

## CLI reference

- `pypet list` — table of all snippets (ID, command, description, tags,
  parameters). Never prompts.
- `pypet search "<query>"` — same table filtered by keyword. Never prompts.
- `pypet new "<command>" [-d desc] [-t tags] [-p params] [-a alias]` —
  create; prints the new ID. Never prompts.
- `pypet edit <id> [--command ...] [--description ...] [--tags ...] [--params ...]` —
  update only after a confirmed proposal, same as creation. Never prompts,
  except `edit -f`, which opens `$EDITOR` — never use it.
- `pypet exec <id> [-p] [-c] [-e] [-P name=value ...]` — always pass
  `<id>`; without one it opens a picker. Always confirms before running
  (prints `Aborted!` and exits 0 with stdin closed); `-p` only prints the
  resolved command, `-c` copies it instead of running, `-e` edits first
  (never use it), `-P` fills a parameter without prompting.
- `pypet copy <id> [-P ...]` — always pass `<id>`; without one it opens a
  picker. Copies the resolved command to the clipboard instead of running
  it; never prompts besides the picker.
- `pypet delete <id>` — always pass `<id>`; without one it opens a picker.
- `pypet alias add <id> <name>` / `list` / `show <id>` / `remove <id>` /
  `update` / `setup` — shell shortcuts; parameterized snippets become shell
  functions. `add` prompts on an alias conflict — check `pypet alias list`
  first.

Do NOT use `save-last` / `save-clipboard` (unreliable: history-file lag,
clipboard flakiness), `sync`, or `gen` — outside this skill's loop.

### Non-interactive use

Always pass `<id>` — `exec`, `copy` and `delete` open a picker without
one. Resolve with `pypet exec <id> -p -P k=v`, passing `-P` for every
parameter, and hand the printed command to the person to run themselves.
Never use `exec -e` (edits first) or `edit -f` (opens `$EDITOR`). Before
`pypet alias add <id> <name>`, check `pypet alias list` for conflicts.

## Proposal sources

In order: the current conversation's command, `~/.bash_history` and
`~/.zsh_history` (the current session may not be flushed yet — ask for
`history -a` if a fresh command is missing), `pypet list` for dedup, agent
memory best-effort — skip silently when the host exposes none.

## Safety

- Never store literal tokens, passwords or keys — replace them with a
  `{{param}}` with no default or an `$ENV_VAR` (see step 2). Snippets are
  plaintext TOML that can be pushed to Git with `pypet sync`.
- Never hand-edit `~/.config/pypet/snippets.toml`; always go through
  `pypet new` / `pypet edit`.
- Never execute a command automatically; `pypet exec` asks before running
  and warns on shell operators.
- Pass the snippet command as one quoted argument so pipes and redirects
  survive intact.

## Placeholder pitfalls

pypet also honours the legacy single-brace `{name}` syntax, so every brace
the target program needs for itself — fzf's `{q}`, `awk '{print $1}'` — is
detected as a phantom required parameter. A command containing at least one
real `{{name}}` placeholder is exempt: detection stops at the new syntax and
never falls back. So either add a genuine `{{param=default}}` to the command,
or keep single braces out of it.

Snippets run through a shell, so pipes, `$(...)` and quoting survive — but
the command is stored verbatim. Check it with `pypet list` after creating it;
backslash-heavy paths deserve a second look.
