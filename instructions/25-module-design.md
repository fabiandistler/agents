---
title: Module design
targets: all
---

## Module design

Cut modules by shared knowledge, not by pipeline phase.

- When a file or function carries a phase name (`load_`, `clean_`, `transform_`, `save_`, `init_`), check whether format or schema knowledge lives in two places. If it does, merge them — execution order is an implementation detail, not a module boundary.
- A wrapper that passes its arguments through unchanged is not a layer. Remove it, or give it an abstraction of its own.
- Add a new layer only when it brings its own abstraction, never for technical reasons.
- Let dependencies point from specific to general only. General code must not know about any specific use case.
