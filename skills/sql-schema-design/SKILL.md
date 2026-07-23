---
name: sql-schema-design
category: architecture
environments: coding
description: Apply module-encapsulation thinking to SQL schema design and query patterns — expose views as the stable public interface, decompose complex queries into named CTE pipelines, hide physical storage (partitioning) behind that interface, and gate deployments with INFORMATION_SCHEMA conformance checks. Use whenever a database schema is being designed or reviewed, a report/application queries tables directly, a query has deep subquery nesting, a table is outgrowing its read pattern, or CI/CD needs to catch schema drift before it reaches consumers.
metadata:
  version: "1.0"
---

# SQL Schema Design

A database schema deserves the same encapsulation discipline as a software module: **consumers should see only a stable logical interface; physical storage is an implementation detail.** This is the deep-module principle — hide complexity behind a simple, durable contract — applied to the database layer instead of to code.

The payoff is the same one deep modules give you: schema evolution stops being a coordinated, multi-team migration. A team that exposes raw tables directly pays for every refactor with breaking changes across every consumer. A team that puts a view layer between tables and consumers can reshape, partition, or relocate tables at will, because the contract — the view's columns, types, and semantics — never moved.

## When to use this

Use it whenever a schema is being designed or reviewed and any of these are true:

- A report, application, or data-science pipeline is about to be pointed at raw tables.
- A query has more than one level of subquery nesting, or the same subquery is written out more than once.
- A table has outgrown its read pattern and is a candidate for splitting.
- More than one person runs migrations against the database, or the database has production consumers.

Skip it for ephemeral notebooks/exploration, single-user single-purpose databases with a short lifespan, and hot OLTP paths where every layer of indirection has a measurable cost — for those, apply Phase 4 (schema conformance checks) selectively and leave the rest.

## The 4-phase workflow

Work through these phases in order. Each phase is independently useful, but phases 2 and 3 assume phase 1 is in place — you can't hide storage behind a view that doesn't exist yet.

### Phase 1 — Define the public interface (views as contract)

Tables stay private: no direct `SELECT` grants for consumers. Every external interface — report, application, data-science pipeline — reads exclusively from views. A view's signature (column names, types, semantics) is the frozen contract, exactly like an interface in object-oriented design.

Side benefit: security becomes granular without row-level-security policies — views mask columns or filter rows on their own.

**Decision rule:** Is a data product used by more than one consumer, or used for more than one quarter? → a view interface is mandatory. Is it a single-user ad-hoc analysis? → direct table access is fine.

### Phase 2 — Decompose query logic with CTEs

Inside a view definition (or inside any report query), break complexity into a linear pipeline of named steps using Common Table Expressions (`WITH step1 AS (...), step2 AS (...) SELECT ... FROM step2`). Each step is understandable in isolation and independently inspectable during debugging: temporarily repoint the statement's final `SELECT` at the step under inspection (e.g. change the closing `SELECT ... FROM step2` to `SELECT * FROM step1`), or copy the `WITH` prefix up to and including that step into a scratch query.

CTE names are scoped to the single statement (statement scope), so CTEs give you the readability of a temp table without the create/drop overhead. This is the SQL equivalent of the stepdown rule: the query reads top-down as a narrative instead of as a nested puzzle the reader has to unwind from the inside out.

**When a CTE beats a subquery — decision rule:** nesting depth is 2 or more subqueries deep, OR the same subquery is referenced more than once in the statement. Either condition on its own is enough to pull the logic out into a named CTE step.

### Phase 3 — Optimize physical storage behind the view

*This phase is aimed at analytical/OLAP schemas* — reporting and analytics workloads where tables grow large and access patterns split into hot/cold or current/historic sets. It is not the priority for OLTP hot paths (see the apply/skip table below).

When a table outgrows its read volume, or its query pattern splits into disjoint row sets, apply view-based table partitioning: split the table horizontally (e.g. `payment_current` + `payment_historic`) and reunite it with a `UNION ALL` view:

```sql
CREATE VIEW payment_all AS
SELECT payment_id, customer_id, amount, paid_at FROM payment_historic
UNION ALL
SELECT payment_id, customer_id, amount, paid_at FROM payment_current;
```

