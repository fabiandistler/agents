# C4 Best Practices

Condensed from Simon Brown's [c4model.com](https://c4model.com). This page is
the "what makes a C4 diagram good" reference: abstractions, diagram types with
audience guidance, notation rules, and the review checklist.

## Contents

- [The four abstractions](#the-four-abstractions)
- [The diagram types](#the-diagram-types)
- [Diagram review checklist](#diagram-review-checklist)

## The four abstractions

C4 is an *abstraction-first* model: you first agree on the building blocks,
then draw pictures of them. Everything in a C4 model is one of:

| Abstraction | Not this |
|---|---|
| **Person** | Other software |
| **Software System** | A microservice (a microservice is a group of containers, or a software system when a separate team owns it) |
| **Container** | A Docker container per se; a library; a class |
| **Component** | A separately deployable service (that's a container) |

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

## Diagram review checklist

Adapted from c4model.com's review checklist. Run it on every finished diagram:

1. Does the diagram have a **title** describing its type and scope ("Container
   diagram — Web Shop")? Number diagrams if there are several.
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
10. Is there a key/legend explaining shapes, colors, line styles, and arrows?
11. Is the **notation consistent** with the other diagrams of the model?
12. Would the diagram **make sense standalone**, without verbal explanation?
13. Are there **≤ ~20 elements**, and only elements of one abstraction level
    (plus their direct neighbors)?
