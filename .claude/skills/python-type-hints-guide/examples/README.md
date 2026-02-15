# Type Hints Examples

This directory contains comprehensive examples of Python type hints usage.

## Files

### basic_types.py
Demonstrates fundamental type hint patterns:
- Basic types (str, int, float, bool)
- Collection types (list, dict, set, tuple)
- Optional types
- Union types
- Variable annotations

**Run type check:**
```bash
mypy examples/basic_types.py
```

### advanced_types.py
Demonstrates advanced type hint features:
- Generic types (TypeVar, Generic)
- Protocol classes (structural typing)
- TypedDict (structured dictionaries)
- Literal types
- Final types
- NewType (distinct types)
- Callable types
- Type aliases
- Overloaded functions
- Type guards

**Run type check:**
```bash
mypy examples/advanced_types.py
```

### good_vs_bad.py
Compares common anti-patterns with recommended patterns:
- Overusing Any
- Overly complex type hints
- Using type: ignore without justification
- Over-specification vs flexibility
- Inconsistent type hint usage
- Missing Protocol usage
- Missing public API types
- Legacy typing imports
- Improper optional handling
- Missing type narrowing
- Missing return type annotations

**Run type check:**
```bash
mypy examples/good_vs_bad.py
```

## Running All Examples

Check all example files:
```bash
mypy examples/*.py
```

With strict mode:
```bash
mypy --strict examples/*.py
```

## Learning Path

1. Start with `basic_types.py` to understand fundamentals
2. Move to `advanced_types.py` for complex patterns
3. Study `good_vs_bad.py` to avoid common mistakes

## Additional Resources

- See `../templates/` for reusable templates
- See `../SKILL.md` for comprehensive type hints documentation
- Run `python examples/basic_types.py` to see examples in action
