# Weather Underground Uploader

## 1. Purpose

Weather Underground Uploader is a small, standalone service that:

1. subscribes to weather measurements published over MQTT,
2. extracts and normalizes configured values,
3. keeps the latest valid value for each supported weather field,
4. periodically uploads a non-empty observation to a Weather Underground
   Personal Weather Station (PWS).

The application must not depend on Home Assistant APIs, a specific MQTT
publisher, or a specific hardware vendor.

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

The implementation should remain small and understandable. Installation-specific
topics, payload fields, units, credentials, and intervals must be supplied
externally.

---

## 2. MVP Scope

The MVP must support:

- configuration in YAML,
- one MQTT broker,
- multiple MQTT topics and sources,
- scalar and JSON MQTT payloads,
- extraction of one value per configured source,
- temperature, relative humidity, and atmospheric pressure,
- supported source-unit conversion,
- freshness checks per source,
- periodic partial observations,
- Weather Underground PWS uploads,
- automatic MQTT reconnection,
- input and configuration validation,
- structured text logging to standard output,
- graceful process shutdown,
- a Docker image and Docker Compose configuration,
- credentials supplied through environment variables.

The following are outside the MVP:

- Home Assistant API integration,
- database or historical storage,
- web UI,
- metrics endpoints,
- configuration reload without restarting the process,
- nested JSON paths,
- templates, expressions, calibration, or arbitrary transformations,
- multiple fallback or priority sources for one weather field,
- derived values,
- rain, wind, UV, solar radiation, and dew point,
- outputs other than Weather Underground.

The architecture should permit additional fields and output adapters later, but
the MVP must not implement unused extension frameworks.

---

## 3. Runtime and Project Requirements

Use:

- Python 3.14,
- `uv` with a project-local `.venv`,
- `pyproject.toml` and a committed `uv.lock`,
- pytest,
- pyright,
- Ruff,
- pre-commit,
- Docker.

Source code, identifiers, comments, tests, configuration documentation, log
messages, and error messages must be in English.

No persistent database is required.

---

## 4. Configuration

The application must load one YAML configuration file at startup. Its path must
be supplied as `--config PATH`. Runtime configuration reload is not required.

Unknown keys, unsupported values, conflicting sources, and missing required
values must cause startup to fail with a clear error. An error should identify
the relevant configuration path and must not expose credentials.

### 4.1 Configuration model

```yaml
mqtt:
  host: mqtt.example.local
  port: 1883
  client_id: weather-underground-uploader
  keepalive: 60s
  tls: false

upload:
  interval: 60s
  timeout: 10s

sources:
  outdoor_temperature:
    topic: zigbee2mqtt/outdoor
    payload: json
    value: temperature
    unit: celsius
    max_age: 180s
    accept_retained: false
    target: temperature

  outdoor_humidity:
    topic: zigbee2mqtt/outdoor
    payload: json
    value: humidity
    unit: percent
    max_age: 180s
    accept_retained: false
    target: humidity

  pressure:
    topic: sensors/pressure
    payload: scalar
    unit: hpa
    max_age: 300s
    accept_retained: false
    target: pressure

outputs:
  weather_underground:
    enabled: true
```

This structure is the required MVP configuration model. Exact validation types
and defaults must be documented in `config.example.yaml`.

### 4.2 Required fields

`mqtt.host`, `mqtt.port`, `upload.interval`, and at least one source are
required.

Each source requires:

- `topic`,
- `payload`,
- `unit`,
- `max_age`,
- `target`.

`value` is required for a JSON payload and forbidden for a scalar payload.

### 4.3 Defaults and value formats

The following defaults apply:

- `mqtt.client_id`: `weather-underground-uploader`,
- `mqtt.keepalive`: `60s`,
- `mqtt.tls`: `false`,
- `upload.timeout`: `10s`,
- `accept_retained`: `false`,
- `outputs.weather_underground.enabled`: `true`.

Durations must be positive integers followed by `s`, `m`, or `h`.

MQTT TLS must use normal certificate verification and the operating system trust
store. Disabling certificate verification is not supported.

### 4.4 Supported targets and units

| Target        | Supported input units   | Internal unit |
| ------------- | ----------------------- | ------------- |
| `temperature` | `celsius`, `fahrenheit` | °C            |
| `humidity`    | `percent`               | %             |
| `pressure`    | `hpa`, `pa`, `inhg`     | hPa           |

