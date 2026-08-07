"""Weather Underground PWS upload adapter."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import SecretStr

from wu_uploader.measurements import Measurement, MeasurementSnapshot
from wu_uploader.models import Target, Unit

LOGGER: logging.Logger = logging.getLogger(__name__)

UPLOAD_ENDPOINT: Final[str] = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
SOFTWARE_TYPE: Final[str] = "weather-underground-uploader"
SUCCESS_RESPONSE: Final[str] = "success"
AUTHENTICATION_ERROR_PREFIX: Final[str] = "INVALIDPASSWORDID"
MAX_RESPONSE_BYTES: Final[int] = 4096
# Standard pressure conversion factor from inches of mercury to hectopascals.
INHG_TO_HPA: Final[float] = 33.8638866667


class HttpRequestError(RuntimeError):
    """Raised when an HTTP request cannot obtain a response safely."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Sanitized HTTP response used by the output adapter."""

    status: int
    body: str


class HttpClient(Protocol):
    """Minimal replaceable HTTP GET boundary."""

    def get(self, endpoint: str, parameters: Mapping[str, str], timeout: float) -> HttpResponse:
        """Perform an HTTPS GET request.

        :param endpoint: Credential-free HTTPS endpoint.
        :param parameters: Query parameters, potentially including protected credentials.
        :param timeout: Request timeout in seconds.
        :return: Sanitized status and response body.
        :raises HttpRequestError: If no HTTP response can be obtained.
        """
        ...


class UrllibHttpClient:
    """Standard-library HTTPS client that sanitizes transport failures."""

    def get(self, endpoint: str, parameters: Mapping[str, str], timeout: float) -> HttpResponse:
        """Perform a verified HTTPS GET request.

        :param endpoint: Credential-free HTTPS endpoint.
        :param parameters: URL-encoded query parameters.
        :param timeout: Request timeout in seconds.
        :return: HTTP status and a bounded response body.
        :raises HttpRequestError: If the request fails before receiving an HTTP response.
        """
        request_url: str = f"{endpoint}?{urlencode(parameters)}"
        request: Request = Request(request_url, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                status: int = response.status
                body: str = response.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        except HTTPError as exc:
            status = exc.code
            body = exc.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
        except OSError, TimeoutError, URLError:
            raise HttpRequestError("network_error") from None
        return HttpResponse(status=status, body=body)


class WeatherUndergroundUploader:
    """Map normalized snapshots to the Weather Underground PWS protocol."""

    def __init__(
        self,
        station_id: SecretStr,
        station_key: SecretStr,
        timeout: float,
        http_client: HttpClient | None = None,
    ) -> None:
        """Initialize the Weather Underground uploader.

        :param station_id: Weather Underground PWS Station ID.
        :param station_key: Weather Underground PWS Station Key.
        :param timeout: HTTP request timeout in seconds.
        :param http_client: Replaceable HTTP client; defaults to the standard-library implementation.
        :raises ValueError: If the timeout is not positive.
        """
        if timeout <= 0:
            raise ValueError("Weather Underground HTTP timeout must be greater than zero")
        self._station_id: SecretStr = station_id
        self._station_key: SecretStr = station_key
        self._timeout: float = timeout
        self._http_client: HttpClient = http_client or UrllibHttpClient()

    def upload(self, snapshot: MeasurementSnapshot) -> bool:
        """Upload one non-empty partial observation.

        :param snapshot: Consistent snapshot of fresh normalized measurements.
        :return: Whether Weather Underground accepted the observation.
        """
        fields: dict[str, str] = _measurement_fields(snapshot)
        if not fields:
            LOGGER.info("event=wu_upload_skipped reason=no_measurements")
            return False

        parameters: dict[str, str] = {
            "ID": self._station_id.get_secret_value(),
            "PASSWORD": self._station_key.get_secret_value(),
            "dateutc": "now",
            "softwaretype": SOFTWARE_TYPE,
            "action": "updateraw",
            **fields,
        }
        try:
            response: HttpResponse = self._http_client.get(UPLOAD_ENDPOINT, parameters, self._timeout)
        except HttpRequestError:
            LOGGER.error("event=wu_upload_failed reason=network_error")
            return False
        except Exception:
            LOGGER.error("event=wu_upload_failed reason=unexpected_error")
            return False

        if response.status != 200:
            LOGGER.error("event=wu_upload_failed reason=http_error status=%d", response.status)
            return False
        response_body: str = response.body.strip()
        if response_body.startswith(AUTHENTICATION_ERROR_PREFIX):
            LOGGER.error("event=wu_upload_failed reason=authentication_error status=%d", response.status)
            return False
        if response_body != SUCCESS_RESPONSE:
            LOGGER.error("event=wu_upload_failed reason=protocol_error status=%d", response.status)
            return False

        uploaded_targets: str = ",".join(_uploaded_targets(snapshot))
        LOGGER.info("event=wu_upload_succeeded fields=%s", uploaded_targets)
        return True


def _measurement_fields(snapshot: MeasurementSnapshot) -> dict[str, str]:
    """Map normalized measurements to Weather Underground query fields.

    :param snapshot: Fresh normalized measurement snapshot.
    :return: Protocol query fields without credentials or fixed metadata.
    :raises ValueError: If a measurement does not use its target's internal unit.
    """
    fields: dict[str, str] = {}
    for measurement in snapshot:
        field_name: str
        field_value: float
        field_name, field_value = _measurement_field(measurement)
        fields[field_name] = _format_number(field_value)
    return fields


def _measurement_field(measurement: Measurement) -> tuple[str, float]:
    """Convert one normalized measurement to a protocol field and value.

    :param measurement: Normalized cached measurement.
    :return: Weather Underground field name and protocol-unit value.
    :raises ValueError: If the measurement target or internal unit is unsupported.
    """
    if measurement.target is Target.TEMPERATURE and measurement.unit is Unit.CELSIUS:
        return "tempf", measurement.value * 9.0 / 5.0 + 32.0
    if measurement.target is Target.HUMIDITY and measurement.unit is Unit.PERCENT:
        return "humidity", measurement.value
    if measurement.target is Target.PRESSURE and measurement.unit is Unit.HPA:
        return "baromin", measurement.value / INHG_TO_HPA
    raise ValueError(f"unsupported internal unit {measurement.unit.value!r} for target {measurement.target.value!r}")


def _format_number(value: float) -> str:
    """Format a protocol value compactly without unnecessary trailing zeros.

    :param value: Finite numeric protocol value.
    :return: Decimal representation with up to ten significant digits.
    """
    return format(value, ".10g")


def _uploaded_targets(snapshot: MeasurementSnapshot) -> tuple[str, ...]:
    """Return uploaded target names in stable protocol order.

    :param snapshot: Successfully uploaded measurement snapshot.
    :return: Present target names ordered as temperature, humidity, pressure.
    """
    present: set[Target] = {measurement.target for measurement in snapshot}
    order: tuple[Target, ...] = (Target.TEMPERATURE, Target.HUMIDITY, Target.PRESSURE)
    return tuple(target.value for target in order if target in present)
