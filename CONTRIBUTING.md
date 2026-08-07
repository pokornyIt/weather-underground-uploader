# Contributing

Thank you for contributing to Weather Underground Uploader. Keep changes focused, testable, and aligned with the
documented MVP.

## Before You Start

- Read [docs/en/PROJECT.md](docs/en/PROJECT.md), the source of truth for product behavior and MVP scope.
- Read [AGENTS.md](AGENTS.md) for repository-wide implementation, documentation, testing, and validation rules.
- Search existing issues before opening a new one.
- Use the provided issue templates for bug reports and feature requests.

Do not include credentials, API keys, private MQTT payloads, or unredacted logs in issues, commits, tests, or pull
requests.

## Development Setup

The project requires Python 3.14 and [uv](https://docs.astral.sh/uv/). Docker is required only for container-related
changes.

Create or update the project-local environment from the repository root:

```bash
uv sync
```

Run project tools through `uv run`; do not install project dependencies with `pip`.

## Workflow

1. Create or choose an issue for a non-trivial change.
2. Create a branch from `main` named `<issue-number>-<short-kebab-case-description>`, for example
   `1-contribution-guidelines`.
3. Keep the change within the issue scope and avoid unrelated refactoring.
4. Add or update tests for behavior changes.
5. Update affected examples and documentation.
6. Run all checks relevant to the change.
7. Open a focused pull request that links the issue with `Closes #<issue-number>`.

Write source code, technical documentation, tests, logs, errors, commit messages, and pull request text in English.

## Commits

Use Conventional Commit subjects in this format:

```text
<type>: <imperative description> (#<issue-number>)
```

Use the type that best describes the primary change: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, or `ci`.
Keep the description lowercase, concise, and without a trailing period. Include the issue reference for tracked work;
omit it only when no issue exists.

For example:

```text
chore: add contribution workflow and pre-commit checks (#1)
```

## Documentation

- Keep English pages under `docs/en/` paired with their Czech versions under `docs/cs/`.
- Keep `README.md` and `README.cs.md` aligned.
- Update `docs/en/PROJECT.md` and its Czech counterpart when product requirements or MVP boundaries change.
- Keep documentation operational and example-driven.

## Validation

Run the available project checks from the repository root:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Run all configured pre-commit hooks:

```bash
uv run pre-commit run --all-files
```

For container-related changes, also run:

```bash
docker build .
docker compose config
```

Report checks that could not be run and explain why.

## Pull Requests

- Prefer one independently reviewable issue per pull request.
- Summarize the outcome and important design decisions.
- List the validation commands that were run.
- Mention documentation changes or explain why none were needed.
- Keep credentials, secret-bearing URLs, and sensitive payloads out of the description and attached logs.
