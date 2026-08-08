# Weather Underground PWS – registering a station and obtaining an API Key

This practical guide is for users registering their first Personal Weather Station (PWS), uploading their own
observations to Weather Underground, and optionally obtaining an API Key. The procedure was verified in August
2026.

> [!NOTE]
> This project requires only a Station ID and Station Key. An API Key is used to read the Weather API and is not
> required to run the uploader; the related sections of this guide are optional.

## 1. Expected result

The complete procedure provides three different values:

```text
Station ID
Station Key
API Key
```

Do not confuse them:

- **Station ID** identifies a specific PWS and is used for uploads and station-specific API requests.
- **Station Key** is the secret used for uploads. The PWS Upload Protocol sends it as `PASSWORD`.
- **API Key** is a separate credential for reading the Weather Underground or The Weather Company API.

## 2. Requirements

A commercial weather station is not required to register and activate a PWS. Weather Underground supports the
`Other` hardware type. A station can also be activated by uploading only a subset of measurements, such as
temperature and relative humidity.

Do not send unavailable measurements such as wind, rain, pressure, or UV. **Never replace them with fabricated
zero values.**

## 3. Creating or signing in to an account

Open [Weather Underground](https://www.wunderground.com/) and sign in or create an account.

The PWS network is available at the
[Weather Underground PWS Network](https://www.wunderground.com/pws/overview).

Use `Register` on that page. When already signed in, the device page is also available through:

```text
My Profile
  └── My Devices
```

## 4. Registering a new PWS

First select the station's real location on the map.

For a custom DIY or MQTT solution, use:

```text
Device Hardware: Other
```

### Name

Choose a descriptive name, for example:

```text
Home Weather Station
```

or:

```text
MQTT Weather Station
```

### Elevation

Enter the elevation of the station location.

### Surface Type

If none of the available options reasonably represents the actual location, leave this field empty when the UI
does not mark it as required.

### Height Above Ground

This value is also optional. A station assembled from several physical sensors at different heights may not have
one correct value.

Weather Underground uses feet for this field:

```text
2 m  ≈ 6.6 ft
10 m ≈ 32.8 ft
```

## 5. After registration

Weather Underground creates the device and assigns:

```text
Station ID
Station Key
```

Store both values securely. This project reads them from:

```env
WU_STATION_ID=...
WU_STATION_KEY=...
```

Never commit credentials to a Git repository.

The station is normally shown as `Offline` immediately after registration. It becomes active after the first
successful upload.

## 6. PWS Upload Protocol

A copy of the official documentation is stored in
[PWS Upload Protocol](../pws-upload-Protocol.pdf). The current online version is available from
[Weather.com](https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US).

Uploads use an HTTP GET request to:

```text
https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php
```

The basic parameters are:

```text
ID       = Station ID
PASSWORD = Station Key
dateutc  = observation time
action   = updateraw
```

For a simple test, use:

```text
dateutc=now
```

## 7. Upload units

The upload protocol primarily uses imperial units.

| Parameter        | Meaning              | Unit  |
| ---------------- | -------------------- | ----- |
| `tempf`          | temperature          | °F    |
| `humidity`       | relative humidity    | %     |
| `baromin`        | pressure             | inHg  |
| `windspeedmph`   | wind speed           | mph   |
| `windgustmph`    | wind gust            | mph   |
| `winddir`        | wind direction       | °     |
| `rainin`         | rainfall             | inch  |
| `dailyrainin`    | daily rainfall       | inch  |
| `solarradiation` | solar radiation      | W/m²  |
| `UV`             | UV index             | index |

For example:

```text
20 °C = 68 °F
```

## 8. Minimal upload test

Temperature and humidity are sufficient for an initial test:

```text
ID=<Station ID>
PASSWORD=<Station Key>
dateutc=now
tempf=68.0
humidity=50
action=updateraw
```

## 9. Testing with Postman

Configure:

```text
Method: GET
URL: https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php
```

Create these values in a Postman Environment:

```text
WU_STATION_ID
WU_STATION_KEY
```

Set the query parameters:

| Key        | Value                |
| ---------- | -------------------- |
| `ID`       | `{{WU_STATION_ID}}`  |
| `PASSWORD` | `{{WU_STATION_KEY}}` |
| `dateutc`  | `now`                |
| `tempf`    | `68.0`               |
| `humidity` | `50`                 |
| `action`   | `updateraw`          |

Weather Underground returns this response when the upload succeeds:

```text
success
```

This confirms that the Station ID, Station Key, and upload endpoint work.

## 10. Testing with curl

```bash
export WU_STATION_ID='YOUR_STATION_ID'
read -s WU_STATION_KEY
export WU_STATION_KEY

curl -G \
  'https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php' \
  --data-urlencode "ID=${WU_STATION_ID}" \
  --data-urlencode "PASSWORD=${WU_STATION_KEY}" \
  --data-urlencode 'dateutc=now' \
  --data-urlencode 'tempf=68.0' \
  --data-urlencode 'humidity=50' \
  --data-urlencode 'action=updateraw'
```

Expected response:

```text
success
```

## 11. After the first upload

After a successful upload, the station changes from:

```text
Offline
```

to:

```text
Online
```

The web interface may update after a short delay.

When only temperature and humidity were uploaded, other measurements may remain displayed as `--`. This is
correct.

## 12. Obtaining an API Key

Registering a PWS may not immediately make an API Key available. The verified procedure is:

```text
register a PWS
        ↓
obtain the Station ID and Station Key
        ↓
upload a valid observation
        ↓
the station becomes Online
        ↓
the API Keys section allows an API Key to be created
```

Open this section in the account:

```text
API Keys
```

The current Weather Underground UI associates PWS API availability with an active station and recent uploads. If
the station stops uploading for an extended period, access may no longer be considered active. The UI currently
mentions a limit of 30 days since the last upload.

Store the API Key securely after creating it:

```env
WU_API_KEY=...
```

## 13. Verifying the API Key

Official documentation is available at
[PWS Current Conditions API](https://developer.weather.com/docs/openapi/pws-observations-current-conditions-2-0).

The endpoint is:

```text
https://api.weather.com/v2/pws/observations/current
```

Use metric units with:

```text
units=m
```

### curl test

```bash
export WU_STATION_ID='YOUR_STATION_ID'
read -s WU_API_KEY
export WU_API_KEY

curl -G \
  'https://api.weather.com/v2/pws/observations/current' \
  --data-urlencode "stationId=${WU_STATION_ID}" \
  --data-urlencode 'format=json' \
  --data-urlencode 'units=m' \
  --data-urlencode 'numericPrecision=decimal' \
  --data-urlencode "apiKey=${WU_API_KEY}"
```

With a valid API Key and active station, the API returns current observation data as JSON.

## 14. Two separate interfaces

```text
                        Weather Underground
                               │
           ┌───────────────────┴───────────────────┐
           │                                       │
           │ upload                                │ read
           ▼                                       ▼
 PWS Upload Protocol                       Weather API
           │                                       │
 Station ID + Station Key                  Station ID + API Key
```

### Upload

Uses:

```text
Station ID
Station Key
```

### Read API

Uses:

```text
Station ID
API Key
```

## 15. Common problems

### The station remains Offline

Check:

- the Station ID,
- the Station Key,
- `action=updateraw`,
- `dateutc=now` or a valid UTC timestamp,
- the upload endpoint response.

When the endpoint returns `success`, the upload was accepted.

### Station Key and API Key are swapped

Uploads use:

```text
PASSWORD = Station Key
```

Read API requests use:

```text
apiKey = API Key
```

### Celsius is sent to `tempf`

`tempf` expects Fahrenheit.

### hPa is sent to `baromin`

`baromin` expects inHg.

### An unavailable sensor is sent as zero

Do not send a parameter for a sensor that is not available. For example, omit `windspeedmph` when there is no
anemometer. `windspeedmph=0` means that calm wind was actually measured.

## 16. Recommended minimal operation

A complete commercial station is not required to keep a PWS active. A custom uploader can regularly send:

```text
temperature
humidity
pressure
```

from MQTT sensors.

A typical architecture is:

```text
ESPHome ──────────┐
Zigbee2MQTT ──────┤
Z-Wave2MQTT ──────┤
MQTT device ──────┘
        │
        ▼
   MQTT broker
        │
        ▼
  PWS uploader
        │
        ▼
Weather Underground
```

One Weather Underground observation may combine several physical sensors.

## 17. Recommendations for a production uploader

- keep credentials outside Git,
- send only actual measured values,
- omit unavailable or stale values,
- check the age of MQTT data,
- convert units only at the Weather Underground output boundary,
- check the Weather Underground response,
- avoid an aggressive retry loop during temporary Weather Underground failures.

A five-minute upload interval is a reasonable default for hobby use.

## 18. Useful links

- [PWS Network](https://www.wunderground.com/pws/overview)
- [Buying Guide](https://www.wunderground.com/pws/buying-guide)
- [Installation Guide](https://www.wunderground.com/pws/installation-guide)
- [PWS Upload Protocol](https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US)
- [PWS Current Conditions API](https://developer.weather.com/docs/openapi/pws-observations-current-conditions-2-0)
- [PWS Historical API](https://developer.weather.com/docs/openapi/pws-historical-2-0/get-pws-history-all)

## 19. Quick checklist

```text
[ ] Weather Underground account created or signed in
[ ] PWS registration opened
[ ] station location selected
[ ] Device Hardware = Other selected for a custom solution
[ ] PWS registered
[ ] Station ID stored securely
[ ] Station Key stored securely
[ ] test upload performed
[ ] upload endpoint response = success
[ ] PWS is Online
[ ] API Keys section opened
[ ] API Key created and stored securely
[ ] read API test performed
[ ] API returns station data as JSON
```

After every item is complete, the Weather Underground PWS and optional Weather API access are working.
