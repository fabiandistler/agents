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
- [Language-agnostic / build-level](#language-agnostic--build-level)
- [Production / runtime fitness functions](#production--runtime-fitness-functions)

## Java

**JDepend** — the chapter's original metrics tool; understands Java package
structure. Two canonical fitness functions:

Cycle detection (Example 6-2 in the book):

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

**ArchUnit** — the modern special-purpose choice; JUnit-ecosystem tests with
predefined governance rules. Layer governance (Example 6-4):

```java
layeredArchitecture()
    .layer("Controller").definedBy("..controller..")
    .layer("Service").definedBy("..service..")
    .layer("Persistence").definedBy("..persistence..")
    .whereLayer("Controller").mayNotBeAccessedByAnyLayer()
    .whereLayer("Service").mayOnlyBeAccessedByLayers("Controller")
    .whereLayer("Persistence").mayOnlyBeAccessedByLayers("Service");
```

ArchUnit also covers cycles (`slices().should().beFreeOfCycles()`), naming
conventions, annotation rules, and anti-gaming checks such as requiring every
test method to contain at least one assertion.

## .NET

**NetArchTest** — fluent layer/dependency rules as ordinary unit tests
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
including layered-architecture and cycle rules.

## JavaScript / TypeScript

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
failures as build failures. **ts-arch** offers ArchUnit-style assertions
(`filesOfProject().inFolder("ui").shouldNot().dependOnFiles().inFolder("db")`)
inside Jest/Vitest.

## Python

**import-linter** — contracts over the import graph, enforced by a CLI:

```ini
# setup.cfg / pyproject.toml
[importlinter]
root_package = myapp

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    myapp.api
    myapp.services
    myapp.persistence

[importlinter:contract:independence]
name = Feature modules stay independent
type = independence
modules =
    myapp.billing
    myapp.inventory
```

The `layers` contract enforces top-may-use-lower-only; `independence` and
`forbidden` contracts cover cycles and banned dependencies. **pytest-archon**
expresses the same rules as pytest tests
(`archrule("no db in ui").match("myapp.ui*").should_not_import("myapp.persistence*")`)
when the team prefers rules living in the test suite. **pydeps --show-cycles**
works as a quick cycle gate.

## Go

**go-arch-lint** — YAML-declared components and allowed dependencies, checked
by a CLI:

```yaml
# .go-arch-lint.yml
components:
  handler:    { in: internal/handler }
  service:    { in: internal/service }
  repository: { in: internal/repository }
deps:
  handler:    { mayDependOn: [service] }
  service:    { mayDependOn: [repository] }
```

`golangci-lint` with `gochecknoglobals`/`depguard` covers banned imports;
`go list -deps` piped into a small script is a zero-dependency cycle/boundary
check when adding tooling is not an option.

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
