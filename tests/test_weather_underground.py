import logging
from collections.abc import Mapping
from typing import Never
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest
from pydantic import SecretStr

import wu_uploader.outputs.weather_underground as weather_underground_module
from wu_uploader.measurements import Measurement, MeasurementSnapshot
from wu_uploader.models import Target, Unit
from wu_uploader.outputs.weather_underground import (
    SOFTWARE_TYPE,
    UPLOAD_ENDPOINT,
    HttpRequestError,
    HttpResponse,
    UrllibHttpClient,
    WeatherUndergroundUploader,
)


def _measurement(target: Target, value: float, unit: Unit) -> Measurement:
    """Build one normalized measurement for output tests.

    :param target: Normalized measurement target.
    :param value: Measurement value in its internal unit.
    :param unit: Internal measurement unit.
    :return: Test measurement instance.
    """
    return Measurement(target=target, value=value, unit=unit, received_at=10.0, source=target.value)


def _snapshot(*measurements: Measurement) -> MeasurementSnapshot:
    """Build a consistent measurement snapshot for output tests.

    :param measurements: Fresh normalized measurements to include.
    :return: Test measurement snapshot.
    """
    return MeasurementSnapshot(captured_at=10.0, measurements=measurements)


class FakeHttpClient:
    """Record HTTP requests and return a configured response or exception."""

    def __init__(
        self,
        response: HttpResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        """Initialize the HTTP test double.

        :param response: Response returned by successful calls; defaults to protocol success.
        :param error: Optional exception raised instead of returning a response.
        """
        self.response: HttpResponse = response or HttpResponse(status=200, body="success")
        self.error: Exception | None = error
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get(self, endpoint: str, parameters: Mapping[str, str], timeout: float) -> HttpResponse:
        """Record a request and return its configured outcome.

        :param endpoint: Credential-free HTTPS endpoint.
        :param parameters: Request query parameters.
        :param timeout: Request timeout in seconds.
        :return: Configured HTTP response.
        :raises Exception: Configured test exception when present.
        """
        self.calls.append((endpoint, dict(parameters), timeout))
        if self.error is not None:
            raise self.error
        return self.response


class FakeUrlResponse:
    """Context-managed urllib response test double."""

    def __init__(self, status: int, body: bytes) -> None:
        """Initialize a fake URL response.

        :param status: HTTP response status.
        :param body: HTTP response body bytes.
        """
        self.status: int = status
        self.body: bytes = body

    def __enter__(self) -> FakeUrlResponse:
        """Enter the fake response context.

        :return: This response instance.
        """
        return self

    def __exit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object | None,
    ) -> None:
        """Exit the fake response context without suppressing exceptions.

        :param _exception_type: Active exception type, if any.
        :param _exception: Active exception instance, if any.
        :param _traceback: Active traceback, if any.
        :return: None.
        """

    def read(self, amount: int = -1) -> bytes:
        """Return the configured response body within the requested limit.

        :param amount: Maximum response bytes to return.
        :return: Bounded response body.
        """
        return self.body[:amount]


