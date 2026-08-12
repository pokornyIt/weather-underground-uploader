# Home Assistant examples

These optional examples read Weather Underground observations into Home Assistant after this uploader has sent
measurements to a Personal Weather Station (PWS).

The examples do not connect Home Assistant to this service directly. Home Assistant reads the current observation
from the Weather.com PWS API.

## Credentials and identifiers

Weather Underground uses three different values:

| Value       | Purpose                                  | Used by these examples |
| ----------- | ---------------------------------------- | ---------------------- |
| Station ID  | Identifies a PWS                         | Yes                    |
| Station Key | Authorizes uploads from this service     | No                     |
| API Key     | Authorizes Weather.com read API requests | Yes                    |

Never put the Station Key into a Home Assistant REST request. The API Key is a separate read credential obtained
after registering and activating a PWS, as described in the
[Weather Underground PWS setup guide](weather-underground-pws-setup-guide.md).

Station IDs are not authentication secrets, but they can disclose an approximate location. The examples therefore
load both Station IDs and the API Key from `secrets.yaml`.

## Requirements

- Home Assistant with YAML configuration access
- an active Weather Underground PWS
- a Weather.com API Key
- [HACS](https://www.hacs.xyz/) for installing dashboard dependencies
- [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) installed through HACS

The package files use only built-in Home Assistant integrations. Mushroom Cards are required only by the dashboard
files.

## Available examples

### Single station

The single-station example reads temperature, relative humidity, and atmospheric pressure from one PWS. It is the
recommended starting point and matches the measurement targets supported by this uploader.

Files:

- [`single-station/package.yaml`](../../examples/home-assistant/single-station/package.yaml)
- [`single-station/dashboard.yaml`](../../examples/home-assistant/single-station/dashboard.yaml)

The package creates these main entities:

```text
sensor.weather_underground_station
sensor.wu_temperature
sensor.wu_humidity
sensor.wu_pressure
```

### Area aggregation

The area example reads five nearby PWS stations. It calculates median temperature, humidity, pressure, dew point,
UV index, solar radiation, wind speed, wind gust, precipitation total, and precipitation rate. Wind direction uses a
circular mean instead of a median. A normal aggregated value is published only when at least three valid stations
provide that measurement.

Files:

- [`area/package.yaml`](../../examples/home-assistant/area/package.yaml)
- [`area/dashboard.yaml`](../../examples/home-assistant/area/dashboard.yaml)

A source station is valid when:

- its REST sensor is available;
- Weather Underground returns `qcStatus: 1`;
- its observation is no more than one hour old;
- the selected value is numeric and inside the configured sanity range.

The median limits the effect of one differing station. Maximum precipitation intensity and rain detection need only
one valid reporting station so that a local shower is not hidden by dry stations. Daily, weekly, monthly, and yearly
[utility meters](https://www.home-assistant.io/integrations/utility_meter/) accumulate the aggregated precipitation
total.

This is an example of consuming nearby public observations, not part of the uploader runtime. Rain totals are an
area estimate: changes in the set of valid source stations can move the median and therefore affect accumulated
utility-meter values.

## Install Mushroom Cards

Install HACS first if it is not already available. In HACS:

1. Open `Frontend`.
2. Search for `Mushroom`.
3. Download Mushroom Cards.
4. Reload the browser when HACS requests it.

Both dashboards use `custom:mushroom-template-card`. They show a missing-card error until Mushroom Cards are loaded.

## Enable Home Assistant packages

Add package loading to the main Home Assistant `configuration.yaml` if it is not already configured:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Create the `packages` directory under the Home Assistant configuration directory.

Copy one example package into it. Use a descriptive `.yaml` name, for example:

```text
/config/packages/weather_underground_station.yaml
```

or:

```text
/config/packages/weather_underground_area.yaml
```

Home Assistant directory includes recognize `.yaml` files but ignore `.yml` files.

## Configure secrets

Use [`secrets.example.yaml`](../../examples/home-assistant/secrets.example.yaml) as a reference. Copy only the entries
needed by the selected example into the Home Assistant `/config/secrets.yaml` file and replace every placeholder.

For the single-station example:

```yaml
weather_com_api_key: "YOUR_WEATHER_COM_API_KEY"
wu_station_id: "YOUR_STATION_ID"
```

For the area example:

```yaml
weather_com_api_key: "YOUR_WEATHER_COM_API_KEY"
wu_area_station_1_id: "YOUR_FIRST_STATION_ID"
wu_area_station_2_id: "YOUR_SECOND_STATION_ID"
wu_area_station_3_id: "YOUR_THIRD_STATION_ID"
wu_area_station_4_id: "YOUR_FOURTH_STATION_ID"
wu_area_station_5_id: "YOUR_FIFTH_STATION_ID"
```

Do not copy `secrets.yaml` back into this repository.

## Load the package

Check the Home Assistant configuration before restarting. Resolve every missing secret or duplicate entity identifier
reported by the check. Restart Home Assistant after the configuration is valid.

The REST sensors poll Weather.com every 20 minutes. Template entities reject observations older than one hour, values
that failed Weather Underground quality control, and values outside their sanity ranges.

## Add a dashboard

The dashboard examples contain complete raw dashboard configurations with a top-level `views` key.

1. Create a new dashboard or open an empty YAML-managed dashboard.
2. Open the raw configuration editor.
3. Paste the matching `dashboard.yaml` contents.
4. Save the dashboard.

The entity IDs in the dashboard assume that no existing entities forced Home Assistant to add a numeric suffix. If an
entity ID differs, update the dashboard reference to match it.

## Change the area stations

To replace a station, change only its value in `secrets.yaml`.

To add a station:

1. copy one complete REST entry in the area package;
2. give its sensor a new name and `unique_id`;
3. add its Station ID secret;
4. add its entity ID to `group.wu_area_stations`;
5. optionally add it to the source list in the dashboard.

The valid/configured station counter is derived from the group and does not contain a fixed station total. Normal
measurement templates currently require three valid values. Maximum precipitation intensity and rain detection are
intentional exceptions that react to one valid station.

## API usage

Each configured source station performs one request every 20 minutes. The single-station example therefore performs
72 requests per day, while the five-station area example performs 360 requests per day. Review the current API terms
and limits before shortening `scan_interval` or adding many stations.
