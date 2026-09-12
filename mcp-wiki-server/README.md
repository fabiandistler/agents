# MCP Wiki Server

An MCP server that exposes a wiki / knowledge base to AI agents. Each top-level
folder under the wiki root becomes its own tool, so the agent can see the
available domains directly from the tool list and pull only what it needs into
context.

```
wiki/sql/    -> tool  wiki_sql
wiki/python/ -> tool  wiki_python
wiki/git/    -> tool  wiki_git
```

## Tool semantics

Every topic tool accepts the same two optional arguments:

| call                                | returns                                              |
| ----------------------------------- | ---------------------------------------------------- |
| `wiki_sql()`                        | Table of contents for the topic (filename + summary) |
| `wiki_sql(query="JOIN")`            | Matching lines across all pages with `file:line`     |
| `wiki_sql(page="joins.md")`         | Full page contents (truncated at 8 KB)               |

## Configuration

The server reads its wiki source from environment variables.

### Local folder (default)

```bash
WIKI_PATH=/absolute/path/to/wiki
```

If unset, defaults to `./wiki` next to `server.py` (the bundled demo).

### Remote git repo

```bash
WIKI_GIT_URL=https://github.com/<org>/<wiki-repo>
WIKI_GIT_BRANCH=main           # optional, defaults to "main"
WIKI_CACHE_DIR=/tmp/my-wiki    # optional, defaults to system tempdir
```

`WIKI_GIT_URL` takes precedence over `WIKI_PATH`. The repo is cloned shallowly
on first run and refreshed with `git pull --ff-only` on every start after that,
so a long-lived cache does not serve the wiki frozen at whenever it was first
cloned. A failed refresh (offline, revoked credentials) is reported on stderr
and the cached copy is served as-is; delete the cache dir to force a fresh
clone.

## Running

### MCP Inspector (for testing)

```bash
# The <2 bound matches pyproject.toml — server.py uses the v1 FastMCP API,
# which mcp 2.x renamed. Without it, --with resolves to 2.x and the import fails.
uv run --with "mcp[cli]<2" mcp dev server.py
```

Open the printed URL → confirm `wiki_sql`, `wiki_python`, `wiki_git` appear and
call them with the argument shapes above.

### From Claude Code

Copy `.mcp.json.example` into your project as `.mcp.json` (or merge it into
`~/.claude.json` for global use), restart Claude Code, then run `/mcp` to
verify the connection.

## Relationship to the skills in this repo

None. The `architecture` and `refactoring` plugins used to embed this server
over their skills' `references/` folders; that wiring was removed because it
only duplicated what an agent gets by reading those pages directly. The
skills now rely on plain progressive disclosure, and this server stands on
its own for wikis that live outside a skill.

The server follows directory symlinks, so topic folders under `WIKI_PATH`
may themselves be links.

## Adding your own content

Create a folder under your `WIKI_PATH` and drop Markdown files in it:

```
my-wiki/
  kubernetes/
    deployments.md
    services.md
  terraform/
    modules.md
```

Restart the server. New tools `wiki_kubernetes` and `wiki_terraform` will
appear automatically. Folder names with non-identifier characters are
sanitized: `data-science/` becomes `wiki_data_science`.

Sanitizing maps every non-alphanumeric character to `_`, so sibling folders can
collapse onto one tool name — `sql-1/` and `sql_1/` both become `wiki_sql_1`.
The server registers the first and skips the rest, naming the collision on
stderr; rename one of them.

## Limits

- Pages are truncated at 8000 characters per fetch.
- Search returns at most 20 hits per call.
- Path traversal via `page=../...` is blocked.
- Only `*.md` files are indexed.
