# Prediction format

The output of the ML service. The backend stores it and the UI displays it, so the database
tables and screens are built against this format.

## One prediction

One record per location, per event, per prediction run:

```json
{
  "location": "Westlands",
  "event": "heavy_rain",
  "category": "rain",
  "probability": 0.62,
  "band": "likely",
  "issued_at": "2026-11-04T09:00:00Z",
  "valid_from": "2026-11-04T09:00:00Z",
  "valid_to": "2026-11-04T15:00:00Z",
  "model_version": "20261104-0900"
}
```

| Field | Type | Meaning |
|---|---|---|
| `location` | text | One of the 23 serving locations |
| `event` | text | One of the 7 events below |
| `category` | text | `rain`, `temperature`, `sky` or `wind`; used to group events in the UI |
| `probability` | number, 0-1 | The model's raw output; not a calibrated chance |
| `band` | text | `very_unlikely`, `unlikely`, `likely` or `very_likely` |
| `issued_at` | UTC time | The latest weather hour the prediction is based on |
| `valid_from` | UTC time | Start of the period predicted; same as `issued_at` |
| `valid_to` | UTC time | End of the period predicted |
| `model_version` | text | The `version` stored in the model bundle |

All times are UTC. The UI converts them to East Africa Time (UTC+3).

Show users the `band`, not the `probability`, because the probabilities are not calibrated.
Each event has its own cut-offs, so the same probability can mean different bands for
different events.

## Events

| `event` | `category` | Predicts | Window |
|---|---|---|---|
| `rain` | `rain` | At least 1 mm of rain | 6 h |
| `heavy_rain` | `rain` | At least 10 mm of rain | 6 h |
| `flood_risk` | `rain` | Past 48 h + next 24 h rain of at least 50 mm, with at least 10 mm still to come | 24 h |
| `hot` | `temperature` | Temperature reaches 35 degC | 6 h |
| `cold` | `temperature` | Temperature falls to 12 degC | 6 h |
| `sunny` | `sky` | Average cloud cover of 30% or less | 6 h |
| `strong_wind` | `wind` | Gusts of at least 12 m/s (about 43 km/h) | 6 h |

`storm` is evaluated in the report but is not a user alert.

## Bands

Each event's cut-offs are stored in the model bundle under `events[event]["cutoffs"]`:

| `band` | Condition |
|---|---|
| `very_unlikely` | `probability < unlikely` |
| `unlikely` | `unlikely <= probability < likely` |
| `likely` | `likely <= probability < very_likely` |
| `very_likely` | `probability >= very_likely` |

An event's `likely` and `very_likely` cut-offs can be equal. That event then never shows `likely`.

## One prediction run

The ML service returns all 7 events for a location together:

```json
{
  "location": "Westlands",
  "issued_at": "2026-11-04T09:00:00Z",
  "model_version": "20261104-0900",
  "predictions": [
    {
      "event": "heavy_rain",
      "category": "rain",
      "probability": 0.62,
      "band": "likely",
      "valid_from": "2026-11-04T09:00:00Z",
      "valid_to": "2026-11-04T15:00:00Z"
    }
  ]
}
```

`predictions` always has 7 items; the example shows one.

## Live readings

The backend gets predictions from `POST /predict/{location}/live`, sending the current reading
from OpenWeather and Tomorrow.io:

```json
{ "temperature": 19.96, "humidity": 77, "pressure": 1018, "wind_speed": 3.09, "wind_deg": 80,
  "wind_gust": 2.7, "rainfall": 0.19, "cloud_cover": 75 }
```

The ML service fetches the past 48 hours from Open-Meteo and replaces the newest hour's values
with the live ones. A field sent as `null` keeps Open-Meteo's estimate. The response is a
prediction run with one extra field, `current`, holding the newest hour as the models saw it:

```json
"current": {
  "timestamp": "2026-11-12T05:00:00Z",
  "values": { "temperature": 19.96, "humidity": 77.0, "...": "..." },
  "live_fields": ["cloud_cover", "humidity", "pressure", "rainfall", "temperature", "wind_deg", "wind_gust", "wind_speed"]
}
```

Fields missing from `live_fields` are Open-Meteo estimates.
