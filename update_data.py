import json
import os
import requests
from datetime import datetime, timezone

LATITUDE = 61.2181
LONGITUDE = -149.9003
TIMEZONE = "America/Anchorage"

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers"
}

def fetch_anchorage_sun_and_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "daily": ["temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "daylight_duration", "weather_code"],
        "current": ["temperature_2m", "cloud_cover", "weather_code"],
        "temperature_unit": "fahrenheit",
        "forecast_days": 1
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    daily = data["daily"]
    current = data["current"]

    # Format times into hh:mm
    sunrise_dt = datetime.fromisoformat(daily["sunrise"][0])
    sunset_dt = datetime.fromisoformat(daily["sunset"][0])
    
    total_seconds = int(daily["daylight_duration"][0])
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": daily["time"][0],
        "high": f"{round(daily['temperature_2m_max'][0])}°",
        "low": f"{round(daily['temperature_2m_min'][0])}°",
        "condition": WEATHER_CODES.get(current["weather_code"], "Cloudy"),
        "sunrise": sunrise_dt.strftime("%I:%M %p").lstrip('0'),
        "sunset": sunset_dt.strftime("%I:%M %p").lstrip('0'),
        "daylight": f"{hours}h {minutes}m",
        "weather_code": current["weather_code"],
        "cloud_cover": f"{current['cloud_cover']}% cloud cover"
    }

    return log_entry

def save_to_json_log(log_entry, filename="data.json"):
    data_list = []
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data_list = json.load(f)
        except json.JSONDecodeError:
            data_list = []

    # Overwrite or append based on date
    data_list = [item for item in data_list if item.get("date") != log_entry["date"]]
    data_list.append(log_entry)

    with open(filename, "w") as f:
        json.dump(data_list, f, indent=2)

    print(f"Successfully logged data for {log_entry['date']}")

if __name__ == "__main__":
    entry = fetch_anchorage_sun_and_weather()
    save_to_json_log(entry)
