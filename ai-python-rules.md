# AI Development Rules for this Python Project

## 1. Core Principles
- **Role**: Act as an expert Python developer with a strong focus on writing clean, maintainable, and robust code.
- **Clarity over cleverness**: Code should be easy to read and understand. Avoid overly complex one-liners if a more explicit multi-line version is clearer.
- **Modern Python**: Use features from Python 3.9+ where appropriate (e.g., `|` for dictionary union, `:=` walrus operator where it enhances clarity).
- **Idempotency**: When generating scripts that modify state (e.g., file systems, databases), make them idempotent where possible.

## 2. Code Style & Formatting
- **PEP 8**: Strictly adhere to all PEP 8 guidelines.
- **Formatter**: All code must be formatted using the **Black** code formatter with a line length of 88 characters.
- **Imports**: Imports should be sorted using `isort` principles: standard library, then third-party libraries, then local application libraries. Group them in that order.
- **Naming**:
    - `snake_case` for variables and functions.
    - `PascalCase` for classes.
    - `UPPER_SNAKE_CASE` for constants.
    - `_` for unused variables (e.g., `for _, value in enumerate(items):`).

## 3. Typing and Docstrings
- **Static Typing**: All function and method signatures **must** include type hints as defined in PEP 484. Use the `typing` module extensively (`List`, `Dict`, `Tuple`, `Optional`, `Any`, `Callable`). For new code, prefer built-in generics like `list` and `dict` over `List` and `Dict`.
- **Docstrings**: All modules, classes, and functions **must** have docstrings.
- **Docstring Format**: Use the **Google Style** docstring format. Every function docstring must include:
    - A one-line summary.
    - A more detailed description if necessary.
    - An `Args:` section detailing each parameter, its type, and description.
    - A `Returns:` section detailing the return type and what it represents.
    - A `Raises:` section if the function can raise specific, expected exceptions.

**Example Function:**
```python
def my_function(name: str, count: int) -> Optional[str]:
    """Summarizes the provided name and count.

    Args:
        name (str): The name to include in the summary.
        count (int): The count to be processed. Must be non-negative.

    Returns:
        Optional[str]: A formatted string, or None if count is zero.

    Raises:
        ValueError: If the count is negative.
    """
    if count < 0:
        raise ValueError("Count cannot be negative.")
    if count == 0:
        return None
    return f"{name} appeared {count} times."