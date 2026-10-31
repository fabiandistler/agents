#!/usr/bin/env python3
"""maintenance-new-deps - flag newly added direct dependencies that are unknown or brand-new.

Agents invent package names. A hallucinated name either fails to resolve (harmless) or
resolves to a package someone registered under that name ("slopsquatting"). uv audit,
pip-audit and renv::vulns() only know published advisories, and a fresh squat has none.

This check diffs the direct dependencies against a base revision and looks each NEW one
up in its index:

- Python (pyproject.toml, requirements*.txt): PyPI JSON API
- R (DESCRIPTION Depends/Imports/Suggests/LinkingTo): CRAN package page + CRAN archive

A dependency is flagged when it is not in the index, its first release is younger than
--min-age-days, or it has fewer than --min-releases releases. The output is a report,
never a failure: whether a young package is legitimate is a judgment call.

Not checked: download counts (pypistats is rate-limited and flaky), transitive
dependencies (uv.lock / renv.lock), private indexes (a package from one shows up as
"not on PyPI" - ignore it after checking).

Source: issue #15, fabiandistler/repo-maintenance.
Part of: plugin `repo-maintenance`; run by the workflow `maintenance-new-deps`.

Usage:   scripts/maintenance-new-deps.py --base <git-rev> [--min-age-days 90] [--min-releases 3]

Exit codes:
  0  report written; flags are findings, not failures (a failed index lookup is a flag,
     "not checked", so an unreachable PyPI or CRAN does not fail the report)
  2  bad arguments
  3  environment: the --base revision is not in the clone (checkout without
     fetch-depth 0, or not a Git repo) - nothing was checked
Plugin-wide exit code table: "## Exit codes" in plugins/repo-maintenance/README.md
(repo fabiandistler/repo-maintenance).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess  # nosec B404
import sys
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from fnmatch import fnmatch

PYPI_URL = "https://pypi.org/pypi/{name}/json"
CRAN_DESCRIPTION_URL = "https://cloud.r-project.org/web/packages/{name}/DESCRIPTION"
CRAN_ARCHIVE_URL = "https://cloud.r-project.org/src/contrib/Archive/{name}/"

R_DEP_FIELDS = ("Depends", "Imports", "Suggests", "LinkingTo")
# Shipped with R itself - never on CRAN as separate packages.
R_BASE_PACKAGES = {
    "R",
    "base",
    "compiler",
    "datasets",
    "graphics",
    "grDevices",
    "grid",
    "methods",
    "parallel",
    "splines",
    "stats",
    "stats4",
    "tcltk",
    "tools",
    "utils",
}

PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


@dataclass(frozen=True)
class RDependency:
    field: str
    package: str
    constraint: str


@dataclass
class Result:
    ecosystem: str
    name: str
    first_release: dt.date | None = None
    releases: int | None = None
    notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


# --- reading dependencies -----------------------------------------------------------


def git(*args: str) -> subprocess.CompletedProcess[str]:
    # git from PATH with an argument list, no shell.
    return subprocess.run(  # nosec B603 B607
        ["git", *args], capture_output=True, text=True, check=False
    )


def git_show(rev: str, path: str) -> str | None:
    """File content at rev, or None if the file does not exist there."""
    proc = git("show", f"{rev}:{path}")
    return proc.stdout if proc.returncode == 0 else None


def read_worktree(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def normalize_python(name: str) -> str:
    """PEP 503 normalization, so `Foo_Bar` and `foo-bar` count as the same package."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec: str) -> str | None:
    m = PEP508_NAME.match(spec)
    return normalize_python(m.group(1)) if m else None


def python_deps_pyproject(text: str | None) -> set[str]:
    if not text:
        return set()
    data = tomllib.loads(text)
    specs: list[str] = []
    project = data.get("project", {})
    specs += project.get("dependencies", [])
    for group in project.get("optional-dependencies", {}).values():
        specs += group
    for group in data.get("dependency-groups", {}).values():
        # Entries can be {include-group = "..."} tables; only strings are requirements.
        specs += [s for s in group if isinstance(s, str)]
    names = {requirement_name(s) for s in specs}
    return {n for n in names if n}


