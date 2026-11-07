#!/usr/bin/env python3
"""maintenance-r-advisories - flag R dependencies whose DESCRIPTION constraint admits an affected version.

renv::vulns() needs a renv.lock and the Posit Package Manager API, oysteR needs Sonatype
OSS Index, and both need R. A package without renv.lock, or a run environment without R or
without access to those hosts, then audits nothing. This check needs only python3: it
loads the OSV dump of the R Consortium advisory database (ecosystem CRAN, one zip from
storage.googleapis.com) and compares every affected range with the version constraints in
DESCRIPTION.

Checked: each Depends/Imports/Suggests/LinkingTo entry except the base packages. It is
flagged when its constraint admits at least one version inside an affected range: no
constraint (or `!=`) admits every version, `>=` / `>` everything from the bound up,
`<=` / `<` everything below it, `==` exactly one. A flag says the constraint allows an
affected version, not that one is installed; the fix is raising the lower bound to the
fixed version. A range or constraint this check cannot read is printed as "not checked",
never dropped.

Not checked: installed versions, renv.lock (renv::vulns() covers it), transitive
dependencies, Bioconductor and r-universe packages.

Exit codes:
  0  advisories loaded and compared (flags are findings, not failures)
  2  bad arguments
  3  the OSV dump could not be read: the --osv-dump file is missing or unreadable, or
     the dump is not a zip of OSV records - nothing was checked; maintenance-scan.sh
     prints it as "not checked", not as blocked
  6  the OSV dump could not be downloaded (HTTP 403/5xx, DNS, proxy, timeout) - nothing
     was checked; maintenance-scan.sh reports the check as blocked
Plugin-wide exit code table: "## Exit codes" in plugins/repo-maintenance/README.md
(repo fabiandistler/repo-maintenance).

Source: deps-audit blocker from the fmisc maintenance run of 2026-10-28 (no renv.lock,
OSS Index answers 403 in cloud sessions).
Part of: plugin `repo-maintenance`; run by `maintenance-scan.sh deps-audit`.
Needs maintenance-new-deps.py next to it (DESCRIPTION parsing).

Usage:   scripts/maintenance-r-advisories.py [--description DESCRIPTION] [--osv-dump <all.zip>]
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

OSV_CRAN_DUMP_URL = "https://osv-vulnerabilities.storage.googleapis.com/CRAN/all.zip"
TIMEOUT_S = 20

# R's package_version(): integers separated by `.` or `-` (1.2.2-2 equals 1.2.2.2).
VERSION_RE = re.compile(r"\d+(?:[.-]\d+)*")
CONSTRAINT_RE = re.compile(r"(>=|<=|==|!=|>|<)\s*(\S+)")

# DESCRIPTION parsing lives in the new-dependency check; the bootstrap vendors both.
_NEW_DEPS = Path(__file__).with_name("maintenance-new-deps.py")
_spec = importlib.util.spec_from_file_location("maintenance_new_deps", _NEW_DEPS)
assert _spec is not None and _spec.loader is not None  # a .py path always has one
new_deps = importlib.util.module_from_spec(_spec)
sys.modules["maintenance_new_deps"] = new_deps  # dataclasses resolve the module by name
_spec.loader.exec_module(new_deps)


class NotChecked(Exception):
    """A range or constraint this check cannot evaluate; reported per entry."""


Version = tuple[int, ...]


@dataclass(frozen=True)
class Bound:
    version: Version
    inclusive: bool


@dataclass(frozen=True)
class Interval:
    """Versions between low and high; None is unbounded."""

    low: Bound | None
    high: Bound | None


@dataclass(frozen=True)
class Advisory:
    id: str
    summary: str
    aliases: tuple[str, ...]
    ranges: tuple[dict, ...]
    versions: tuple[str, ...]


@dataclass(frozen=True)
class Match:
    dependency: new_deps.RDependency
    advisory: Advisory
    admitted: bool
    # Fixed version of each admitted affected interval; None where there is no fix.
    fixed: tuple[str | None, ...] = ()
    not_checked: str = ""


def parse_version(text: str, where: str) -> Version:
    if not VERSION_RE.fullmatch(text.strip()):
        raise NotChecked(f"{where} is not a version of `.`- or `-`-separated integers")
    return tuple(int(part) for part in re.split(r"[.-]", text.strip()))


def tighter_low(a: Bound | None, b: Bound | None) -> Bound | None:
    if a is None or b is None:
        return a or b
    if a.version != b.version:
        return max(a, b, key=lambda bound: bound.version)
    return a if not a.inclusive else b


def tighter_high(a: Bound | None, b: Bound | None) -> Bound | None:
    if a is None or b is None:
        return a or b
    if a.version != b.version:
        return min(a, b, key=lambda bound: bound.version)
    return a if not a.inclusive else b


def overlaps(a: Interval, b: Interval) -> bool:
    low, high = tighter_low(a.low, b.low), tighter_high(a.high, b.high)
    if low is None or high is None:
        return True
    if low.version != high.version:
        return low.version < high.version
    return low.inclusive and high.inclusive


def admitted_interval(constraint: str) -> Interval:
    """Versions a DESCRIPTION constraint such as `>= 1.2.0` admits."""
    if not constraint:
        return Interval(None, None)
    m = CONSTRAINT_RE.fullmatch(constraint)
    if not m:
        raise NotChecked("constraint is not `<operator> <version>`")
    op, text = m.groups()
    if op == "!=":
        # Excludes one version and narrows nothing else.
        return Interval(None, None)
    bound = Bound(parse_version(text, "constraint version"), op in (">=", "<=", "=="))
    if op in (">=", ">"):
        return Interval(bound, None)
    if op in ("<=", "<"):
        return Interval(None, bound)
    return Interval(bound, bound)


def affected_intervals(advisory: Advisory) -> list[tuple[Interval, str | None]]:
    """Each affected interval with its fixed version (None: no fix, or a listed version)."""
    if not advisory.ranges:
        # OSV allows an explicit version list instead of ranges.
        if not advisory.versions:
            raise NotChecked("advisory has neither ranges nor versions")
        points = [parse_version(v, "listed version") for v in advisory.versions]
        return [(Interval(Bound(p, True), Bound(p, True)), None) for p in points]
    intervals: list[tuple[Interval, str | None]] = []
    for rng in advisory.ranges:
        if rng.get("type") != "ECOSYSTEM":
            raise NotChecked("range type is not ECOSYSTEM")
        low = None
        for event in rng["events"]:
            if "introduced" in event:
                low = Bound(parse_version(event["introduced"], "introduced"), True)
            elif "fixed" in event:
                high = Bound(parse_version(event["fixed"], "fixed"), False)
                intervals.append((Interval(low, high), event["fixed"]))
                low = None
            elif "last_affected" in event:
                high = Bound(
                    parse_version(event["last_affected"], "last_affected"), True
                )
                intervals.append((Interval(low, high), None))
                low = None
            else:
                raise NotChecked(
                    "range event is not introduced, fixed or last_affected"
                )
        if low is not None:
            intervals.append((Interval(low, None), None))
    return intervals


def load_advisories(dump: bytes) -> tuple[dict[str, list[Advisory]], int]:
    """Advisories per CRAN package from the OSV zip, and the number of records read."""
    with zipfile.ZipFile(io.BytesIO(dump)) as zf:
        records = [json.loads(zf.read(n)) for n in zf.namelist() if n.endswith(".json")]
    if not records:
        # The real dump always has records; none means the format changed.
        raise ValueError("no advisory records in the dump")
    by_package: dict[str, list[Advisory]] = defaultdict(list)
    for rec in records:
        if rec.get("withdrawn"):
            continue
        for affected in rec["affected"]:
            package = affected["package"]
            if package.get("ecosystem") != "CRAN":
                continue
            by_package[package["name"]].append(
                Advisory(
                    id=rec["id"],
                    summary=rec.get("summary", ""),
                    aliases=tuple(rec.get("upstream", []) + rec.get("aliases", [])),
                    ranges=tuple(affected.get("ranges", [])),
                    versions=tuple(affected.get("versions", [])),
                )
            )
    return by_package, len(records)


class OsvDumpUnreachable(Exception):
    """The OSV dump host did not deliver the dump; the run environment lacks access."""


def download_osv_dump() -> bytes:
    """The OSV CRAN dump, fetched from storage.googleapis.com."""
    # Fixed https URL, no user input: bandit B310 does not apply.
    req = urllib.request.Request(
        OSV_CRAN_DUMP_URL, headers={"User-Agent": "maintenance-r-advisories"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # nosec B310
            return resp.read()
    except (OSError, http.client.HTTPException) as exc:
        # URLError (HTTP 403/5xx, DNS, proxy) and TimeoutError are OSErrors; a
        # connection cut while reading raises HTTPException (IncompleteRead).
        raise OsvDumpUnreachable(f"{type(exc).__name__}: {exc}") from exc


def match_dependency(dep: new_deps.RDependency, advisory: Advisory) -> Match:
    try:
        admitted = admitted_interval(dep.constraint)
        fixed = tuple(
            f for iv, f in affected_intervals(advisory) if overlaps(admitted, iv)
        )
    except NotChecked as exc:
        return Match(dep, advisory, admitted=False, not_checked=str(exc))
    return Match(dep, advisory, admitted=bool(fixed), fixed=fixed)


def check(
    deps: list[new_deps.RDependency], advisories: dict[str, list[Advisory]]
) -> list[Match]:
    return [match_dependency(d, a) for d in deps for a in advisories.get(d.package, [])]


def describe(m: Match) -> str:
    dep, adv = m.dependency, m.advisory
    declared = f"{dep.package} ({dep.constraint})" if dep.constraint else dep.package
    ids = ", ".join((adv.id, *adv.aliases))
    head = f"{dep.field}: {declared} - {ids} {adv.summary}".rstrip()
    affected = "; ".join(
        ", ".join(
            f"{kind} {value}"
            for event in rng["events"]
            for kind, value in event.items()
        )
        for rng in adv.ranges
    ) or "versions " + ", ".join(adv.versions)
    if m.not_checked:
        return f"NOT CHECKED  {head}\n  {m.not_checked}"
    if not m.admitted:
        return f"ok           {head}\n  affected: {affected} - not admitted by the constraint"
    if None in m.fixed:
        fix = "no fixed version for an admitted range"
    else:
        # Narrows the type only: the branch above already ruled out None.
        fixed = (f for f in m.fixed if f is not None)
        latest = max(fixed, key=lambda f: parse_version(f, "fixed"))
        fix = f"raise the lower bound: {dep.package} (>= {latest})"
    return (
        f"FLAG         {head}\n  affected: {affected} - DESCRIPTION admits them; {fix}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--description", default="DESCRIPTION", help="default: ./DESCRIPTION"
    )
    ap.add_argument(
        "--osv-dump", help="local copy of the OSV CRAN all.zip (tests, offline)"
    )
    args = ap.parse_args(argv)

    deps = new_deps.r_dep_entries(Path(args.description).read_text(encoding="utf-8"))
    try:
        dump = (
            Path(args.osv_dump).read_bytes() if args.osv_dump else download_osv_dump()
        )
        advisories, n_records = load_advisories(dump)
    except OsvDumpUnreachable as exc:
        print(
            f"blocked: OSV CRAN dump unreachable at {OSV_CRAN_DUMP_URL} ({exc}). "
            "Nothing was checked.",
            file=sys.stderr,
        )
        return 6
    except (
        OSError,
        zipfile.BadZipFile,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"not checked: OSV CRAN advisories not loaded ({type(exc).__name__}: {exc}). "
            "Nothing was checked.",
            file=sys.stderr,
        )
        return 3

    matches = check(deps, advisories)
    flagged = [m for m in matches if m.admitted or m.not_checked]
    print(
        f"{n_records} OSV CRAN advisories, {len(deps)} DESCRIPTION entries, "
        f"{len(matches)} advisories for them, {len(flagged)} flagged or not checked."
    )
    order = sorted(
        matches, key=lambda m: (not m.not_checked, not m.admitted, m.dependency.package)
    )
    for m in order:
        print(describe(m))
    if not matches:
        print("No published advisory for any DESCRIPTION entry.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
