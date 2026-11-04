"""Live weather mapping: turns each API's response into the weather fields the models use.

The models only understand these fields, in these units (see training/features.py):
temperature degC, humidity %, pressure hPa at sea level, wind_speed m/s, wind_deg degrees,
wind_gust m/s, rainfall mm in the preceding hour, cloud_cover %.

A field the API didn't send becomes None, so it can be filled from the backfill. The exception
is rain: OpenWeather leaves "rain" out when it is dry, so missing means 0 mm.
"""


def from_openweather(data):
    """Map a response from /data/2.5/weather, requested with units=metric."""
    wind = data["wind"]
    return {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],  # already at sea level
        "wind_speed": wind["speed"],
        "wind_deg": wind.get("deg"),
        "wind_gust": wind.get("gust"),  # often left out in light wind
        "rainfall": data.get("rain", {}).get("1h", 0.0),
        "cloud_cover": data["clouds"]["all"],
    }


def from_tomorrow(data):
    """Map a response from /v4/weather/realtime, requested with units=metric."""
    values = data["data"]["values"]
    return {
        "temperature": values.get("temperature"),
        "humidity": values.get("humidity"),
        # Not pressureSurfaceLevel: Nairobi's surface pressure is far below its sea-level value
        "pressure": values.get("pressureSeaLevel"),
        "wind_speed": values.get("windSpeed"),
        "wind_deg": values.get("windDirection"),
        "wind_gust": values.get("windGust"),
        "rainfall": values.get("rainIntensity"),  # mm/h right now, used as the hour's rainfall
        "cloud_cover": values.get("cloudCover"),
    }
