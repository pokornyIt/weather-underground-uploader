# Weather Underground Uploader

[English](README.md) | [Čeština](README.cs.md)

Weather Underground Uploader is a small, configuration-driven Python service
for collecting weather measurements from MQTT and uploading fresh observations
to a Weather Underground Personal Weather Station (PWS).

> [!NOTE]
> The MVP runtime, non-root container packaging, and CI validation are
> implemented.

## Data flow

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

The service:

- consume scalar and JSON measurements from configured MQTT topics,
- normalize temperature, relative humidity, and atmospheric pressure,
- reject invalid values and exclude stale measurements,
- combine fresh values into partial observations,
- skip uploads when no fresh value is available,
- upload observations on a configurable schedule,
- reconnect automatically after MQTT connection loss.

The application will not depend on Home Assistant APIs, a specific MQTT
publisher, or a specific sensor vendor.

## Documentation

The authoritative project and MVP specification is
[docs/en/PROJECT.md](docs/en/PROJECT.md).

Use the [Weather Underground PWS setup guide](docs/en/weather-underground-pws-setup-guide.md) to register a station
and obtain the Station ID and Station Key. A local copy of the official
[PWS Upload Protocol](docs/pws-upload-Protocol.pdf) is also available.

Contribution instructions are in [CONTRIBUTING.md](CONTRIBUTING.md).
Repository automation instructions are in [AGENTS.md](AGENTS.md).

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

The test suite covers configuration, CLI startup, measurement processing, MQTT
ingestion, scheduling, service shutdown, and Weather Underground uploads
without requiring live services.

Run all configured pre-commit hooks with:

```bash
uv run pre-commit run --all-files
```

Run the manual pytest hook with:

```bash
uv run pre-commit run pytest --hook-stage manual --all-files
```

## Configuration

Copy `config.example.yaml`, adjust its installation-specific values, and pass
the resulting file to the CLI:

```bash
uv run --env-file .env weather-underground-uploader --config config.yaml
```

The CLI strictly validates the complete configuration before startup. Unknown
keys, unsupported combinations, duplicate targets, and missing required values
cause an actionable error.

The scheduler waits for one complete configured interval before the first
upload. `SIGINT` and `SIGTERM` stop new uploads, disconnect MQTT, and end the
service without a traceback.

Credentials are read only from environment variables:

```text
MQTT_USERNAME
MQTT_PASSWORD
WU_STATION_ID
WU_STATION_KEY
```

Do not commit real credentials or include them in configuration examples, logs,
issues, or test fixtures.

## Docker deployment

Create local configuration and credential files from the committed examples:

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Edit both files for the target installation. Keep real credentials only in
`.env`; both local files are ignored by Git.

Build and start the service:

```bash
docker compose up --build --detach
```

Follow structured service logs or stop the deployment:

```bash
docker compose logs --follow
docker compose down
```

The container runs as an unprivileged user with a read-only root filesystem.
Compose mounts `config.yaml` read-only and restarts the service unless it is
explicitly stopped.

Validate container changes locally with:

```bash
docker build .
docker compose config
```

## Key repository files

```text
.
├── .github/workflows/ci.yaml
├── .github/ISSUE_TEMPLATE/
├── .dockerignore
├── .env.example
├── compose.yaml
├── config.example.yaml
├── docs/cs/PROJECT.md
├── docs/en/PROJECT.md
├── src/wu_uploader/
├── tests/
├── .python-version
├── AGENTS.md
├── CONTRIBUTING.md
├── Dockerfile
├── LICENSE
├── README.cs.md
├── pyproject.toml
├── README.md
└── uv.lock
```

## License

This project is licensed under the [MIT License](LICENSE).
