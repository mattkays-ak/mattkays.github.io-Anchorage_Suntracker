import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from update_data import (
    LATITUDE,
    LONGITUDE,
    TIMEZONE,
    WEATHER_CODES,
    calculate_sun_peak,
    fetch_noaa_tides,
    get_moon_phase_and_illumination,
    get_retry_session,
    save_to_json_log,
)


def find_missing_dates(filename="data.json"):
    """Finds all missing YYYY-MM-DD dates between the first entry in data.json and yesterday."""
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return []

    with open(filename, "r") as f:
        data_list = json.load(f)

    existing_dates = {item["date"] for item in data_list if "date" in item}
    if not existing_dates:
        print("No existing dates found in data.json.")
        return []

    start_date = datetime.strptime(min(existing_dates), "%Y-%m-%d").date()
    # Stop at yesterday in Anchorage time (today is handled by the normal forecast script)
    yesterday = (datetime.now(ZoneInfo(TIMEZONE)) - timedelta(days=1)).date()

    missing = []
    current = start_date
    while current <= yesterday:
        date_str = current.strftime("%Y-%m-%d")
        if date_str not in existing_dates:
            missing.append(date_str)
        current += timedelta(days=1)

    return missing


def backfill_missing_days(filename="data.json"):
    missing_dates = find_missing_dates(filename)
    if not missing_dates:
        print("No missing dates found! Your data.json is completely up to date.")
        return

    print(f"Found {len(missing_dates)} missing date(s): {', '.join(missing_dates)}")

    start_str = missing_dates[0]
    end_str = missing_dates[-1]

    session = get_retry_session()
    archive_url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "start_date": start_str,
        "end_date": end_str,
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "sunrise",
            "sunset",
            "daylight_duration",
        ],
        "temperature_unit": "fahrenheit",
    }

    print(f"Fetching historical weather from Open-Meteo ({start_str} to {end_str})...")
    response = session.get(archive_url, params=params, timeout=20)
    response.raise_for_status()
    daily = response.json().get("daily", {})

    # Map API arrays by date string for O(1) lookup
    times = daily.get("time", [])
    weather_by_date = {}
    for i, d_str in enumerate(times):
        weather_by_date[d_str] = {
            "weather_code": daily.get("weather_code", [])[i],
            "temp_max": daily.get("temperature_2m_max", [])[i],
            "temp_min": daily.get("temperature_2m_min", [])[i],
            "sunrise": daily.get("sunrise", [])[i],
            "sunset": daily.get("sunset", [])[i],
            "daylight": daily.get("daylight_duration", [])[i],
        }

    for date_str in missing_dates:
        w = weather_by_date.get(date_str, {})

        high_temp = f"{round(w['temp_max'])}°" if w.get("temp_max") is not None else "--°"
        low_temp = f"{round(w['temp_min'])}°" if w.get("temp_min") is not None else "--°"

        w_code = w.get("weather_code")
        condition = WEATHER_CODES.get(w_code, "Cloudy") if w_code is not None else "Unavailable"

        sunrise_str = "--"
        if w.get("sunrise"):
            sunrise_str = datetime.fromisoformat(w["sunrise"]).strftime("%I:%M %p").lstrip("0")

        sunset_str = "--"
        if w.get("sunset"):
            sunset_str = datetime.fromisoformat(w["sunset"]).strftime("%I:%M %p").lstrip("0")

        daylight_str = "--"
        if w.get("daylight") is not None:
            total_seconds = int(w["daylight"])
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            daylight_str = f"{hours}h {minutes}m"

        moon_phase, moon_illumination = get_moon_phase_and_illumination(date_str)
        sun_peak = calculate_sun_peak(date_str)
        high_tide, low_tide = fetch_noaa_tides(date_str, session)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": date_str,
            "high": high_temp,
            "low": low_temp,
            "condition": condition,
            "weather_code": w_code,
            "sunrise": sunrise_str,
            "sunset": sunset_str,
            "daylight": daylight_str,
            "sun_peak": sun_peak,
            "moon_phase": moon_phase,
            "moon_illumination": moon_illumination,
            "high_tide": high_tide,
            "low_tide": low_tide,
        }

        save_to_json_log(log_entry, filename=filename)
        print(f"Backfilled {date_str}: High {high_temp}, Low {low_temp}, {condition}, Tides {high_tide} / {low_tide}")

    print("Backfill complete!")


if __name__ == "__main__":
    backfill_missing_days()