List the columns explicitly in an interface view — precisely because the view is the frozen contract, a `SELECT *` definition would silently move the contract whenever a base table changes shape.

Consumers query `payment_all` exactly as they would a single table — nothing about their queries changes. The query optimizer can often exploit partition pruning, touching only the relevant partition instead of scanning everything.

The partitioning strategy is now an implementation detail and can be changed later (recency-based → by year → by tenant) as long as the view's signature stays constant. This indirection is close to free: views store no data of their own, so the only cost is the `UNION ALL` at query time.

**Decision rule:** apply this when a table grows to more than 10x its read volume, or when the query pattern can be decomposed into disjoint sets of rows (e.g. current vs. historic, hot vs. cold, this-tenant vs. other-tenants).

### Phase 4 — Automate schema conformance checks

Verify every deployment against `INFORMATION_SCHEMA`, the standardized metadata catalog that describes tables, columns, and constraints. Check: do all expected tables and columns exist, with the correct types? Are the expected constraints present? Is the view signature from Phase 1 unchanged? (Index presence is not part of ANSI `INFORMATION_SCHEMA` — check it via engine-specific catalogs such as `pg_indexes`, MySQL's `INFORMATION_SCHEMA.STATISTICS`, or SQL Server's `sys.indexes`.)

Pattern for existence checks:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'mydb' AND table_name = 'expected_table';
-- empty result → deployment failed
```

Pattern for shape checks:

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'customer';
-- compare against the expected schema
```

The value is continuous validation: these checks are the database-side safety net for gradual change. Someone hand-edited a column in production? The next CI run catches the drift instead of a consumer discovering it downstream. As a bonus, the same queries can diff schemas across environments (prod vs. staging), and schema documentation becomes generated rather than hand-maintained — a single source of truth.

**Integration into CI/CD:** deployment script runs the schema migration → validation script queries `INFORMATION_SCHEMA` → assertions compare against the expected state → failure triggers a rollback.

**Decision rule:** as soon as more than one person runs migrations against the database, or the database has production consumers, this phase is non-negotiable.

## When to apply the whole workflow, when not to

| Apply | Skip (or apply selectively) |
|---|---|
| Analytical databases with multiple consumer teams | Ephemeral exploration / notebooks |
| Operational databases with legacy applications whose queries aren't centrally controllable | Single-user, single-purpose databases with a short lifespan |
| Data products that serve as the interface between teams | High-performance OLTP hot paths, where every layer of indirection has a cost — there, apply only Phase 4 (schema validation) selectively |

## Supporting pattern: push work to the data source

A complementary performance principle for any query or pipeline touching this schema: **do as much filtering, grouping, and aggregation as possible at the data source, before transferring rows out.** Data transfer from source to client is usually the slowest step in the pipeline.

```sql
-- Worse: pull everything, filter client-side
SELECT * FROM transactions WHERE user_id = 123;

-- Better: filter and aggregate at the source
SELECT date, SUM(amount) AS daily_total
FROM transactions
WHERE user_id = 123
GROUP BY date;
```

This fits well for simple summary statistics, SQL-native filters/groupings/aggregations, and general data reduction — sending only the rows and columns actually needed. It fits poorly when the data source itself is slow or already overloaded, when the task is a complex ML computation that a SQL engine has no native support for, or when the required algorithm simply isn't available at the source. In those cases, pulling data once and processing it client-side is the better trade.

This principle composes with the 4-phase workflow: views (Phase 1) and CTE pipelines (Phase 2) are exactly the place to push filtering and aggregation down, so consumers receive already-reduced result sets rather than raw tables.

## How this maps to general design principles

This workflow is not database-specific invention — it is a set of established software-design principles instantiated at the schema level:

- **Information hiding / abstraction** — physical table structure disappears behind the view.
- **Facade pattern** — views are facades over the interaction of one or more underlying tables.
- **Seams for incremental change** — views are database-side seams: they let you refactor storage with a safety net instead of a coordinated cutover.
- **High cohesion, low coupling** — each view bundles one coherent consumer need and decouples it from physical structure.
- **Layers with different abstraction levels** — consumers see the semantic layer (views); the DBA works at the physical layer (tables, indexes, partitions).