def python_deps_requirements(text: str | None) -> set[str]:
    if not text:
        return set()
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        # Options (-r, -e, --index-url), URLs and local paths are not index names.
        if not line or "://" in line or line.startswith(("-", ".", "/")):
            continue
        name = requirement_name(line)
        if name:
            names.add(name)
    return names


def parse_dcf(text: str) -> dict[str, str]:
    """Debian control format as used by DESCRIPTION: continuation lines start with space."""
    fields: dict[str, str] = {}
    key = None
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and key:
            fields[key] += " " + line.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            fields[key] = value.strip()
    return fields


def r_dep_entries(text: str) -> list[RDependency]:
    """One entry per dependency in DESCRIPTION, base packages excluded.

    The constraint is the text inside the parentheses (`>= 1.2.0`), "" when there is none.
    """
    fields = parse_dcf(text)
    entries = []
    for f in R_DEP_FIELDS:
        for entry in fields.get(f, "").split(","):
            name = re.sub(r"\(.*?\)", "", entry).strip()
            if name and name not in R_BASE_PACKAGES:
                constraint = re.search(r"\((.*?)\)", entry)
                entries.append(
                    RDependency(
                        f, name, constraint.group(1).strip() if constraint else ""
                    )
                )
    return entries


def r_deps_description(text: str | None) -> set[str]:
    if not text:
        return set()
    return {dep.package for dep in r_dep_entries(text)}


def r_remotes(text: str | None) -> set[str]:
    """Package names that DESCRIPTION pulls from a non-CRAN source (Remotes field)."""
    if not text:
        return set()
    names = set()
    for entry in parse_dcf(text).get("Remotes", "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        # github::owner/repo@ref, owner/repo, bioc::pkg, url::https://.../pkg.tar.gz
        tail = entry.split("::", 1)[-1].split("@", 1)[0].rstrip("/")
        names.add(tail.rsplit("/", 1)[-1].removesuffix(".tar.gz").split("_", 1)[0])
    return names


def python_files(base: str) -> set[str]:
    """Dependency files at the repo root, in the working tree or at base."""
    patterns = ("pyproject.toml", "requirements*.txt")
    at_base = git("ls-tree", "--name-only", base).stdout.split()
    in_tree = [p for pattern in patterns for p in glob.glob(pattern)]
    return {p for p in [*at_base, *in_tree] if any(fnmatch(p, pat) for pat in patterns)}


def new_python_deps(base: str) -> set[str]:
    before, after = set(), set()
    for path in sorted(python_files(base)):
        parse = (
            python_deps_pyproject
            if path.endswith(".toml")
            else python_deps_requirements
        )
        before |= parse(git_show(base, path))
        after |= parse(read_worktree(path))
    return after - before


def new_r_deps(base: str) -> tuple[set[str], set[str]]:
    before = r_deps_description(git_show(base, "DESCRIPTION"))
    head = read_worktree("DESCRIPTION")
    return r_deps_description(head) - before, r_remotes(head)


# --- index lookups ------------------------------------------------------------------


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "maintenance-new-deps"})
    try:
        # Only the fixed https URLs above, never a user-supplied scheme.
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, ""
    except (urllib.error.URLError, TimeoutError):
        return 0, ""


def not_checked(status: int, what: str = "lookup") -> str:
    reason = f"HTTP {status}" if status else "network error"
    return f"not checked: {what} failed ({reason})"


def check_pypi(name: str) -> Result:
    res = Result("PyPI", name)
    status, body = fetch(PYPI_URL.format(name=name))
    if status == 404:
        res.flags.append("not on PyPI")
        return res
    if status != 200:
        res.flags.append(not_checked(status))
        return res
    data = json.loads(body)
    uploads = {
        version: [dt.datetime.fromisoformat(f["upload_time_iso_8601"]) for f in files]
        for version, files in data.get("releases", {}).items()
        if files
    }
    res.releases = len(uploads)
    if uploads:
        res.first_release = min(min(times) for times in uploads.values()).date()
    if not (data.get("info") or {}).get("project_urls"):
        res.notes.append("no project URLs")
    return res


