import json
import os
import requests
from datetime import datetime, timezone

# Anchorage, Alaska Coordinates
LATITUDE = 61.2181
LONGITUDE = -149.9003
TIMEZONE = "America/Anchorage"

def fetch_anchorage_sun_and_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "daily": ["sunrise", "sunset", "daylight_duration"],
        "current": ["temperature_2m", "cloud_cover", "weather_code"],
        "temperature_unit": "fahrenheit",
        "forecast_days": 1
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # Format the log entry
    daily = data["daily"]
    current = data["current"]

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": daily["time"][0],
        "sunrise": daily["sunrise"][0],
        "sunset": daily["sunset"][0],
        "daylight_hours": round(daily["daylight_duration"][0] / 3600, 2),
        "current_temp_f": current["temperature_2m"],
        "cloud_cover_pct": current["cloud_cover"],
        "weather_code": current["weather_code"]
    }

    return log_entry

def save_to_json_log(log_entry, filename="data.json"):
    data_list = []
    
    # Load existing data if file exists
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                data_list = json.load(f)
        except json.JSONDecodeError:
            data_list = []

    # Append new daily log
    data_list.append(log_entry)

    # Write back to JSON file
    with open(filename, "w") as f:
        json.dump(data_list, f, indent=2)

    print(f"Successfully logged data for {log_entry['date']} to {filename}")

if __name__ == "__main__":
    entry = fetch_anchorage_sun_and_weather()
    save_to_json_log(entry)
