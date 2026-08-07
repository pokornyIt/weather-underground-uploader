# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader is a small, configuration-driven Python service
for collecting weather measurements from MQTT and uploading fresh observations
to a Weather Underground Personal Weather Station (PWS).

> [!NOTE]
> The repository is currently in the project bootstrap phase. The service is not
> implemented or runnable yet.

## Planned data flow

```text
MQTT publishers
      │
      ▼
 MQTT broker
      │
      ▼
Weather Underground Uploader
      │
      ▼
Weather Underground PWS
```

The MVP will:

- consume scalar and JSON measurements from configured MQTT topics,
- normalize temperature, relative humidity, and atmospheric pressure,
- reject invalid values and exclude stale measurements,
- combine fresh values into partial observations,
- skip uploads when no fresh value is available,
- upload observations on a configurable schedule,
- reconnect automatically after MQTT connection loss,
- run locally or in a non-root Docker container.

The application will not depend on Home Assistant APIs, a specific MQTT
publisher, or a specific sensor vendor.

## Documentation

The authoritative project and MVP specification is
[docs/en/PROJECT.md](docs/en/PROJECT.md).

Repository contribution and automation instructions are in
[AGENTS.md](AGENTS.md).

## Development requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker for container-related work

The Python version is pinned in `.python-version`. Project dependencies and tool
configuration live in `pyproject.toml`; exact dependency versions are locked in
`uv.lock`.

## Development setup

Create or update the project-local virtual environment:

```bash
uv sync
```

Run the available quality checks:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

The test suite will remain empty until the first application components are
implemented. In that state, pytest exits with code 5 because it collects no
tests.

Once pre-commit configuration is added, run all configured hooks with:

```bash
uv run pre-commit run --all-files
```

## Planned configuration

The service will load a YAML configuration file supplied with:

```bash
weather-underground-uploader --config config.yaml
```

Installation-specific MQTT topics, payload fields, units, freshness limits, and
upload intervals will live in that file. The final example configuration will be
provided as `config.example.yaml` when configuration loading is implemented.

Credentials will be read only from environment variables:

```text
MQTT_USERNAME
MQTT_PASSWORD
WU_STATION_ID
WU_STATION_KEY
```

Do not commit real credentials or include them in configuration examples, logs,
issues, or test fixtures.

## Key repository files

```text
.
├── docs/cs/PROJECT.md
├── docs/en/PROJECT.md
├── .python-version
├── AGENTS.md
├── LICENSE
├── README.cs.md
├── pyproject.toml
├── README.md
└── uv.lock
```

The source package, tests, example configuration, Docker files, and runtime entry
point will be added during implementation.

## License

This project is licensed under the [MIT License](LICENSE).
