# Python Type Hints Guide - Skill Package

A comprehensive reference guide for Python type hints and static type checking, designed for use with the Uncle Duke Python agent during code reviews.

## Overview

This skill provides detailed guidance on Python type hints for modern Python (3.9+), including:
- Basic and advanced type hint patterns
- Static type checking with mypy
- Best practices and anti-patterns
- Ready-to-use templates and examples
- Helper scripts for type checking

## File Structure

```
python-type-hints-guide/
├── SKILL.md                    # Main skill documentation
├── README.md                   # This file
├── templates/
│   ├── mypy.ini               # Sample mypy configuration
│   ├── pyproject.toml         # Sample pyproject.toml with mypy config
│   ├── stub_file.pyi          # Type stub template
│   └── typed_class.py         # Well-typed class examples
├── examples/
│   ├── README.md              # Examples documentation
│   ├── basic_types.py         # Basic type hint patterns
│   ├── advanced_types.py      # Advanced type patterns
│   └── good_vs_bad.py         # Anti-patterns vs best practices
└── scripts/
    ├── check_types.sh         # Run mypy type checking
    └── generate_stubs.sh      # Generate type stubs
```

## Usage

### For Uncle Duke Agent

This skill is automatically loaded by the uncle-duke-python agent when performing code reviews. It provides comprehensive type hint guidance during CODE REVIEW mode.

The agent will reference this skill to:
- Evaluate type hint quality and consistency
- Identify type hint anti-patterns
- Recommend mypy configuration improvements
- Guide gradual typing adoption

### For Developers

#### Quick Start

1. **Review the main skill documentation:**
   ```bash
   cat SKILL.md
   ```

2. **Study examples:**
   ```bash
   cd examples/
   python basic_types.py
   python advanced_types.py
   ```

3. **Check your code:**
   ```bash
   # Make script executable (first time only)
   chmod +x scripts/check_types.sh

   # Check your code
   ./scripts/check_types.sh your_file.py

   # Strict mode
   ./scripts/check_types.sh --strict your_project/
   ```

#### Using Templates

**mypy Configuration:**
```bash
# Copy mypy.ini to your project root
cp templates/mypy.ini /path/to/your/project/

# Or use pyproject.toml (for modern projects)
cp templates/pyproject.toml /path/to/your/project/
```

**Type Stub File:**
```bash
# Create a type stub for untyped code
cp templates/stub_file.pyi mymodule.pyi
# Edit mymodule.pyi to match your module's API
```

**Well-Typed Class Template:**
```bash
# Use as reference when writing new classes
cat templates/typed_class.py
```

#### Running Scripts

**Type Checking:**
```bash
# Check entire project
./scripts/check_types.sh

# Check specific directory
./scripts/check_types.sh src/

# Check with strict mode
./scripts/check_types.sh --strict src/

# Help
./scripts/check_types.sh --help
```

**Generate Type Stubs:**
```bash
# Generate stubs for a module
./scripts/generate_stubs.sh mymodule

# Generate stubs for a package
./scripts/generate_stubs.sh -p mypackage

# Custom output directory
./scripts/generate_stubs.sh -o typings mymodule

# Help
./scripts/generate_stubs.sh --help
```

## Key Topics Covered

### Basic Type Hints (PEP 484)
- Basic types (int, str, float, bool)
- Collections (list, dict, set, tuple)
- Optional types
- Union types
- Any and None types

### Advanced Types (PEP 585, 604, 612, 613)
- Generic types (TypeVar, Generic)
- Protocol classes (structural subtyping)
- Literal types
- TypedDict
- Final types
- NewType
- Callable types
- Type aliases
- Union operator (|) in Python 3.10+
- Built-in generic types in Python 3.9+

### Function Annotations
- Parameter type hints
- Return type hints
- Default values with type hints
- *args and **kwargs type hints
- Overload decorator

### Class Type Hints
- Instance variables
- Class variables (ClassVar)
- Property type hints
- __init__ annotations

### mypy Configuration
- Basic mypy setup
- Common mypy flags
- Ignoring errors appropriately
- Type: ignore comments
- mypy.ini and pyproject.toml configuration

