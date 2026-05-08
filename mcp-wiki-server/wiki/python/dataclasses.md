# Python Dataclasses

`@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__` from typed
class attributes — eliminating boilerplate for plain data objects.

## Basic
```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
```

## Frozen (immutable, hashable)
```python
@dataclass(frozen=True)
class Coord:
    x: int
    y: int
```
Use `frozen=True` when instances should be usable as dict keys or set members.

## Mutable defaults
Never use `field_name: list = []` — all instances would share one list.
Use `field(default_factory=...)`:

```python
from dataclasses import dataclass, field

@dataclass
class Bag:
    items: list[str] = field(default_factory=list)
```

## Slots (Python 3.10+)
`@dataclass(slots=True)` reduces memory and prevents accidental attribute
creation. Cannot mix with multiple inheritance from non-slot classes.
