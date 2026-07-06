# Component Identification — Approaches, Examples, and Worksheet

Full detail behind the workflow in `SKILL.md`. Everything here is drawn from
*Fundamentals of Software Architecture*, 2nd ed. (Richards & Ford), ch. 8. Read
the section you need; the worksheet at the end is the reusable artifact.

## Contents

1. [The identification and refactoring cycle](#1-the-identification-and-refactoring-cycle)
2. [The Workflow approach](#2-the-workflow-approach)
3. [The Actor/Action approach](#3-the-actoraction-approach)
4. [The Entity Trap (antipattern)](#4-the-entity-trap-antipattern)
5. [Assigning user stories — worked example](#5-assigning-user-stories--worked-example)
6. [Analyzing roles and responsibilities — worked example](#6-analyzing-roles-and-responsibilities--worked-example)
7. [Analyzing architectural characteristics](#7-analyzing-architectural-characteristics)
8. [Component coupling](#8-component-coupling)
9. [The Law of Demeter](#9-the-law-of-demeter)
10. [Case study: Going, Going, Gone](#10-case-study-going-going-gone)
11. [Component design worksheet](#11-component-design-worksheet)

---

## 1. The identification and refactoring cycle

Creating a logical architecture is a continuous loop of identifying and
restructuring logical components. The architect:

1. Identifies the **initial core components**.
2. Assigns **user stories or requirements** to them.
3. Analyzes each component's **roles and responsibilities** (cohesion).
4. Analyzes the **architectural characteristics** the system must support.
5. **Refines / restructures** the components — then loops.

The loop is deliberate. You know least about the system at the start, so the
first components are a *best guess*. It is better to iterate as you learn than to
try to get everything perfect when you know the least. The cycle applies to
greenfield systems and to any feature added to or changed in an existing system
(a change may add components, alter existing ones, or both — and as roles change,
so does where the code should live).

---

## 2. The Workflow approach

Leverage the major happy-path (non-error) workflows a user takes through the
system, or its main request-processing workflow. Assign a component to each
meaningful step. Not every step yields a *new* component — steps that do the same
job reuse one.

**Example — new order-entry system.** You don't know the detailed requirements
yet, but you know the general order-processing flow:

| # | Workflow step | Component |
|---|---------------|-----------|
| 1 | User browses the catalog of items | `Item Browser` |
| 2 | User places an order | `Order Placement` |
| 3 | User pays for the order | `Order Payment` |
| 4 | Send user an email with order details | `Customer Notification` |
| 5 | Prepare the order | `Order Fulfillment` |
| 6 | Ship the order | `Order Shipment` |
| 7 | Email customer that order has shipped | `Customer Notification` |
| 8 | Track shipment | `Order Tracking` |

Steps 4 and 7 both map to `Customer Notification` — reuse, not duplication. Model
as many major workflows / user journeys as you can and pull components from their
steps. Don't try to model every workflow; focus on the major ones and let the
rest emerge as user stories arrive.

---

## 3. The Actor/Action approach

Identify the major **actors** and the major **actions** each performs, then map
actions to components. Particularly useful when a system has multiple actors. The
**system itself is always an actor**, performing automated functions such as
billing and restocking. As with the Workflow approach, not every action gets its
own component.

**Example — order-entry system, three actors:**

**Customer actor**
- Search for items → `Item Search`
- View the details about an item → `Item Details`
- Place an order → `Order Placement`
- Cancel an order → `Order Cancel`
- Register as a new customer → `Customer Registration`
- Update customer information → `Customer Profile`

**Order packer actor**
- Select the box size → `Order Fulfillment`
- Mark the order as ready for shipment → `Order Fulfillment`
- Ship the order to the customer → `Order Shipment`

**System actor**
- Adjust inventory → `Inventory Management`
- Order more stock from the supplier → `Supplier Ordering`
- Apply payment → `Order Payment`

Selecting the box size and marking ready for shipment both map to `Order
Fulfillment`. The Actor/Action approach generally generates **more** components
than the Workflow approach. Both let the architect identify the initial core
components and how they communicate *before* detailed requirements exist.

---

## 4. The Entity Trap (antipattern)

It is tempting to identify components from the system's entities — `Customer`,
`Item`, `Order` become `Customer Manager`, `Item Manager`, `Order Manager`. Avoid
this. Three reasons:

1. **Ambiguous names that describe no role.** "What does `Order Manager` do?" →
   "it manages orders." Useless. Compare `Validate Order`, whose name states its
   responsibility.
2. **Dumping grounds.** Every bit of order logic — validation, placement,
   history, fulfillment, shipping, tracking — lands in the one `Order Manager`,
   the "kitchen sink" utility class with dozens of unrelated methods.
3. **Coarse-grained and purposeless.** The component does too much; it becomes
   hard to maintain, test, and deploy, and thus unreliable.

**Red-flag suffixes** that signal the trap: **Manager, Supervisor, Controller,
Handler, Engine, Processor.**

**Escape hatch:** if a system genuinely is just CRUD (create/read/update/delete)
over entities with no real business logic, it doesn't need an architecture — use
a CRUD-based framework or a no-code/low-code environment that generates the code
acting on those entities.

---

## 5. Assigning user stories — worked example

Assigning stories fills the empty buckets, giving components concrete
responsibilities. It is iterative — stories are rarely all known up front.

Components identified so far: `Order Placement`, `Order Fulfillment`,
`Order Shipment`, `Inventory Management`.

Three user stories:

- **Customer #1** — "As a customer, I want my order validated to make sure I
  entered everything completely and correctly."
- **Order preparer** — "As the person preparing the order, I want to know what
  size box to use, so I can pack it efficiently."
- **Customer #2** — "As a customer, I want an email each time the order status
  changes, so I always know its state."

Assignments:

| Story | Component | Why |
|-------|-----------|-----|
| Validate the order | `Order Placement` | It's the component the user interacts with to place the order. |
| Determine box size | `Order Fulfillment` | It owns preparing and packing the order. |
| Email on every status change | `Customer Notification` (**new**) | Fits none of the four cleanly; three components would otherwise duplicate the email code. |

Because the emailing story spans `Order Placement`, `Order Fulfillment`, and
`Order Shipment`, and the code has to live in one directory/namespace,
duplicating it three times is wrong. Create `Customer Notification` and have the
three components communicate with it. When a story fits no component cleanly,
that is the signal to add one.

---

## 6. Analyzing roles and responsibilities — worked example

Ensure each component's assigned work belongs together and that it isn't doing
too much. The concern is **cohesion**: how, and how much, a component's
operations interrelate. Components drift toward doing too much over time even when
the operations are loosely related.

Suppose `Order Placement` has accumulated these responsibilities:

- Validate the order (all fields entered and correct).
- Display the shopping cart (descriptions, quantities, prices).
- Determine the correct shipping address.
- Collect payment information.
- Generate a unique order ID.
- Apply payment for the order.
- Adjust inventory counts for the items ordered.
- Email the customer an order summary.

Its role-and-responsibility statement reads:

> This component is responsible for validating the order **and** displaying the
> valid shopping cart… It is **also** responsible for determining the shipping
> address, **as well as** collecting payment information. **In addition**, it is
> **also** responsible for applying the payment, adjusting inventory, **and**
> emailing the customer the order summary.

**The conjunction test:** the pile-up of *and*, *also*, *as well as*, *in
addition*, and commas is the tell that the component carries too much —
particularly applying payment, adjusting inventory, and emailing. A component is
one namespace/directory, so this is also just too much code in one place.

Split it — move the strayed responsibilities into their own components:

| Component | Responsibilities after split |
|-----------|------------------------------|
| `Order Placement` | Validate the order; display the shopping cart; determine shipping address; collect payment information; generate a unique order ID. |
| `Payment Processing` | Apply payment. |
| `Inventory Management` | Adjust inventory counts for items ordered. |
| `Customer Notification` | Email the customer an order summary. |

Each now has a clearer, more distinct role and is easier to maintain, test, and
deploy. For a metric-backed decision on a borderline case, use `analyze-cohesion`.

---

## 7. Analyzing architectural characteristics

The final analysis step: consider the architecture characteristics the system
must support — scalability, reliability, availability, fault tolerance,
elasticity, agility (the ability to respond quickly to change). These can change
a component's size.

- Breaking a large, high-responsibility component into smaller ones improves
  agility (easier to maintain and test), scalability, elasticity, and fault
  tolerance.
- Two parts of a system may handle the same *kind* of work (say, user input) but
  at very different scales — one serving hundreds of concurrent users, the other
  a handful. A purely functional view would give them one component; the
  differing characteristics argue for splitting them.

This step assumes you already know which architecture characteristics matter most
to the system — determine those first, then run this pass.

---

## 8. Component coupling

Components are **coupled** when they communicate, or when a change to one may
impact another. More coupling → harder to maintain and test → pay attention to it.

### Static coupling

Synchronous communication between components. Two directions:

- **Afferent coupling (Cᴀ)** — *incoming* / fan-in: how many other components
  depend on this one. `Customer Notification` is called by both `Order Placement`
  and `Order Shipment` to email the customer → Cᴀ = 2.
- **Efferent coupling (Cᴇ)** — *outgoing* / fan-out: how many components this one
  depends on. `Order Placement` depends on `Order Fulfillment` → Cᴇ = 1.

### Temporal coupling

Non-static dependencies based on timing or transactions (single units of work).
When processing an order, `Order Placement`'s functionality must run before
`Order Shipment`'s — they are temporally coupled. Current tooling rarely detects
this; it usually surfaces from design documents or shows up through error
conditions. Note it explicitly during design.

For coupling **metrics on realized code** — instability, abstractness, distance
from the main sequence, zones of pain/uselessness — use `analyze-coupling`.

---

## 9. The Law of Demeter

Also the **Principle of Least Knowledge**: a component or service should have
limited knowledge of other components or services. (Demeter, the Greek goddess,
produced all the world's grain but had no idea what people did with it — decoupled
from the rest of the world.)

**Before.** On accepting an order, `Order Placement`:

- tells `Inventory Management` to decrement inventory, and
- if stock is too low, tells `Supplier Ordering` to reorder, and
- tells `Item Pricing` to adjust the price for limited supply, and
- tells `Email Notification` to email the customer.

`Order Placement` doesn't *perform* these actions, but it *knows they must
happen* — and more knowledge means tighter coupling. It is highly coupled to the
rest of the system.

**After.** Distribute the knowledge. The decrement-inventory coupling must stay
(inserting a middle component wouldn't change `Order Placement`'s efferent count).
But the knowledge that "low stock → reorder *and* reprice" can be **deferred to
`Inventory Management`**, which already owns inventory. `Order Placement` no
longer needs to know about `Supplier Ordering` or `Item Pricing`, lowering its
coupling.

**The honest trade-off.** Applying the Law of Demeter reduced `Order Placement`'s
coupling but **raised `Inventory Management`'s**. It does not necessarily reduce
system-wide coupling; it **redistributes** it. Move knowledge to where it belongs,
don't just push a number down on one node.

---

## 10. Case study: Going, Going, Gone

With no special constraints and a need for a good general-purpose decomposition,
the **Actor/Action approach** works well as a generic solution.

**Actors and actions** for the GGG online-auction system:

- **Bidder** — view live video stream; view live bid stream; place a bid.
- **Auctioneer** — enter live bids into system; receive online bids; mark item
  as sold.
- **System** — start auction; make payment; track bidder activity.

**Initial component set** (each role/action maps to a component; they collaborate
to share information):

| Component | Responsibility |
|-----------|----------------|
| `Video Streamer` | Streams a live auction to users. |
| `Bid Streamer` | Streams bids to users as they occur. (With `Video Streamer`, gives bidders a read-only view of the auction.) |
| `Bid Capture` | Captures bids from the auctioneer and bidders. |
| `Bid Tracker` | Tracks bids; acts as the system of record. |
| `Auction Session` | Starts an auction; on a win/auction-end, triggers payment and resolution, including notifying bidders of the next item. |
| `Payment` | Third-party payment processor for credit-card payments. |

**Characteristics-driven refactor.** After the first round, analyze the
previously identified architecture characteristics. `Bid Capture` handles bids
from both bidders and the auctioneer — functionally fine, since a bid is a bid.
But the characteristics differ sharply:

- **Bidders** could number in the thousands → need high **scalability** and
  **elasticity**.
- The **auctioneer** is a single critical connection → needs high **reliability**
  (connection must not drop) and **availability** (must stay up). A bidder
  dropping is bad; the auctioneer dropping is disastrous.

So split `Bid Capture` into **`Bid Capture`** (bidders) and **`Auctioneer
Capture`** (auctioneer). Wire `Auctioneer Capture` to `Bid Streamer` (to show
online bidders the live bids) and to `Bid Tracker` (to manage the streams).
`Bid Tracker` now unifies two very different streams: the auctioneer's single
stream and the many bidder streams.

This is not the final design — account registration, payment administration, and
more are still to be uncovered — but it's a good starting point to iterate from.
There is rarely one true design; assess trade-offs as objectively as you can and
choose the one with the **least-worst** set.

---

## 11. Component design worksheet

Copy and fill this in per system or feature. Iterate it — it is a snapshot of the
current loop, not a final artifact.

```markdown
# Logical components: <system / feature>

## Approach
- Chosen: <Workflow | Actor/Action>  — why: <one line>
- Actors (if Actor/Action, include the System actor): <...>
- Major workflows (if Workflow): <...>

## Components
| Component | Role / responsibility (one sentence, passes the conjunction test) | Assigned stories / requirements | Cᴀ (fan-in) | Cᴇ (fan-out) | Notes |
|-----------|-------------------------------------------------------------------|---------------------------------|------|------|-------|
|           |                                                                   |                                 |      |      |       |

## Entity-Trap check
- Any component named *Manager / Handler / Processor / Engine / Controller /
  Supervisor? Rename to a role, or split.  [ ] clear

## Cohesion pass (roles & responsibilities)
- Any role statement leaning on and / also / as well as / in addition / commas?
  → split candidate: <component> → <new components>

## Coupling pass
- Static: components with high fan-out (Cᴇ) to review: <...>
- Temporal: ordering dependencies (X must run before Y): <...>

## Law of Demeter pass
- Any component that *knows too much* about what must happen next?
  <component> → defer knowledge to <downstream component>
  (note where the coupling moves *to*)

## Architecture-characteristics pass
- Driving characteristics: <scalability / reliability / availability / ...>
- Splits they force: <component> → <...> because <characteristic mismatch>

## Next iteration / open questions
- <requirements still to uncover, decisions to revisit>
```
