---
name: software-design
description: Design and validate deep modules that maximize functionality while minimizing interface complexity. Use this when planning APIs, functions, or modules (e.g., R functions, package interfaces) and you want to keep user-facing surfaces small, optimize the 80/20 use case, and hide internal complexity. Includes an interface-first workflow, a practical checklist, validation via mental execution, tests, and performance checks.
metadata:
  version: "1.0"
---

Purpose
- Help agents create “deep modules” with powerful internals and simple, compact interfaces.
- Provide a concrete checklist and workflow to keep interfaces small, defaults smart, and internals flexible.

When to use
- You are designing or refactoring a function, API, component, or R package surface and want:
  - Minimal arguments and mental overhead for common use cases
  - General interfaces that remain stable while internals evolve
  - Clear validation signals (mental execution, interface tests, performance on the 80% case)

Core principles
- Depth = high functionality over low interface cost; reduce system complexity by keeping interfaces small and simple.
- Keep the interface general; solve specifics in the implementation to increase versatility without bloating the surface.
- Optimize the most common use case (80/20); provide intelligent defaults so typical calls “just work”.
- Hide internal complexity and preserve flexibility so implementations can change without breaking the interface.

Step-by-step workflow
1) Interface design (minimize complexity)
- Cover the most frequent use case with minimal parameters; prefer 3–4 core args max, push extras behind... or an options object.
- Keep the interface general; archetypes like fun(mapping, data,...) or DT[i, j, by] encourage breadth with simplicity.
- Provide intelligent defaults so 80% of calls need no extra parameters.

2) Build implementation depth (maximize functionality)
- Hide complexity behind the simple interface; keep specialized optimizations internal.
- Make the common path trivial; expose extension points for edge cases (e.g.,... hooks).
- Preserve internal flexibility so you can switch algorithms without interface changes.

3) Structured design process
- Work interface-first after clarifying the problem and decomposition; ensure consistency with existing module patterns (e.g., ggplot2, data.table).

4) Validation (test depth)
- Mental execution: can a user “run it in their head” from the interface alone?
- Tests: focus on behavior via the public interface (functionality and edge cases).
- Performance: benchmark the 80% case against a baseline; track time/memory trends.

5) Documentation and extensibility
- Document parameters, return values, and examples on the public surface; point to extension points (…, related families).
- Keep families/patterns consistent across modules to aid discoverability and composability.
