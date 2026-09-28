# Fitness-Function Tooling Catalog

Implementation options per ecosystem, starting with the three examples from
the source chapter, then modern equivalents. Pick the tool that already fits
the project's test stack — a fitness function developers can read and run
locally beats a more powerful one bolted on from outside.

## Contents

- [Java](#java)
- [.NET](#net)
- [JavaScript / TypeScript](#javascript--typescript)
- [Python](#python)
- [Go](#go)
- [PHP](#php)
- [R](#r)
- [Language-agnostic / build-level](#language-agnostic--build-level)
- [Production / runtime fitness functions](#production--runtime-fitness-functions)

## Java

Recommended default: **ArchUnit**.

**ArchUnit** — the modern special-purpose choice; JUnit-ecosystem tests with
predefined governance rules. Layer governance (Example 6-4):

```java
@ArchTest
static final ArchRule layers = layeredArchitecture()
    .consideringAllDependencies()
    .layer("Controller").definedBy("..controller..")
    .layer("Service").definedBy("..service..")
    .layer("Persistence").definedBy("..persistence..")
    .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
    .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller")
    .whereLayer("Persistence").mayOnlyBeAccessedByLayers("Service");
```

Outside the JUnit5 runner the same rule runs as `layers.check(classes)`.

ArchUnit also covers cycles (`slices().should().beFreeOfCycles()`), naming
conventions, annotation rules, and anti-gaming checks such as requiring every
test method to contain at least one assertion.

**JDepend** — historical (unmaintained): the chapter's original metrics tool,
kept because the book's canonical examples use it; new projects should use
ArchUnit above. Cycle detection (Example 6-2 in the book):

```java
public class CycleTest {
    private JDepend jdepend;

    @BeforeEach
    void init() {
        jdepend = new JDepend();
        jdepend.addDirectory("/path/to/project/persistence/classes");
        jdepend.addDirectory("/path/to/project/web/classes");
        jdepend.addDirectory("/path/to/project/thirdpartyjars");
    }

    @Test
    void testAllPackages() {
        Collection packages = jdepend.analyze();
        assertEquals("Cycles exist", false, jdepend.containsCycles());
    }
}
```

Distance from the Main Sequence with a tolerance (Example 6-3; the tolerance
is project-dependent — measure first, then set it):

```java
@Test
void AllPackages() {
    double ideal = 0.0;
    double tolerance = 0.5; // project-dependent
    Collection packages = jdepend.analyze();
    Iterator iter = packages.iterator();
    while (iter.hasNext()) {
        JavaPackage p = (JavaPackage) iter.next();
        assertEquals("Distance exceeded: " + p.getName(),
            ideal, p.distance(), tolerance);
    }
}
```

Baselining legacy code: wrap the rule in a `FreezingArchRule` so current
violations are frozen and only new ones fail the build; remove frozen entries
as the code is cleaned up.

## .NET

Recommended default: **ArchUnitNET**.

**NetArchTest** — stale (no release since 2021): fluent layer/dependency rules as ordinary unit tests
(Example 6-5):

```csharp
// Presentation classes should not depend directly on the repository layer
var result = Types.InCurrentDomain()
    .That()
    .ResideInNamespace("NetArchTest.SampleLibrary.Presentation")
    .ShouldNot()
    .HaveDependencyOn("NetArchTest.SampleLibrary.Data")
    .GetResult()
    .IsSuccessful;
```

**ArchUnitNET** — a .NET port of ArchUnit with the same rule vocabulary,
including layered-architecture and cycle rules. Teams already on NetArchTest
should move to its maintained continuation, **NetArchTest.eNhancedEdition**.

Baselining legacy code: commit the current violation list and fail only on
entries not already on it, shrinking the list as violations are fixed.

## JavaScript / TypeScript

Recommended default: **dependency-cruiser**.

**dependency-cruiser** — declarative rules over the import graph; runs as a
CLI in CI. Cycle detection plus boundary rules:

```js
// .dependency-cruiser.cjs
module.exports = {
  forbidden: [
    { name: "no-circular", severity: "error",
      from: {}, to: { circular: true } },
    { name: "ui-not-into-persistence", severity: "error",
      from: { path: "^src/ui" }, to: { path: "^src/persistence" } },
  ],
};
```

**eslint-plugin-boundaries** / **import/no-cycle** — same governance expressed
inside an existing ESLint setup; good when the team already treats lint
failures as build failures. **ArchUnitTS** (npm `archunit`) offers
ArchUnit-style assertions
(`filesOfProject().inFolder("ui").shouldNot().dependOnFiles().inFolder("db")`)
inside Jest/Vitest. **ts-arch** covers the same ground but shows no release
since 2024-12, so prefer ArchUnitTS for new rules.

Baselining legacy code: generate a known-violations file (`depcruise-baseline`
command, `baseline` reporter) and run CI with `depcruise --ignore-known`, so
only new violations fail the build.

## Python

Recommended default: **import-linter**.

**import-linter** — contracts over the import graph, enforced by a CLI.
pyproject.toml:

```toml
[tool.importlinter]
root_package = "myapp"

[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = [
    "myapp.api",
    "myapp.services",
    "myapp.persistence",
]

[[tool.importlinter.contracts]]
name = "Feature modules stay independent"
type = "independence"
modules = [
    "myapp.billing",
    "myapp.inventory",
]

[[tool.importlinter.contracts]]
name = "No sibling cycles"
type = "acyclic_siblings"
ancestors = ["myapp"]
```

The same contracts in `.importlinter` or `setup.cfg` use `[importlinter]`
and `[importlinter:contract:...]` INI sections.

The `layers` contract enforces top-may-use-lower-only; `independence` forbids
imports in any direction between the listed modules; `acyclic_siblings`
forbids dependency cycles between siblings; `forbidden` covers banned
dependencies. **pytest-archon**
expresses the same rules as pytest tests
(`archrule("no db in ui").match("myapp.ui*").should_not_import("myapp.persistence*").check("myapp")`)
when the team prefers rules living in the test suite. **pytestarch** covers
similar layer and dependency rules as pytest tests, an alternative for the
same preference. **pydeps --show-cycles**
works as a quick cycle gate.

**tach** — component boundaries declared in `tach.toml`, enforced by a
Rust-backed CLI. `tach check` fails the build on undeclared cross-module
imports, `tach check-external` does the same for third-party packages, and
`tach sync` writes the dependencies a codebase already has back into the
config — so an existing project can be pinned as-is and tightened later.
Closer to modular-monolith governance than to a pure import contract; still
pre-1.0 (0.35.x), but the second most used option in this list by a wide
margin.

**ArchUnitPython** — ArchUnit-style fluent rules living in the test suite
rather than in config:
`project_files("src/").in_folder("**/api/**").should_not().depend_on_files().in_folder("**/db/**")`.
Also covers named layers (`project_layers()`), external modules, naming
conventions, LCOM and distance metrics, and PlantUML component-diagram
adherence in one API; zero runtime dependencies, works with pytest or
unittest. Empty matches fail by default, which catches glob typos. Caveat:
first release April 2026, one maintainer, roughly two orders of magnitude
less adopted than import-linter — weigh that before it becomes a build
blocker.

Baselining legacy code: pin current violations with per-contract
`ignore_imports` (import-linter) or `tach sync` (tach), then remove pinned
entries as the code is cleaned up.

## Go

Recommended default: **go-arch-lint**.

**go-arch-lint** — YAML-declared components and allowed dependencies, checked
by a CLI:

```yaml
# .go-arch-lint.yml
version: 3
workdir: internal
components:
  handler:    { in: internal/handler }
  service:    { in: internal/service }
  repository: { in: internal/repository }
deps:
  handler:    { mayDependOn: [service] }
  service:    { mayDependOn: [repository] }
```

`golangci-lint` with `depguard` covers banned imports;
`go list -deps` piped into a small script is a zero-dependency cycle/boundary
check when adding tooling is not an option.

Baselining legacy code: commit the current violation output and fail only
when it grows, tightening the allowed set as violations are fixed.

## PHP

Recommended default: **Deptrac**.

**Deptrac** — layers declared in `deptrac.yaml`, checked by a CLI:

```yaml
parameters:
  paths:
    - ./src
  layers:
    - name: Controller
      collectors:
        - type: className
          regex: .*Controller.*
    - name: Service
      collectors:
        - type: className
          regex: .*Service.*
    - name: Repository
      collectors:
        - type: className
          regex: .*Repository.*
  ruleset:
    Controller:
      - Service
    Service:
      - Repository
    Repository: ~
```

Baselining legacy code: dump current violations with `--formatter=baseline`
into `deptrac.baseline.yaml` and import it from `deptrac.yaml`, so only new
violations fail the build.

## R

Recommended default: **a custom boundary script** — no ArchUnit equivalent
exists for R.

With `box` modules (for example a `rhino` application layout), keep
boundaries with a small script that parses `box::use()` declarations and
fails on forbidden edges, or with a custom `lintr` linter flagging imports
across module boundaries.

Baselining legacy code: commit the current violation output and fail only
when it grows, tightening the allowed set as violations are fixed.

## Language-agnostic / build-level

- **Threshold gates in CI** — any metric a CLI can emit (coverage, bundle
  size, image size, build time, number of TODOs) becomes a fitness function
  the moment CI compares it to a committed threshold and fails on regress.
- **SonarQube quality gates** — cycles, duplication, coverage, and security
  hotspots with pass/fail gates on the analysis.
- **Custom scripts** — a fitness function is *any* objective mechanism; a
  20-line script asserting "no module in `core/` imports from `plugins/`" is
  as legitimate as a framework.

## Production / runtime fitness functions

Modeled on Netflix's Simian Army — governance of characteristics that only
exist in a running system:

- **Chaos engineering** (Chaos Monkey, Latency Monkey, Chaos Kong; today:
  Chaos Toolkit, AWS Fault Injection Service, Gremlin, LitmusChaos) —
  resilience is verified by injecting the failure before reality does. The
  perspective shift: not *if* something breaks, but *when*.
- **Conformity checks** (Conformity Monkey) — continuously assert deployed
  services meet architect-defined rules, e.g. "every service answers health
  checks without errors", "every service exposes required metadata".
- **Security scanning** (Security Monkey) — recurring checks for well-known
  defects: ports that shouldn't be open, misconfigurations, expiring
  certificates. Modern equivalents: cloud-provider config rules
  (AWS Config, Azure Policy), Prowler, ScoutSuite.
- **Cost / hygiene janitors** (Janitor Monkey) — find and remove orphaned
  instances no service routes to anymore; in an evolutionary architecture,
  services get abandoned routinely and idle instances burn money.

These run on a schedule or continuously rather than per-commit; alerting and
auto-remediation take the place of a failing build.
