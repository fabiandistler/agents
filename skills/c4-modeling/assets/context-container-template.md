# Architecture — <System Name>

<!--
Copy-paste starting point for a C4 model document (e.g. docs/architecture/).
Replace the Web Shop example with your system. Editing rule: change the
model tables first, then re-derive the diagrams from them — never edit a
diagram directly.
-->

## Model

### Elements

| ID | Element | Type | Technology | Description |
|----|---------|------|------------|-------------|
| customer | Customer | Person | — | Buys products via the web shop |
| shop | Web Shop | Software System (in scope) | — | Lets customers browse the catalog and place orders |
| spa | Storefront | Container | React | Browsing and checkout UI in the browser |
| api | Shop API | Container | Spring Boot | Business logic, exposed via JSON/HTTPS |
| db | Shop Database | Container | PostgreSQL | Products, orders, customers |
| payments | Payment Provider | Software System (external) | — | Card and wallet payments |
| mail | E-Mail Service | Software System (external) | — | Transactional e-mail delivery |

### Relationships

| From | To | Purpose | Technology |
|------|----|---------|------------|
| customer | spa | Browses catalog, places orders | HTTPS |
| spa | api | Calls | JSON/HTTPS |
| api | db | Reads/writes | SQL/TCP |
| api | payments | Charges cards via | HTTPS |
| api | mail | Sends order confirmations via | SMTP |

## System Context diagram

Audience: everyone — shows who uses the system and what it talks to.

```mermaid
C4Context
    title System Context diagram — Web Shop

    Person(customer, "Customer", "Buys products via the web shop")
    System(shop, "Web Shop", "Lets customers browse the catalog and place orders")
    System_Ext(payments, "Payment Provider", "Card and wallet payments")
    System_Ext(mail, "E-Mail Service", "Transactional e-mail delivery")

    Rel(customer, shop, "Browses catalog, places orders", "HTTPS")
    Rel(shop, payments, "Charges cards via", "HTTPS")
    Rel(shop, mail, "Sends order confirmations via", "SMTP")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Container diagram

Audience: the team and adjacent technical people — shows the deployable
pieces inside the Web Shop and how they communicate.

```mermaid
C4Container
    title Container diagram — Web Shop

    Person(customer, "Customer", "Buys products via the web shop")

    System_Boundary(shop, "Web Shop") {
        Container(spa, "Storefront", "React", "Browsing and checkout UI")
        Container(api, "Shop API", "Spring Boot", "Business logic via JSON/HTTPS")
        ContainerDb(db, "Shop Database", "PostgreSQL", "Products, orders, customers")
    }

    System_Ext(payments, "Payment Provider", "Card and wallet payments")
    System_Ext(mail, "E-Mail Service", "Transactional e-mail delivery")

    Rel(customer, spa, "Browses, orders", "HTTPS")
    Rel(spa, api, "Calls", "JSON/HTTPS")
    Rel(api, db, "Reads/writes", "SQL/TCP")
    Rel(api, payments, "Charges cards via", "HTTPS")
    Rel(api, mail, "Sends order confirmations via", "SMTP")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

Key: blue = part of the Web Shop, gray = external system.
