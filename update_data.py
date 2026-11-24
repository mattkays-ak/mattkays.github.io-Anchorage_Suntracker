import json
import os
import math
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LATITUDE = 61.2181
LONGITUDE = -149.9003
TIMEZONE = "America/Anchorage"
NOAA_STATION_ID = "9455920"  # Anchorage, AK NOAA Station

WEATHER_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers"
}


def get_retry_session():
    """Creates a requests Session with exponential backoff and retry logic."""
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=2,  # waits 2s, 4s, 8s, 16s between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


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


def fetch_noaa_tides(date_str, session):
    """Fetches high and low tide predictions from NOAA CO-OPS API for Anchorage."""
    formatted_date = date_str.replace("-", "")
    url = (
        f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        f"?begin_date={formatted_date}&end_date={formatted_date}"
        f"&station={NOAA_STATION_ID}&product=predictions&datum=MLLW"
        f"&time_zone=lst_ldt&units=english&interval=hilo&format=json"
    )

    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        predictions = data.get("predictions", [])

        highs = [float(p["v"]) for p in predictions if p["type"] == "H"]
        lows = [float(p["v"]) for p in predictions if p["type"] == "L"]

        high_str = f"{max(highs):.1f} ft" if highs else "-- ft"
        low_str = f"{min(lows):.1f} ft" if lows else "-- ft"
        return high_str, low_str
    except Exception as e:
        print(f"NOAA Tide Fetch Error: {e}")
        return "-- ft", "-- ft"


def fetch_anchorage_sun_and_weather():
    session = get_retry_session()
    today_date = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")

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

    # Safe fallback defaults in case Open-Meteo times out after all retries
    high_temp = "--°"
    low_temp = "--°"
    condition = "Unavailable"
    weather_code = None
    sunrise_str = "--"
    sunset_str = "--"
    daylight_str = "--"

    try:
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        daily = data.get("daily", {})
        current = data.get("current", {})

        if daily.get("time"):
            today_date = daily["time"][0]

        if daily.get("temperature_2m_max") and daily["temperature_2m_max"][0] is not None:
            high_temp = f"{round(daily['temperature_2m_max'][0])}°"
        if daily.get("temperature_2m_min") and daily["temperature_2m_min"][0] is not None:
            low_temp = f"{round(daily['temperature_2m_min'][0])}°"

        weather_code = current.get("weather_code")
        if weather_code is not None:
            condition = WEATHER_CODES.get(weather_code, "Cloudy")

        if daily.get("sunrise") and daily["sunrise"][0]:
            sunrise_dt = datetime.fromisoformat(daily["sunrise"][0])
            sunrise_str = sunrise_dt.strftime("%I:%M %p").lstrip("0")

        if daily.get("sunset") and daily["sunset"][0]:
            sunset_dt = datetime.fromisoformat(daily["sunset"][0])
            sunset_str = sunset_dt.strftime("%I:%M %p").lstrip("0")

        if daily.get("daylight_duration") and daily["daylight_duration"][0] is not None:
            total_seconds = int(daily["daylight_duration"][0])
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            daylight_str = f"{hours}h {minutes}m"

    except requests.exceptions.RequestException as e:
        print(f"Open-Meteo API failed after retries (recording fallback entry): {e}")

    moon_phase, moon_illumination = get_moon_phase_and_illumination(today_date)
    sun_peak = calculate_sun_peak(today_date)
    high_tide, low_tide = fetch_noaa_tides(today_date, session)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": today_date,
        "high": high_temp,
        "low": low_temp,
        "condition": condition,
        "weather_code": weather_code,
        "sunrise": sunrise_str,
        "sunset": sunset_str,
        "daylight": daylight_str,
        "sun_peak": sun_peak,
        "moon_phase": moon_phase,
        "moon_illumination": moon_illumination,
        "high_tide": high_tide,
        "low_tide": low_tide
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
    data_list.sort(key=lambda x: x.get("date", ""))

    with open(filename, "w") as f:
        json.dump(data_list, f, indent=2)


if __name__ == "__main__":
    entry = fetch_anchorage_sun_and_weather()
    save_to_json_log(entry)
