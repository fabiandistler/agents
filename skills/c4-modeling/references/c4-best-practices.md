# C4 Best Practices

Condensed from Simon Brown's [c4model.com](https://c4model.com). This page is
the "what makes a C4 diagram good" reference: abstractions, diagram types with
audience guidance, notation rules, and the review checklist.

## The four abstractions

C4 is an *abstraction-first* model: you first agree on the building blocks,
then draw pictures of them. Everything in a C4 model is one of:

| Abstraction | Definition | Examples | Not this |
|---|---|---|---|
| **Person** | A human user of the system | Customer, back-office admin, support agent | Other software |
| **Software System** | Highest level: something that delivers value to users, built by one team or bought | Web shop, CRM, identity provider | A microservice (usually a container) |
| **Container** | A separately **runnable/deployable** unit that executes code or stores data | SPA, mobile app, API service, background worker, database, message broker, file store | A Docker container per se; a library; a class |
| **Component** | A cohesive grouping of related functionality behind a well-defined interface, living **inside** a container; **not** separately deployable | `OrderPlacement`, `EmailNotifier`, a controller + its service | A separately deployable service (that's a container) |

Level 4 (Code: classes, functions) exists in the model but is deliberately
out of scope for hand-drawn diagrams — IDEs generate it better and it goes
stale fastest.

The most common modeling error is conflating container and Docker container.
The test is: *can it be deployed/started on its own?* A PostgreSQL database:
yes → container. A `PaymentService` class inside the API: no → component.

## The diagram types

Core hierarchy (each level zooms into one element of the previous):

| Diagram | Shows | Audience | How often needed |
|---|---|---|---|
| **System Context** | The system as one box, surrounded by its users and neighboring systems | Everyone, including non-technical | Always — the starting point |
| **Container** | Inside one system: apps, services, data stores and how they communicate | Technical people in and around the team | Almost always |
| **Component** | Inside one container: its major structural building blocks | Developers of that container | On demand, per interesting container |
| **Code** (UML class, ER) | Inside one component | — | Rarely; generate, don't draw |

Supplementary:

| Diagram | Shows | Use when |
|---|---|---|
| **System Landscape** | Multiple software systems of an enterprise/domain and their users, no internals | The "how does it all fit together" question spans systems |
| **Dynamic** | A numbered sequence of collaborations for **one** use case / feature / story | A workflow needs explaining (order placement, login flow) |
| **Deployment** | How containers map onto infrastructure (nodes: cloud accounts, clusters, VMs, regions) | Ops, infra reviews, latency/failover discussions |

Audience rule of thumb: Context always, Container almost always, the rest only
when a concrete audience asks a question that diagram answers.

## Notation recommendations

C4 is notation-independent (it is *not* UML), but c4model.com recommends:

- **Title every diagram**, stating type and scope: "Container diagram — Web
  Shop". Number diagrams if there are several.
- **Every element**: name, abstraction type, and a short description — the
  description kills ambiguity ("API Application — Spring Boot — provides
  shop functionality via JSON/HTTPS"). No box without text.
- **Technology choices** explicitly on containers and components, and on
  relationships where not obvious ("JSON/HTTPS", "SQL/TCP", "AMQP").
- **Every relationship labeled** with its purpose — "reads product catalog
  from", never bare lines or a lonely "uses".
- **Unidirectional arrows**, pointing in the direction of the primary
  dependency or data flow; annotate the response direction in words if it
  matters. Double-headed arrows hide who initiates.
- **No unexplained acronyms/abbreviations.** Diagrams travel further than
  their narrator.
- **Shape and color are a supplement, not a code.** The diagram must survive
  black-and-white printing; if color carries meaning, add a legend/key.
- **Consistency across diagrams**: the same element keeps the same name,
  color, and shape everywhere; boundaries (system/container) drawn the same
  way on every level.
- **Size limit**: roughly ≤ 20 elements per diagram. Beyond that, split — a
  Component diagram per container, a Landscape above overloaded Contexts.
- **Diagrams must stand alone.** The test: could someone outside the team
  read it cold and describe the system back correctly?

## Diagram review checklist

Adapted from c4model.com's review checklist. Run it on every finished diagram:

1. Does the diagram have a **title** describing its type and scope?
2. Is the **diagram type** obvious from the title or a label (Context /
   Container / Component / Dynamic / Deployment / Landscape)?
3. Do you know who the **audience** is, and does the level of detail match?
4. Does every **element** have a name, a type, and a description?
5. Are **technology choices** stated for containers, components, and
   deployment nodes?
6. Are all **acronyms and abbreviations** explained (or removed)?
7. Does every **relationship** have a label describing its purpose?
8. Are relationship **technologies/protocols** shown where they matter?
9. Is every line **unidirectional** with a clear primary direction?
10. If **color or shape** carries meaning, is there a key/legend?
11. Is the **notation consistent** with the other diagrams of the model?
12. Would the diagram **make sense standalone**, without verbal explanation?
13. Are there **≤ ~20 elements**, and only elements of one abstraction level
    (plus their direct neighbors)?

## Keeping diagrams alive

- **One model, many views.** Maintain the element/relationship table as the
  source of truth; regenerate diagrams from it. Renames touch one place.
- **Store diagrams as text next to the code** (Mermaid in Markdown) so they
  ride along in PRs and diffs — diagram changes get reviewed like code.
- **Prefer fewer diagrams, updated,** over many diagrams, abandoned. Delete
  diagrams that no longer answer anyone's question.
- **Record the "why" elsewhere.** Diagrams show structure; decisions and
  their rationale belong in ADRs (see the `adr-workflow` skill).
