def get_snow_state(
    temp_c: float = 0.0,
    min_temp_c: float = 0.0,
    max_temp_c: float = 0.0,
    humidity: int = 50,
    snow_depth_cm: float = 0.0,
    snow_24h_cm: float = 0.0,
    wind_kph: float = 0.0,
    cloud_cover: int = 0,
    condition_text: str = "",
    prev_day_max_temp: float = 0.0,
    totalprecip_mm: float = 0.0,
    will_it_snow: int = 0,
    totalsnow_cm: float = 0.0,
) -> dict:
    """Classify current snow conditions based on temperature, humidity,
    wind, and precipitation data, returning a dict with a `status` key
    (e.g. "Powder", "Wet snow", "Ice crust", "No snow")."""

    cond = condition_text.lower()
    snow_density = (totalprecip_mm / (snow_24h_cm * 10)) if snow_24h_cm > 0 else 0.1

    if temp_c > 15 or (will_it_snow == 0 and totalsnow_cm <= 0 and snow_depth_cm <= 0):
        return {"status": "No snow"}

    if snow_depth_cm > 0 or snow_24h_cm > 0:
        is_freeze_thaw = max_temp_c > 0 and min_temp_c < 0
        if (
            is_freeze_thaw
            or prev_day_max_temp > 2.0
            or "ice" in cond
            or "freezing" in cond
        ):
            if snow_24h_cm < 5:
                return {"status": "Ice crust"}

    if temp_c > 0.5 or (temp_c >= -0.5 and humidity > 80):
        if cloud_cover < 30 and temp_c > 0:
            return {"status": "Spring slush"}
        return {"status": "Wet snow"}

    if temp_c <= -5 and snow_24h_cm >= 15:
        if snow_density < 0.08:
            return {"status": "Dry champagne powder!"}
        if wind_kph > 30:
            return {"status": "Wind-drifted powder"}
        return {"status": "Powder"}

    if wind_kph > 35:
        return {"status": "Wind slab"}

    if temp_c <= 0:
        if snow_24h_cm >= 8:
            return {"status": "Fresh, firm snow"}
        return {"status": "Hard-packed snow"}

    return {"status": "Unstable conditions"}
