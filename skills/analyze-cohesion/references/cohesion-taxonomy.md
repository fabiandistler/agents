# Cohesion taxonomy and the LCOM metric

Reference material for the `analyze-cohesion` skill. Read this when you need
the precise definition of a cohesion type, the worked trade-off example, or
the details of the LCOM metric. The source is the *Cohesion* section of
Richards & Ford, *Fundamentals of Software Architecture* (O'Reilly).

## Contents

- [What cohesion is](#what-cohesion-is)
- [The seven types, best to worst](#the-seven-types-best-to-worst)
- [Worked example: when to split a module](#worked-example-when-to-split-a-module)
- [The LCOM metric](#the-lcom-metric)
- [What LCOM cannot tell you](#what-lcom-cannot-tell-you)
- [Cohesion is not an object-oriented idea](#cohesion-is-not-an-object-oriented-idea)

## What cohesion is

Cohesion refers to the extent to which a module's parts should be contained
within the same module. It measures how related the parts are to one another.
An ideal cohesive module is one where all parts are packaged together; breaking
them into smaller pieces would require coupling the parts together (via calls
between modules) to achieve useful results.

The cautionary tale of modularity is that you can take cohesion too far. From
Larry Constantine, who originated the concept in *Structured Design*:

> Attempting to divide a cohesive module would only result in increased
> coupling and decreased readability.

That tension — too little cohesion scatters related work, too much splitting
re-couples it — is why the right answer is so often "it depends." The job is to
find the dominant relationship binding a module's parts and judge whether it is
strong enough to justify keeping them together.

## The seven types, best to worst

Computer scientists have defined a range of cohesion, measured from best to
worst. When you analyze a module, identify which type *dominates* — the
strongest relationship that actually holds the parts together.

### Functional cohesion *(best)*

Every part of the module is related to the other, and the module contains
everything essential to function. This is the target: the parts are there
because the module's single job requires them.

### Sequential cohesion

Two parts interact: one outputs data that becomes the input for the other. A
pipeline of steps where each feeds the next.

### Communicational cohesion

Two parts form a communication chain in which each operates on the same
information and/or contributes to some output. For example, one adds a record
to the database and the other generates an email based on that information.

### Procedural cohesion

Two parts must execute code in a particular order. They are grouped because of
sequencing, not because they operate on the same data.

### Temporal cohesion

Parts are related based on timing dependencies. For example, many systems have
a list of seemingly unrelated things that must be initialized at system
startup; these different tasks are *temporally cohesive* — bound only by *when*
they run.

### Logical cohesion

The parts are related logically but not functionally. For example, a module
that converts information from text, serialized objects, or streams into some
other format. The operations are related as a category ("conversions"), but the
functions are otherwise quite different. A common example is a `StringUtils`
grab-bag: a group of static methods that operate on `String` but are otherwise
unrelated.

### Coincidental cohesion *(worst)*

The parts are unrelated other than being in the same source file. This is the
most negative form of cohesion.

## Worked example: when to split a module

Cohesion is a less precise metric than coupling. Often, a module's degree of
cohesion is determined at the discretion of a particular architect. Consider
this module definition:

```
Customer Maintenance
  - add customer
  - update customer
  - get customer
  - notify customer
  - get customer orders
  - cancel customer orders
```

Should the last two entries reside in this module? Or should the developer
create two separate modules?

```
Customer Maintenance              Order Maintenance
  - add customer                    - get customer orders
  - update customer                 - cancel customer orders
  - get customer
  - notify customer
```

Which is the correct structure? As always, it depends. These three questions
are the trade-off analysis to apply — they are the heart of a software
architect's job:

1. **Are these the only two operations for `Order Maintenance`?** If so, it may
   make sense to collapse those operations back into `Customer Maintenance`.
   A two-method module that will never grow is rarely worth the extra coupling.
2. **Is `Customer Maintenance` expected to grow much larger?** If so, developers
   should look for opportunities to extract behavior into a different (or new)
   module before it becomes a god-module.
3. **Does `Order Maintenance` require so much knowledge of `Customer`
   information that separating the two modules would require a high degree of
   coupling to make it functional?** (This is Constantine's warning: splitting
   a genuinely cohesive module just re-couples the pieces.)

Apply these same questions to any split-or-keep decision. They convert "it
depends" into something you can actually reason about.

## The LCOM metric

Cohesion is subjective, but there is a good structural metric for one part of
it — specifically, *Lack of Cohesion*. The Chidamber and Kemerer
Object-Oriented Metrics Suite measures aspects of object-oriented systems and
includes the **Lack of Cohesion in Methods (LCOM)** metric, which measures the
*structural* cohesion of a module.

### LCOM, version 1

```
LCOM = | |P| - |Q| |, if |P| > |Q|
       | 0,           otherwise
```

`P` increases by 1 for any pair of methods that does **not** access a
particular shared field; `Q` increases by 1 for pairs of methods that **do**
share a field. If this formulation feels confusing, you are not alone — it
became more elaborate over time.

### LCOM96b

A second variation, introduced in 1996 (hence `LCOM96B`):

```
            1   a    m - μ(Aj)
LCOM96b =  --- Σ    -----------
            a  j=1       m
```

where `a` is the number of fields, `m` the number of methods, and `μ(Aj)` the
number of methods that access field `Aj`.

### The plain-English version

The written explanation is clearer than the equations. A good definition of
LCOM is **"the sum of sets of methods not shared via sharing fields."**

Consider a class with private fields `a` and `b`. Many methods only access `a`,
and many other methods only access `b`. The sum of the sets of methods not
shared via sharing fields (`a` and `b`) is high; therefore the class incurs a
high LCOM score, indicating a significant lack of cohesion in methods. Those
two method-sets are evidence that the class is really two classes wearing one
name.

### Figure 3-1: three classes

The book illustrates LCOM with three classes (fields drawn as octagons, methods
as squares):

- **Class X** — every method shares fields with the others; the method/field
  graph is one connected web. LCOM is **low** → good structural cohesion.
- **Class Y** — each method touches its own field and shares nothing with the
  others. The class **lacks cohesion**: every field/method pair could move to
  its own class without affecting the system's behavior.
- **Class Z** — **mixed**: most methods are connected, but one field/method
  combination stands apart and could be refactored into its own class.

The bundled `scripts/lcom.py` reports exactly this picture: a **connected
components** count is the number of "Class Y" style clusters a module breaks
into (1 = like Class X; 2+ = a Class-Y/Z split candidate), alongside the
Chidamber & Kemerer LCOM score.

## What LCOM cannot tell you

LCOM is useful to architects analyzing code bases in order to restructure,
migrate, or understand them. Shared utility classes are a common headache when
moving architectures; LCOM helps find classes that are incidentally coupled and
should never have been a single class to begin with.

But many software metrics have serious deficiencies, and LCOM is not immune.
**All LCOM can find is *structural* lack of cohesion** — methods that don't
happen to share fields. It has no way to determine whether particular pieces
fit together *logically*. This reflects the principle that **why is more
important than how**: two methods can share no field yet clearly belong to the
same concept, and two methods can share a field yet have no business being in
the same module. So:

- A **high** LCOM / multi-component result is a prompt to look closer, not a
  verdict. Ask whether the clusters represent genuinely separate concepts.
- A **low** LCOM does not prove a module is well designed — a class can share
  state everywhere and still mix unrelated responsibilities.

Always finish with the human judgment in the
[worked example's three questions](#worked-example-when-to-split-a-module).

## Cohesion is not an object-oriented idea

LCOM is framed in terms of classes, methods, and fields because that is what
Chidamber & Kemerer measured. But cohesion itself is a property of *any* module
— a function, a file, a package, a service. The underlying question is always
the same: **do these parts belong together, or are they merely colocated?**

For non-OO code, apply the same lens to a **file or namespace of functions**:

- The "methods" are the top-level functions.
- The "shared field" analog is a shared module-level symbol (a script- or
  package-level constant or data object) that the functions read or write, or a
  direct call from one function to another.
- Functions that form one connected cluster are cohesive; functions that fall
  into disjoint clusters suggest the file is a grab-bag (logical or coincidental
  cohesion) that wants splitting.

This is why `scripts/lcom.py` analyzes both a **class** (OO mode) and a **file
of functions** (file mode), and why it is useful for R and Bash code, which are
predominantly function- and script-based rather than class-based.
