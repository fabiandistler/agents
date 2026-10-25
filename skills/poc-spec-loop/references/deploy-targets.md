# Deployment targets — Definition of Done

Each target is three lines. Phase 1 copies them into `SPEC.md ## Definition of Done`; the smoke command becomes the `check` of the final prd item. Language × target picks the framework.

- **`package`**
  - Smoke command (`check` of last prd item): Python: `uv build && uv run python -c "import <name>"` · R: `Rscript -e 'devtools::check(error_on="warning")'` · bash: `bats --recursive test/`
  - Required artefact: installable package with README usage block
  - Non-goal: publishing to PyPI/CRAN
- **`http-service`**
  - Smoke command (`check` of last prd item): `docker rm -f t >/dev/null 2>&1; docker build -t app:test . && docker run --rm -d -p 8000:8000 --name t app:test && curl -sf --retry 10 --retry-connrefused --retry-delay 1 localhost:8000/health; rc=$?; docker rm -f t >/dev/null 2>&1; exit $rc` — the container is removed on every path, so a failed attempt never blocks the next one on the name `t`
  - Required artefact: `Dockerfile` (multi-stage, `--target test` runs suite), `/health` endpoint
  - Non-goal: TLS, auth, horizontal scaling
- **`mcp-server`**
  - Smoke command (`check` of last prd item): Python: `npx -y @modelcontextprotocol/inspector@2.8.0 --cli uv run python -m <name> --method tools/list --format json | jq -e '.result.tools | length > 0'` (needs Node; a stdio server ignores `--help` and would wait on stdin) · R/bash: n/a → ask, likely `other`
  - Required artefact: stdio entry point, `tools/list` returns ≥1 tool
  - Non-goal: HTTP transport unless the goal says so
- **`cli`**
  - Smoke command (`check` of last prd item): `<cmd> --help` exits 0 and one golden-path invocation from SPEC.md `## Users` exits 0
  - Required artefact: single entry point, `--help` documents every flag
  - Non-goal: shell completion, packaging for distros
- **`other:<text>`**
  - Smoke command (`check` of last prd item): Phase 1 asks for a smoke command verbatim; refuse to write prd.json without one
  - Required artefact: as stated
  - Non-goal: as stated

Frameworks by language × target:

- **`http-service`**
  - Python: FastAPI
  - R: plumber
  - bash: n/a → ask
- **`mcp-server`**
  - Python: FastMCP (stdio; Streamable HTTP only if the goal says so)
  - R: n/a → ask
  - bash: n/a → ask
- **`cli`**
  - Python: `typer` or stdlib `argparse`
  - R: `docopt`/`optparse` via `Rscript`
  - bash: `getopts`

Docker: `docker build --check .` (BuildKit) plus `hadolint Dockerfile` as the lint line for any target with a Dockerfile.
