# Repository Instructions

## Scope and source of truth

These instructions apply to the entire repository.

Read `docs/en/PROJECT.md` before designing or implementing project behavior. It
is the authoritative product and MVP specification. Keep implementation,
examples, tests, and documentation consistent with it. If a requested change
conflicts with the specification, call out the conflict and update the
specification as part of the same change when appropriate.

Do not introduce assumptions about a particular installation, MQTT publisher,
sensor vendor, host, hypervisor, or network layout.

## Communication and language

- Communicate with the user in Czech.
- Write source code and technical artifacts in English.
- Use English for identifiers, comments, docstrings, tests, logs, errors,
  configuration comments, documentation, commit messages, and pull request
  text.

## Documentation Guidance

- English docs live under `docs/en/`, Czech docs under `docs/cs/`.
- Preserve the paired bilingual structure.
- If you update only one language, mention the mismatch in the final summary
  unless the user asked for a single-language change.
- Keep docs operational and example-driven; avoid marketing language.
- Keep documentation changes scoped to the requested pages. Avoid unrelated
  rewrites and bulk reformatting.

## Markdown conventions

These rules apply to every `*.md` file in the repository.

### Source of truth

- Follow the repository rules in `.markdownlint.yml` when the file is present.
- Treat every enabled Markdown rule as required.
- Do not add inline or file-level exceptions for rules that can be satisfied
  clearly without them.

The project permits these repository-level exceptions when configured in
`.markdownlint.yml`:

- `MD024: false`: duplicate headings are allowed.
- `MD025: false`: multiple top-level headings are allowed.
- `MD036: false`: emphasis used instead of a heading is allowed.
- `MD041: false`: the first line does not need to be a top-level heading.

Do not disable additional rules without a concrete repository need.

### Line length and tables

- Keep normal prose within the configured `MD013` limit of 120 characters.
- Use local `MD013` disable and enable comments only when needed for readability,
  such as for long URLs, command output, or wide tables.
- Do not aggressively reflow a Markdown table only to satisfy line length.
- Keep a disabled region as small as possible, preferably around the table only.

```md
<!-- markdownlint-disable MD013 -->
| Column A | Column B | Column C |
| -------- | -------- | -------- |
| ...      | ...      | ...      |
<!-- markdownlint-enable MD013 -->
```

### Validation

Validate Markdown changes with:

```bash
uv run pre-commit run markdownlint --all-files
```

Use a narrower file scope during iteration when appropriate, but run the full
configured Markdown check before completing a documentation-wide change.

## Project principles

- Keep the service small, configuration-driven, and easy to understand.
- Keep MQTT ingestion separate from Weather Underground uploads.
- Normalize values before storing them in the in-memory measurement cache.
- Use a monotonic clock for freshness calculations.
- Build uploads from a consistent cache snapshot on the configured schedule.
- Send an observation only when it contains at least one fresh, valid value.
- Omit missing, invalid, and stale fields; never fabricate measurements.
- Permit only one configured source per target in the MVP.
- Treat Jinja templates and other programmable transformations as future work,
  not as part of the MVP.
- Avoid speculative abstractions and unused extension frameworks.

## Python toolchain

- Use Python 3.14 as pinned in `.python-version`.
- Use `uv` for dependency management, environments, locking, and command
  execution.
- Use the project-local `.venv`.
- Declare dependencies in `pyproject.toml` and keep `uv.lock` synchronized.
- Do not use `pip install` or introduce `requirements.txt` as the primary
  dependency definition.
- Use pytest, Ruff, pyright, and pre-commit as development tools.
- Do not add a production dependency without a concrete need and an explanation
  in the change summary.

Run Python tools through `uv run`, for example:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pre-commit run --all-files
```

Use only commands supported by the files currently present in the repository.
During initial bootstrap, create the project configuration before running these
checks. Do not report a check as passing if it could not be run.

## Python style and typing

- Follow PEP 8 and enforce the configured Ruff rules.
- Add type annotations to every function and method signature, including return
  types.
- Add explicit type annotations to module-level and local variables introduced
  by assignment, even when the type checker could infer them.
- Inline annotations are not required for targets of `for` loops,
  comprehensions, `with ... as`, `except ... as`, assignment expressions, or
  unpacking assignments where Python syntax does not support them directly.
- Use precise types and avoid `Any`. Prefer `str | None` to `Optional[str]` and
  concrete built-in collections such as `list[str]` and `dict[str, int]`.
- Use `TypeAlias` or `TypedDict` for complex data shapes when a dedicated model
  would not be clearer.
- Annotate constants with `Final` and an explicit type when practical.
- Use `pathlib.Path` for filesystem paths instead of `os.path`.
- Give standalone executable scripts a `#!/usr/bin/env python3` shebang and a
  module-level docstring. Package modules do not need a shebang.
- Keep modules short and single-purpose. Do not introduce heavy abstractions for
  one-off behavior.

Use standard Python naming:

- `PascalCase` for classes,
- `snake_case` for variables and functions,
- `UPPER_SNAKE_CASE` for constants,
- `snake_case.py` for Python file names; never use hyphens.

## Python errors and logging

