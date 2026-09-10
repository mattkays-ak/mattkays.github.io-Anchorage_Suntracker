import json
import os
import requests
import math
from datetime import datetime, timezone

LATITUDE = 61.2181
LONGITUDE = -149.9003
TIMEZONE = "America/Anchorage"

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers"
}

def calculate_sun_peak(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_of_year = dt.timetuple().tm_yday
    declination = 23.45 * math.sin(math.radians((360 / 365) * (day_of_year - 81)))
    max_elevation = max(0.0, 90.0 - LATITUDE + declination)
    return f"{round(max_elevation, 1)}°"

def get_moon_phase_and_illumination(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    ref_date = datetime(2024, 1, 11)
    days_since_ref = (dt - ref_date).days + (dt.hour / 24.0)
    
    lunar_cycle = 29.53058770576
    phase_value = (days_since_ref % lunar_cycle) / lunar_cycle

    illumination = round((1 - math.cos(phase_value * 2 * math.pi)) / 2 * 100)

    if phase_value < 0.03 or phase_value >= 0.97:
        phase_name = "New Moon"
    elif phase_value < 0.22:
        phase_name = "Waxing Crescent"
    elif phase_value < 0.28:
        phase_name = "First Quarter"
    elif phase_value < 0.47:
        phase_name = "Waxing Gibbous"
    elif phase_value < 0.53:
        phase_name = "Full Moon"
    elif phase_value < 0.72:
        phase_name = "Waning Gibbous"
    elif phase_value < 0.78:
        phase_name = "Last Quarter"
    else:
        phase_name = "Waning Crescent"

    return phase_name, f"{illumination}% illuminated"

def fetch_anchorage_sun_and_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "daily": ["temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "daylight_duration"],
        "current": ["temperature_2m", "weather_code"],
        "temperature_unit": "fahrenheit",
        "forecast_days": 1
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    daily = data["daily"]
    current = data["current"]
    today_date = daily["time"][0]

    sunrise_dt = datetime.fromisoformat(daily["sunrise"][0])
    sunset_dt = datetime.fromisoformat(daily["sunset"][0])

    total_seconds = int(daily["daylight_duration"][0])
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    moon_phase, moon_illumination = get_moon_phase_and_illumination(today_date)
    sun_peak = calculate_sun_peak(today_date)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": today_date,
        "high": f"{round(daily['temperature_2m_max'][0])}°",
        "low": f"{round(daily['temperature_2m_min'][0])}°",
        "condition": WEATHER_CODES.get(current["weather_code"], "Cloudy"),
        "weather_code": current["weather_code"],  # ADDED THIS FIELD
        "sunrise": sunrise_dt.strftime("%I:%M %p").lstrip("0"),
        "sunset": sunset_dt.strftime("%I:%M %p").lstrip("0"),
        "daylight": f"{hours}h {minutes}m",
        "sun_peak": sun_peak,
        "moon_phase": moon_phase,
        "moon_illumination": moon_illumination
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

    data_list = [item for item in data_list if item.get("date") != log_entry["date"]]
    data_list.append(log_entry)

    with open(filename, "w") as f:
        json.dump(data_list, f, indent=2)

if __name__ == "__main__":
    entry = fetch_anchorage_sun_and_weather()
    save_to_json_log(entry)
