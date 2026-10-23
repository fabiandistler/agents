# Code review conventions

- Review in order of cost to change later: API surface, then implementation, then docs, then tests. Report findings in that order, so the first finding comes from the lowest layer that has one.
- API surface is wider than exports: NAMESPACE/`__all__`, HTTP endpoints (plumber, FastAPI), config keys, metric names and log formats. A removal or rename of any of these is a breaking change; flag it unless NEWS/changelog says so.
- For new API: as small as possible, one way to do one thing, no internals leaking, not tailored to a single caller.
- If you would comment on formatting or naming that a linter/formatter could catch, report it once as a missing CI gate.