- Raise specific exceptions in reusable and library code; do not call
  `sys.exit` there.
- Call `sys.exit` only from `main()` or an equivalent top-level CLI layer.
- Use `logging` for operational and diagnostic output. Use `print` only for
  intentional CLI output.
- Write actionable exception messages with relevant non-secret context such as
  a configuration path, host, source identifier, or expected key.
- Preserve the structured key-value logging and secret-redaction requirements
  from `docs/en/PROJECT.md`.

## Python docstrings

- Every class, function, and method must have an English docstring. This also
  applies to private helpers, nested functions, special methods, and
  constructors such as `__init__`.
- Constructor docstrings must describe every parameter other than `self` using
  `:param <name>:` fields.
- Private and nested functions follow the same documentation standard as public
  functions; describe their parameters, return value, and raised exceptions
  where applicable.
- Use reStructuredText fields: `:param <name>:`, `:return:`, and
  `:raises <ExceptionType>:` where applicable.
- Do not use `:type:` or `:rtype:` fields; types belong in annotations.
- Keep docstrings focused on the contract, behavior, and non-obvious failure
  modes. Do not restate the implementation line by line.
- Test methods must state the behavior they verify. They do not need `:param:`
  fields for pytest fixtures or values supplied by `@pytest.mark.parametrize`.
- Python does not attach docstrings to assigned constants. Add a concise English
  comment for a constant only when its purpose, unit, or derivation is not clear
  from its name, type, and surrounding context; do not place a bare string after
  an assignment as a pseudo-docstring.

```python
def load_sources(path: Path) -> list[str]:
    """Load configured MQTT source names.

    :param path: Path to the YAML configuration file.
    :return: Source names in configuration order.
    :raises FileNotFoundError: If the configuration file does not exist.
    :raises ValueError: If the file is not valid project configuration.
    """
```

## Code organization

Use a `src` layout with the `wu_uploader` package unless the existing project
structure establishes another documented convention. Keep responsibilities
separated along these boundaries:

- configuration loading and validation,
- MQTT connection and payload ingestion,
- parsing and normalization,
- measurement state and freshness,
- observation scheduling,
- Weather Underground output.

Do not let MQTT callbacks perform HTTP uploads. Keep time, MQTT, and HTTP
boundaries replaceable in tests. Prefer explicit data flow and typed models over
hidden global state.

## Configuration changes

- Validate configuration strictly and reject unknown keys.
- Keep defaults and examples aligned with `docs/en/PROJECT.md`.
- Update `config.example.yaml` whenever the schema, defaults, units, or duration
  formats change.
- Keep credentials out of YAML and source control.
- Never weaken TLS certificate verification.
- Preserve the MVP rule that JSON extraction addresses one top-level key.

## Security and logging

- Read credentials only from the documented environment variables.
- Never commit real credentials or operational MQTT payloads containing private
  data.
- Never log MQTT passwords, Weather Underground Station Keys, environment
  contents, or complete upload URLs containing credentials.
- Sanitize secrets from exception messages and HTTP diagnostics.
- Keep logs in consistent, human-readable key-value form on standard output.

## Testing

Add or update tests with every behavior change. At minimum, cover the affected
happy path and its relevant boundary or failure cases.

- Use pytest and keep tests under `tests/`.
- Group tests into classes such as `class TestPayloadParser:`; do not add plain
  top-level test functions.
- Prefer `@pytest.mark.parametrize` to multiple near-identical test methods.
- Add type annotations to test method signatures.
- Do not add tests for trivial I/O-only flows unless the user requests them.

```python
class TestScalarParser:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (b"18.5", 18.5),
            (b" 1007.4 ", 1007.4),
        ],
    )
    def test_parse_valid_payload(self, payload: bytes, expected: float) -> None:
        assert parse_scalar(payload) == expected
```

Tests must not require:

- a live MQTT broker,
- live Weather Underground credentials,
- Internet access,
- wall-clock waiting.

Use test doubles for MQTT and HTTP boundaries and controllable clocks for
scheduler and freshness behavior. Include focused tests for parsing, unit
conversion, validation, retained messages, stale measurements, partial
observations, empty-observation suppression, reconnect behavior, and credential
redaction as those components are implemented.

For a normal Python change, run all available checks:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
uv run pre-commit run --all-files
```

For container-related changes, also run when available:

```bash
docker build .
docker compose config
```

## Docker

- Run the application as a non-root container user.
- Keep the configuration mount read-only.
- Do not bake credentials or installation-specific configuration into the
  image.
- Do not add persistent storage unless the project specification changes.

## Commits

- Follow the commit subject format and allowed types documented in
  `CONTRIBUTING.md`.
- Include the related issue number in the subject for tracked work.

## Change discipline

- Inspect the working tree before editing and preserve unrelated user changes.
- Make focused changes and avoid unrelated refactoring.
- Do not edit generated files manually when their generator is available.
- Keep `README.md`, examples, and project documentation consistent with changed
  behavior.
- Update `docs/en/PROJECT.md` when product requirements or MVP boundaries change;
  do not use it as a status log or implementation diary.
- Do not mark work complete before running validation appropriate to the change.
- Report which checks ran, which did not run, and why.