class TestWeatherUndergroundUploader:
    """Test protocol mapping, responses, and credential redaction."""

    def test_maps_complete_observation_to_protocol_request(self) -> None:
        """Verify fixed parameters, field mapping, units, timeout, and HTTPS endpoint."""
        client: FakeHttpClient = FakeHttpClient()
        uploader: WeatherUndergroundUploader = WeatherUndergroundUploader(
            SecretStr("station-id"),
            SecretStr("station-key"),
            timeout=7.5,
            http_client=client,
        )
        snapshot: MeasurementSnapshot = _snapshot(
            _measurement(Target.TEMPERATURE, 20.0, Unit.CELSIUS),
            _measurement(Target.HUMIDITY, 55.5, Unit.PERCENT),
            _measurement(Target.PRESSURE, 1013.25, Unit.HPA),
        )

        uploaded: bool = uploader.upload(snapshot)

        assert uploaded is True
        assert len(client.calls) == 1
        endpoint: str
        parameters: dict[str, str]
        timeout: float
        endpoint, parameters, timeout = client.calls[0]
        assert endpoint == UPLOAD_ENDPOINT
        assert endpoint.startswith("https://")
        assert timeout == 7.5
        barometer_inches: float = float(parameters.pop("baromin"))
        assert barometer_inches == pytest.approx(29.92125535)
        assert parameters == {
            "ID": "station-id",
            "PASSWORD": "station-key",
            "dateutc": "now",
            "softwaretype": SOFTWARE_TYPE,
            "action": "updateraw",
            "tempf": "68",
            "humidity": "55.5",
        }

    def test_omits_measurements_missing_from_partial_observation(self) -> None:
        """Verify that partial observations do not fabricate protocol fields."""
        client: FakeHttpClient = FakeHttpClient()
        uploader: WeatherUndergroundUploader = WeatherUndergroundUploader(
            SecretStr("station-id"), SecretStr("station-key"), timeout=10.0, http_client=client
        )

        uploaded: bool = uploader.upload(_snapshot(_measurement(Target.HUMIDITY, 0.0, Unit.PERCENT)))

        assert uploaded is True
        parameters: dict[str, str] = client.calls[0][1]
        assert parameters["humidity"] == "0"
        assert "tempf" not in parameters
        assert "baromin" not in parameters

    def test_skips_empty_observation_without_http_request(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that an empty snapshot never produces a Weather Underground request."""
        client: FakeHttpClient = FakeHttpClient()
        uploader: WeatherUndergroundUploader = WeatherUndergroundUploader(
            SecretStr("station-id"), SecretStr("station-key"), timeout=10.0, http_client=client
        )

        with caplog.at_level(logging.INFO):
            uploaded: bool = uploader.upload(_snapshot())

        assert uploaded is False
        assert client.calls == []
        assert "event=wu_upload_skipped reason=no_measurements" in caplog.messages

    @pytest.mark.parametrize(
        ("response", "expected", "reason"),
        [
            (HttpResponse(200, "success"), True, None),
            (HttpResponse(200, " success\n"), True, None),
            (HttpResponse(200, "SUCCESS"), False, "protocol_error"),
            (HttpResponse(200, "INVALIDPASSWORDID|Password and/or id are incorrect"), False, "authentication_error"),
            (HttpResponse(401, "success"), False, "http_error"),
            (HttpResponse(500, "server error"), False, "http_error"),
        ],
    )
    def test_accepts_only_documented_success_response(
        self,
        response: HttpResponse,
        expected: bool,
        reason: str | None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify strict protocol response handling without logging response contents."""
        client: FakeHttpClient = FakeHttpClient(response)
        uploader: WeatherUndergroundUploader = WeatherUndergroundUploader(
            SecretStr("station-id"), SecretStr("station-key"), timeout=10.0, http_client=client
        )

        with caplog.at_level(logging.INFO):
            uploaded: bool = uploader.upload(_snapshot(_measurement(Target.TEMPERATURE, 0.0, Unit.CELSIUS)))

        assert uploaded is expected
        if reason is not None:
            assert f"reason={reason}" in caplog.messages[0]
        assert "INVALIDPASSWORDID" not in caplog.text

    @pytest.mark.parametrize(
        "error",
        [
            HttpRequestError("network_error"),
            RuntimeError("https://example.invalid?ID=station-id&PASSWORD=station-key"),
        ],
    )
    def test_redacts_credentials_from_http_failures(
        self,
        error: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that transport exceptions cannot leak credentials through logs."""
        client: FakeHttpClient = FakeHttpClient(error=error)
        uploader: WeatherUndergroundUploader = WeatherUndergroundUploader(
            SecretStr("station-id"), SecretStr("station-key"), timeout=10.0, http_client=client
        )

        with caplog.at_level(logging.ERROR):
            uploaded: bool = uploader.upload(_snapshot(_measurement(Target.PRESSURE, 1000.0, Unit.HPA)))

        assert uploaded is False
        assert len(client.calls) == 1
        assert "station-id" not in caplog.text
        assert "station-key" not in caplog.text
        assert "https://" not in caplog.text

    @pytest.mark.parametrize("timeout", [0.0, -1.0])
    def test_rejects_non_positive_timeout(self, timeout: float) -> None:
        """Verify that an invalid HTTP timeout is rejected before any request."""
        with pytest.raises(ValueError, match="timeout must be greater than zero"):
            WeatherUndergroundUploader(SecretStr("station-id"), SecretStr("station-key"), timeout)


class TestUrllibHttpClient:
    """Test URL encoding and sanitized urllib transport failures."""

    def test_url_encodes_query_parameters(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify safe URL encoding and propagation of timeout and response data."""
        captured_request: Request | None = None
        captured_timeout: float | None = None

        def fake_urlopen(request: Request, timeout: float) -> FakeUrlResponse:
            """Capture a urllib request and return a successful response.

            :param request: Encoded urllib request.
            :param timeout: Configured HTTP timeout.
            :return: Successful fake URL response.
            """
            nonlocal captured_request, captured_timeout
            captured_request = request
            captured_timeout = timeout
            return FakeUrlResponse(200, b"success")

        monkeypatch.setattr(weather_underground_module, "urlopen", fake_urlopen)
        client: UrllibHttpClient = UrllibHttpClient()

        response: HttpResponse = client.get(
            UPLOAD_ENDPOINT,
            {"ID": "station id", "PASSWORD": "key&value", "dateutc": "now"},
            3.0,
        )

        assert response == HttpResponse(200, "success")
        assert captured_request is not None
        query: dict[str, list[str]] = parse_qs(urlparse(captured_request.full_url).query)
        assert query == {"ID": ["station id"], "PASSWORD": ["key&value"], "dateutc": ["now"]}
        assert captured_timeout == 3.0

    def test_sanitizes_url_errors(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that urllib exceptions are replaced with a credential-free error."""

        def failing_urlopen(_request: Request, timeout: float) -> Never:
            """Raise a URL error containing simulated credentials.

            :param _request: Encoded urllib request.
            :param timeout: Configured HTTP timeout.
            :raises URLError: Always, with simulated sensitive context.
            """
            del timeout
            raise URLError("https://example.invalid?ID=station-id&PASSWORD=station-key")

        monkeypatch.setattr(weather_underground_module, "urlopen", failing_urlopen)
        client: UrllibHttpClient = UrllibHttpClient()

        with pytest.raises(HttpRequestError) as error:
            client.get(UPLOAD_ENDPOINT, {"ID": "station-id", "PASSWORD": "station-key"}, 3.0)

        assert str(error.value) == "network_error"