Target and unit names are case-sensitive.

Only one source may be configured for each target in the MVP. Configuring two
sources with the same target must fail at startup.

### 4.5 Credentials

Credentials must not appear in the YAML configuration.

The application reads:

```text
MQTT_USERNAME
MQTT_PASSWORD
WU_STATION_ID
WU_STATION_KEY
```

MQTT credentials are optional. If only one of `MQTT_USERNAME` and
`MQTT_PASSWORD` is set, startup must fail.

`WU_STATION_ID` and `WU_STATION_KEY` are required when the Weather
Underground output is enabled.

---

## 5. MQTT Input Contract

The application consumes MQTT and never publishes to MQTT.

The MVP uses MQTT 3.1.1 with a clean session.

It must:

- subscribe to every distinct configured topic,
- avoid duplicate subscriptions when several sources use the same topic,
- request QoS 1 for subscriptions,
- process messages independently so one invalid value does not affect other
  sources,
- reconnect automatically after connection loss, starting after 1 second and
  doubling the delay up to a maximum of 60 seconds,
- resubscribe after reconnection.

MQTT wildcard topics are not supported in the MVP.

### 5.1 Scalar payload

A scalar payload is decoded as UTF-8, stripped of surrounding whitespace, and
parsed as a finite decimal number.

```text
1007.4
```

Empty, non-UTF-8, non-numeric, `NaN`, and infinite values are invalid.

### 5.2 JSON payload

A JSON payload must be a UTF-8 encoded JSON object. The source's `value`
property identifies one top-level object key.

```json
{
  "temperature": 18.7,
  "humidity": 63.2
}
```

The extracted value must be a JSON number. Missing keys, `null`, booleans,
strings, nested paths, `NaN`, and infinite values are invalid.

### 5.3 Future template extraction

