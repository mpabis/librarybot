# Repository Guidelines

## Project Structure & Module Organization

This is a small Python automation repository for checking Stockholm Library due
dates and sending Mailgun notifications. The main entry point is
`check-due-dates.py`; keep changes to scraping, due-date parsing, and
notification logic there unless the code grows enough to justify modules.
`load_env.py` loads local `.env` values for development. Runtime dependencies
live in `requirements.txt`, while Python/tooling metadata lives in
`pyproject.toml`. GitHub automation is under `.github/workflows/`, especially
`check-library-due-dates.yml`. Generated files such as
`email_notification_*.txt` and `public/` are artifacts, not source.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt` installs runtime dependencies.
- `python -m pip install -e ".[dev]"` installs the package with dev tools from
  `pyproject.toml`.
- `python check-due-dates.py` runs the due-date checker locally using `.env` or
  environment variables and writes the encrypted web report to `public/`.
- `python -m pytest` runs tests once they exist.
- `ruff check .`, `black .`, and `mypy .` run linting, formatting, and type
  checks.

## Coding Style & Naming Conventions

Target Python 3.9+ and keep code compatible with the GitHub Actions Python 3.11
runtime. Use Black formatting with 88-character lines and Ruff rules configured
in `pyproject.toml`. Prefer clear, typed functions with Google-style docstrings.
Use `snake_case` for functions and variables, `PascalCase` for classes, and
`UPPER_SNAKE_CASE` for constants. Keep imports grouped as standard library,
third-party packages, then local modules.

## Testing Guidelines

There is no committed test suite yet. Add tests under `tests/` using pytest,
with files named `test_*.py`. Focus tests on pure parsing and notification
decision logic before mocking network calls. Avoid tests that require real
library credentials or Mailgun API keys.

## Commit & Pull Request Guidelines

Recent history uses short, direct commit subjects such as `Email format` and
`Update check-library-due-dates.yml`. Keep commits focused and use imperative
summaries where possible. Pull requests should describe the behavior change,
note any configuration or secret changes, and include relevant local command
results. For workflow or notification changes, include a sample output or
artifact name when practical.

## Security & Configuration Tips

Never commit `.env`, `config.json`, library card numbers, PINs, Mailgun keys, or
generated notification/report artifacts. Use `.env.template` to document
required variables and GitHub Secrets/Variables for Actions runs. Store the web
report passcode outside the repo, such as in Bitwarden, and expose it to Actions
only through `REPORT_PASSPHRASE`.
