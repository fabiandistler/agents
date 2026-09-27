# API Reference

The reader is writing code against your service right now, with your page open
in a second window. Optimize for scanning and copying, not for reading.

## Skeleton

```markdown
# <API name> API

Base URL, versioning scheme, and where the machine-readable spec lives.

## Authentication
## Errors
## Pagination
## Rate limits

## Endpoints
### <METHOD> <path>
  Purpose · parameters · request example · response example · error cases
```

Put auth, errors, pagination, and rate limits **before** the endpoint list.
They apply to every endpoint; repeating them per-endpoint is the main source of
drift in API docs.

## Section notes

**Generated vs hand-written.** If an OpenAPI/GraphQL schema exists, it is the
source of truth for parameter tables and field types — link to the rendered
reference and do not retype it. Hand-write only what a schema cannot carry:
semantics, ordering guarantees, idempotency, side effects, and worked examples.

**Authentication.** Show how to obtain a credential, how to send it, and what
an auth failure looks like on the wire. One curl that works end to end.

**Errors.** A table of code, HTTP status, meaning, and — the part usually
missing — *what the caller should do about it*. Retryable and non-retryable
must be distinguishable.

| Code | Status | Meaning | Caller action |
|---|---|---|---|
| `invalid_cursor` | 400 | Cursor is malformed or expired | Restart pagination from the first page |
| `rate_limited` | 429 | Quota exhausted for this window | Back off using `Retry-After` |

**Pagination.** State the style (cursor, offset, keyset), the page-size default
and maximum, and how the caller knows it has reached the end. Show two
consecutive requests, not one.

**Endpoints.** Per endpoint: one line of purpose, parameters, a request example
with realistic values, the actual response body, and which of the documented
error codes it can return.

```console
$ curl -s https://api.example.com/v1/orders?limit=2 \
    -H "Authorization: Bearer $API_TOKEN"
{
  "items": [
    {"id": "ord_8Kd2", "total_cents": 4200, "status": "shipped"},
    {"id": "ord_8Kd1", "total_cents": 990,  "status": "pending"}
  ],
  "next_cursor": "eyJvIjoyfQ"
}
```

Use realistic values — `ord_8Kd2`, not `string`. Readers pattern-match off
examples far more than off type tables.

## Failure modes

- **Documented fields that no longer exist**, or real fields never documented.
  Generate what can be generated; otherwise pin a test that asserts the example
  responses still parse.
- **Error codes listed without causes or remedies.** A bare code table tells the
  caller nothing about whether to retry.
- **Auth described but never demonstrated.** "Send a bearer token" leaves the
  reader guessing the header name and prefix.
- **Rate limits mentioned without numbers or headers.** Say the window, the
  quota, and which response headers expose the remaining budget.
