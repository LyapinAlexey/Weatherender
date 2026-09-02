import pytest

from weatherender.snow import get_snow_state


@pytest.mark.parametrize(  # Parametrized tests
    "params,expected_status",
    [
        # 1. No snow
        (
            {
                "snow_depth_cm": 0.0,
                "snow_24h_cm": 0.0,
                "totalprecip_mm": 0.0,
            },
            "No snow",
        ),
        # 2. Ice crust
        (
            {
                "snow_depth_cm": 10.0,
                "snow_24h_cm": 2.0,
                "max_temp_c": 4.0,
                "min_temp_c": -2.0,
                "totalprecip_mm": 1.0,
            },
            "Ice crust",
        ),
        # 3. Spring slush
        (
            {
                "temp_c": 1.5,
                "cloud_cover": 20,
                "snow_depth_cm": 10.0,
                "totalprecip_mm": 2.0,
            },
            "Spring slush",
        ),
        # 4. Wet snow
        (
            {
                "temp_c": 1.5,
                "cloud_cover": 80,
                "snow_depth_cm": 10.0,
                "totalprecip_mm": 2.0,
            },
            "Wet snow",
        ),
        # 5. Dry powder
        (
            {
                "temp_c": -6.0,
                "snow_24h_cm": 20.0,
                "snow_depth_cm": 30.0,
                "totalprecip_mm": 1.0,
            },
            "Dry champagne powder!",
        ),
        # 6. Wind-drifted powder
        (
            {
                "temp_c": -6.0,
                "snow_24h_cm": 20.0,
                "snow_depth_cm": 30.0,
                "totalprecip_mm": 18.0,
                "wind_kph": 32.0,
            },
            "Wind-drifted powder",
        ),
        # 7. Powder
        (
            {
                "temp_c": -6.0,
                "snow_24h_cm": 20.0,
                "snow_depth_cm": 30.0,
                "totalprecip_mm": 18.0,
                "wind_kph": 15.0,
            },
            "Powder",
        ),
        # 8. Bargeboard
        (
            {
                "temp_c": -2.0,
                "snow_depth_cm": 15.0,
                "snow_24h_cm": 3.0,
                "wind_kph": 40.0,
                "totalprecip_mm": 2.0,
            },
            "Wind slab",
        ),
        # 9. Packed snow
        (
            {
                "temp_c": -2.0,
                "snow_depth_cm": 20.0,
                "snow_24h_cm": 10.0,
                "wind_kph": 10.0,
                "totalprecip_mm": 5.0,
            },
            "Fresh, firm snow",
        ),
        # 10. Hard-packed snow
        (
            {
                "temp_c": -2.0,
                "snow_depth_cm": 20.0,
                "snow_24h_cm": 2.0,
                "wind_kph": 10.0,
                "totalprecip_mm": 1.0,
            },
            "Hard-packed snow",
        ),
        # 11. Unstable conditions
        (
            {
                "temp_c": 0.2,
                "humidity": 40,
                "snow_depth_cm": 10.0,
                "snow_24h_cm": 2.0,
                "wind_kph": 10.0,
                "totalprecip_mm": 1.0,
            },
            "Unstable conditions",
        ),
    ],
)
def test_get_snow_state(params, expected_status):
    result = get_snow_state(**params)
    assert result["status"] == expected_status
