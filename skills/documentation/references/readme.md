# README

The README answers two questions in order: *should I use this?* and *how do I
get it working?* Everything else is a link.

## Skeleton

```markdown
# <name>

<One or two sentences: what it is, who it is for, what problem it removes.>

## Quick start

<Copy-pasteable path from nothing to one visible success.>

## Configuration

<Table of settings: name, default, effect. Required ones first.>

## Usage

<The two or three things people actually do, each with a runnable example.>

## Contributing

<How to run tests and what the review expectations are — or a link.>
```

## Section notes

**Title + opening.** Name the concrete problem, not the category. "A CLI that
diffs two OpenAPI specs and fails CI on breaking changes" beats "A tool for API
lifecycle management." If the project has a non-obvious scope boundary, say what
it does *not* do here — it saves the wrong reader ten minutes.

**Quick start.** The bar is five minutes to first success, and *success* means
something the reader can see: output printed, a page served, a test passing.
State the starting assumptions (OS, runtime version, credentials needed) before
the first command, and put install and run in one contiguous block so the whole
thing can be pasted at once.

```console
$ pipx install speccheck
$ speccheck diff examples/v1.yaml examples/v2.yaml
2 breaking changes:
  - DELETE /orders/{id}: removed
  - GET /orders: response.items[].total changed integer -> string
```

**Configuration.** A table beats prose: name, default, what changes when you
change it. Mark required entries. Do not restate every flag — for anything
generated (`--help`, an options schema), link to the generated output rather
than copying it.

**Usage.** Two or three real tasks, not an exhaustive API tour. Each one gets a
runnable example. If a task needs more than ~15 lines to explain, it belongs in
its own doc with a link from here.

**Contributing.** Usually three lines and a link: how to run the tests, how to
run the linter, what the PR expectations are. If a `CONTRIBUTING.md` exists,
this section is just the link.

## Failure modes

- **The quick start assumes the author's machine.** A global tool, an env var
  set in the author's shell, a checked-out sibling repo. Test it from a clean
  container, or at minimum list the assumptions explicitly.
- **The quick start stops before anything runs.** Install instructions followed
  by "see the docs" is not a quick start — the reader never got to success.
- **Motivation buried above the fold.** History, badges, and a philosophy
  paragraph push the install command onto screen two.
- **Copied config tables** that drift from the real defaults within a release.
  Link to the source of truth or generate the table.