### Best Practices
- Gradual typing strategy
- When to use type hints
- Type hint readability
- Avoiding over-specification
- Using Protocol for duck typing
- Type narrowing

### Common Patterns
- Forward references
- Circular type dependencies
- Generic container types
- Callback type hints
- Context manager type hints

### Anti-Patterns
- Overusing Any
- Over-complicated type hints
- Ignoring type errors without justification
- Not running mypy in CI/CD
- Inconsistent type hint usage

## Python Version Support

This skill targets Python 3.9+ and takes advantage of modern type hint features:

- **Python 3.9+**: Built-in generic types (list[str] instead of List[str])
- **Python 3.10+**: Union operator (int | str instead of Union[int, str])
- **Python 3.11+**: NotRequired in TypedDict

For legacy Python versions (3.7-3.8), see the SKILL.md for compatibility notes.

## Tools Covered

- **mypy**: Standard Python type checker (primary focus)
- **pyright**: Microsoft's type checker
- **pyre**: Facebook's type checker
- **stubgen**: Type stub generator
- **typing_extensions**: Backport of typing features

## Learning Path

1. **Beginners**: Start with `examples/basic_types.py` and basic sections in SKILL.md
2. **Intermediate**: Study `examples/advanced_types.py` and advanced sections
3. **Advanced**: Review `examples/good_vs_bad.py` and best practices
4. **Experts**: Use as reference during code reviews and for team standards

## Integration with Uncle Duke

When Uncle Duke performs a code review with `[CODE REVIEW]` tag, this skill is automatically referenced to:

1. **Check Type Hint Quality:**
   - Verify all public functions have type hints
   - Ensure type hints are accurate
   - Check for proper use of Optional, Union, etc.
   - Validate collection type annotations

2. **Identify Anti-Patterns:**
   - Overuse of Any
   - Overly complex type hints
   - Unjustified type: ignore comments
   - Inconsistent type hint usage

3. **Evaluate mypy Configuration:**
   - Check for mypy config file
   - Recommend appropriate strictness settings
   - Suggest per-module overrides

4. **Guide Gradual Typing:**
   - Recommend prioritization for adding types
   - Suggest incremental strictness increases
   - Identify good candidates for type stubs

## Quick Reference

### Common Type Hints

```python
# Basic types
def func(x: int, y: str) -> bool: ...

# Collections (Python 3.9+)
def func(items: list[str]) -> dict[str, int]: ...

# Optional
def func(x: str | None = None) -> int | None: ...

# Union (Python 3.10+)
def func(x: int | str | float) -> str: ...

# Callable
def func(callback: Callable[[int], str]) -> None: ...

# Generic
T = TypeVar('T')
def func(items: list[T]) -> T | None: ...
```

### Common mypy Commands

```bash
# Basic check
mypy file.py

# Strict mode
mypy --strict file.py

# Show error codes
mypy --show-error-codes file.py

# Check specific Python version
mypy --python-version 3.9 file.py

# Generate HTML report
mypy --html-report report/ src/
```

### Type: ignore Best Practices

```python
# BAD
result = func()  # type: ignore

# GOOD
result = func()  # type: ignore[arg-type]  # Reason: known false positive, issue #123
```

## Contributing

This skill is maintained as part of the Uncle Duke agent system. To improve it:

1. Add new examples to `examples/`
2. Update templates in `templates/`
3. Enhance SKILL.md with new patterns
4. Add helper scripts to `scripts/`
5. Update this README with new features

## References

### Official Python Documentation
- [typing module](https://docs.python.org/3/library/typing.html)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 585 - Type Hinting Generics](https://peps.python.org/pep-0585/)
- [PEP 604 - Union Operator](https://peps.python.org/pep-0604/)

### Type Checker Documentation
- [mypy](https://mypy.readthedocs.io/)
- [pyright](https://github.com/microsoft/pyright)
- [pyre](https://pyre-check.org/)

### Additional Resources
- [Real Python - Type Checking](https://realpython.com/python-type-checking/)
- [Mypy Cheat Sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html)

---

**Version:** 1.0
**Last Updated:** 2025-12-24
**Target Python:** 3.9+
**Maintainer:** Uncle Duke (Python Development Agent)