ARCHIVE_ROW = re.compile(r">[^<]+_[^<]+\.tar\.gz</a>\s+(\d{4}-\d{2}-\d{2})")


def check_cran(name: str) -> Result:
    res = Result("CRAN", name)
    status, body = fetch(CRAN_DESCRIPTION_URL.format(name=name))
    if status == 404:
        res.flags.append("not on CRAN (archived, Bioconductor, r-universe or GitHub?)")
        return res
    if status != 200:
        res.flags.append(not_checked(status))
        return res
    published = parse_dcf(body).get("Date/Publication", "")[:10]
    dates = [dt.date.fromisoformat(published)] if published else []
    # The archive lists every earlier release; it does not exist for a first release.
    status, archive = fetch(CRAN_ARCHIVE_URL.format(name=name))
    if status == 200:
        dates += [dt.date.fromisoformat(d) for d in ARCHIVE_ROW.findall(archive)]
    elif status != 404:
        # Without the archive, age and release count would be understated.
        res.flags.append(not_checked(status, "archive lookup"))
        return res
    res.releases = len(dates)
    res.first_release = min(dates) if dates else None
    return res


def apply_thresholds(
    res: Result, today: dt.date, min_age_days: int, min_releases: int
) -> None:
    if res.first_release is not None:
        age = (today - res.first_release).days
        if age < min_age_days:
            res.flags.append(f"first release {age} days ago (< {min_age_days})")
    if res.releases is not None and res.releases < min_releases:
        res.flags.append(f"{res.releases} release(s) (< {min_releases})")


# --- output -------------------------------------------------------------------------


def report(results: list[Result], min_age_days: int, min_releases: int) -> str:
    flagged = [r for r in results if r.flags]
    lines = ["## New dependencies", ""]
    if not results:
        lines.append("No new direct dependencies.")
        return "\n".join(lines) + "\n"
    lines += [
        (
            f"{len(results)} new direct dependencies, {len(flagged)} flagged (first "
            f"release < {min_age_days} days, < {min_releases} releases, or not in the index)."
        ),
        "",
        (
            "A flag is a question, not a verdict: check that the name is the package you "
            "meant (typo, invented name, lookalike of a popular package) before merging."
        ),
        "",
        "| Package | Index | Finding |",
        "|---|---|---|",
    ]
    for r in sorted(results, key=lambda r: (not r.flags, r.ecosystem, r.name)):
        first = r.first_release.isoformat() if r.first_release else "-"
        releases = r.releases if r.releases is not None else "-"
        finding = (
            "; ".join(r.flags + r.notes) or f"ok (since {first}, {releases} releases)"
        )
        mark = "**flag** " if r.flags else ""
        lines.append(f"| `{r.name}` | {r.ecosystem} | {mark}{finding} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="git revision to diff against")
    ap.add_argument(
        "--min-age-days",
        type=int,
        default=int(os.environ.get("NEW_DEPS_MIN_AGE_DAYS", "90")),
    )
    ap.add_argument(
        "--min-releases",
        type=int,
        default=int(os.environ.get("NEW_DEPS_MIN_RELEASES", "3")),
    )
    args = ap.parse_args(argv)

    if git("rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}").returncode:
        print(
            f"error: base revision {args.base!r} not found (fetch-depth 0?)",
            file=sys.stderr,
        )
        return 3

    today = dt.datetime.now(dt.UTC).date()
    results = [check_pypi(n) for n in sorted(new_python_deps(args.base))]
    r_new, r_remote = new_r_deps(args.base)
    for name in sorted(r_new):
        if name in r_remote:
            results.append(
                Result("Remotes", name, flags=["installed from Remotes, not CRAN"])
            )
        else:
            results.append(check_cran(name))
    for r in results:
        apply_thresholds(r, today, args.min_age_days, args.min_releases)

    text = report(results, args.min_age_days, args.min_releases)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(text)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for r in results:
            if r.flags:
                print(
                    f"::warning title=New dependency {r.name}::{r.ecosystem}: {'; '.join(r.flags)}"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