The direct top-level JSON extraction above is intentionally sufficient for the
MVP. A future version may add a mutually exclusive `value_template` option using
sandboxed Jinja syntax, similar in purpose to the Home Assistant MQTT sensor
[`value_template`](https://www.home-assistant.io/integrations/sensor.mqtt/).

A possible future configuration, which is not valid in the MVP, is:

```yaml
value_template: "{{ value_json.environment.temperature }}"
```

The template context should be limited to the decoded payload as `value` and,
when valid JSON is received, as `value_json`. It must not expose Home Assistant
state, environment variables, files, network access, or arbitrary Python
objects. Its rendered result must be parsed and validated as a single finite
number by the normal validation pipeline.

Before template support is implemented, its allowed filters, functions,
execution limits, error behavior, and security tests must be specified. The MVP
must not add Jinja as a dependency.

### 5.4 Retained messages

Retained messages must be ignored unless the matching source has
`accept_retained: true`.

The MVP does not extract measurement timestamps from payloads. An accepted
retained message is therefore considered updated when it is received, not when
it was originally published. This limitation must be mentioned in the example
configuration.

---

## 6. Normalized Measurement State

MQTT handling must not call the Weather Underground adapter directly. Each valid
MQTT value is first converted into the internal unit and stored in a
measurement cache.

Each cached measurement contains:

```text
target
value
unit
received_at
source
```

`received_at` is based on a monotonic clock and is used only for age
calculation. Wall-clock time must not affect freshness decisions.

Cache updates and scheduler reads must be safe when they occur concurrently.
The cache is in memory only and starts empty after every process restart.

---

## 7. Validation and Unit Conversion

Validation occurs in this order:

1. decode and parse the payload,
2. extract the configured value,
3. convert it to the internal unit,
4. validate the normalized value,
5. update the cache.

The MVP validation rules are:

- every value must be a finite number,
- temperature must be between -100 and 100 °C inclusive,
- humidity must be between 0 and 100 percent inclusive,
- pressure must be between 300 and 1200 hPa inclusive.

Invalid values must:

- not update the cached value,
- produce a warning containing the source identifier and reason,
- not terminate the service or affect other sources.

Unit conversion is part of the normalization layer. Conversion to
Weather Underground protocol units belongs only to its output adapter.

---

## 8. Freshness and Observation Construction

At each configured upload interval, the scheduler takes a consistent snapshot
of the cache.

A measurement is stale when:

```text
current_time - received_at > max_age
```

Stale measurements are excluded and logged at warning level. Other fresh
measurements remain eligible for upload.

Partial observations are valid. Missing or stale values must be omitted and must
never be fabricated. In particular, a missing measurement must not be replaced
with zero.

If the snapshot contains no fresh, valid measurements, the upload must be
skipped and the reason logged. The scheduler waits for the first complete
interval after startup before attempting an upload.

An MQTT message never triggers an immediate upload.

---

## 9. Weather Underground Output

Weather Underground is the only MVP output.

The adapter must be called only when an observation contains at least one fresh,
valid measurement as defined in Section 8. If no such measurement exists, no
Weather Underground HTTP request may be made. When at least one measurement is
fresh, it is uploaded and any missing, invalid, or stale fields are omitted.

The adapter must implement the official PWS Upload Protocol:

<!-- markdownlint-disable MD013 -->
[https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US](https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US)
<!-- markdownlint-enable MD013 -->

The official protocol documentation is the source of truth for the endpoint,
required request parameters, protocol units, and response format.

The MVP maps:

| Internal field | Weather Underground field |
| -------------- | ------------------------- |
| temperature    | outdoor temperature       |
| humidity       | outdoor relative humidity |
| pressure       | atmospheric pressure      |

The adapter must:

- use HTTPS,
- supply the Station ID and Station Key,
- identify the uploader through the protocol's software type parameter,
- use the current upload time as required by the protocol,
- include only fields present in the observation,
- convert internal units to protocol units,
- apply the configured HTTP timeout,
- treat only the protocol's documented success response as success,
- sanitize credentials from URLs, exceptions, and logs.

Failed observations are not persisted or queued. A transient failure is logged,
and the latest current observation is attempted at the next scheduled interval.
The application must not perform an immediate aggressive retry loop.

An authentication or configuration error must be logged clearly without
revealing credentials. It must not crash the MQTT processing loop.

Weather Underground read API access and its API key are not used by the MVP.

---

## 10. Failure Handling and Process Lifecycle

### Invalid configuration

Fail before connecting to MQTT or Weather Underground.

### MQTT unavailable

Continue running and reconnect automatically. Measurements expire normally
while disconnected.

### Invalid MQTT payload

Log a warning, ignore the affected update, and continue.

### Weather Underground unavailable

Log the failure and wait until the next scheduled interval.

### Shutdown

On `SIGINT` or `SIGTERM`, stop scheduling new uploads, disconnect from MQTT,
finish or cancel current work within the configured HTTP timeout, and exit
without a traceback.

---

## 11. Logging and Secret Handling

Logs must be written to standard output and work naturally with:

```bash
docker compose logs -f
```

Logs must use consistent structured key-value fields in human-readable text.

```text
INFO event=mqtt_connected host=mqtt.example.local
INFO event=measurement_updated source=outdoor_temperature target=temperature value=18.4 unit=celsius
WARN event=measurement_stale source=pressure age_seconds=421 max_age_seconds=300
WARN event=invalid_measurement source=outdoor_humidity reason=out_of_range
INFO event=wu_upload_succeeded fields=temperature,humidity
ERROR event=wu_upload_failed reason=http_error status=500
```

Logs must never contain:

- MQTT passwords,
- Weather Underground Station Keys,
- complete request URLs containing credentials,
- raw environment-variable contents.

---

## 12. Docker Deployment

The repository must provide:

- a `Dockerfile`,
- a `compose.yaml`,
- a `.env.example` containing placeholder values only,
- a `config.example.yaml`,
- a read-only configuration-file mount.

The container must run as a non-root user and use:

```yaml
restart: unless-stopped
```

No persistent volume is required.

---

## 13. Suggested Module Boundaries

A simple initial separation is:

```text
config
mqtt
measurements
normalization
models
scheduler
outputs/weather_underground
```

This is guidance, not a mandatory file structure. Prefer direct, testable code
over unnecessary abstractions.

---

## 14. Minimal Acceptance Criteria

The MVP is complete when:

- valid scalar and JSON MQTT messages produce the expected normalized cached
  values,
- invalid, retained-disabled, and stale measurements are not uploaded,
- a scheduled non-empty partial observation is mapped and sent to the Weather
  Underground adapter,
- the service reconnects after an MQTT disconnect and exits cleanly on
  `SIGTERM`,
- automated tests and Ruff checks pass, the Docker image builds, and the Docker
  Compose configuration validates.

Live Weather Underground credentials must not be required for the automated test
suite. Network interactions must be replaceable by test doubles.
