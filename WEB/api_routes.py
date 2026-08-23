from flask import Blueprint, request
from marshmallow import ValidationError

from models import SessionLocal, WeatherRequest

try:
    from .extensions import limiter
    from .swagger_config import spec
except ImportError:
    from swagger_config import spec  # type: ignore[no-redef]
    from extensions import limiter  # type: ignore[no-redef]

from flask import g

from schemas import CityRequestSchema
from services import WeatherService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/weather")
@limiter.limit("25 per minute")
def get_weather():
    """Get weather by city name
    ---
    get:
      parameters:
        - in: query
          name: city
          schema:
            type: string
          required: true
          description: Name of the city
      responses:
        200:
          description: >
            Successful response with weather data. In addition to the raw
            WeatherAPI payload (location/current/forecast), the response
            includes two derived fields:
            - snow_state: object with a `status` string describing today's
              snow conditions (e.g. "Powder", "Wet snow", "No snow data" if
              no forecast data is available).
            - snow_forecast: array of objects, one per forecast day, each
              with `date` (string) and `snow_state` (object with `status`),
              covering the same days as forecast.forecastday.
        400:
          description: Invalid or missing city parameter
        404:
          description: City not found
    """
    if "db_session" not in g:
        g.db_session = SessionLocal()
    schema = CityRequestSchema()
    data = request.args.to_dict()
    try:
        load_data = schema.load(data)
    except ValidationError as e:
        error = "Error while fetching city: city must be a string and between 1 and 100 characters. City isn't valid"
        info_valide_err = WeatherRequest(
            city=(
                data.get("city", "")
                if (data.get("city") and len(data.get("city", "")) <= 100)
                else (data.get("city") or "")[:95] + "..."
            ),
            source="api",
            success=0,
            error_message=error,
        )
        g.db_session.add(info_valide_err)
        g.db_session.commit()
        return {"error": e.messages}, 400
    city = load_data["city"]
    weather_data = WeatherService.get_weather(city=city)
    if "error" in weather_data:
        info_err = WeatherRequest(
            city=str(city),
            source="api",
            success=0,
            error_message=weather_data["error"].get("message"),
        )
        g.db_session.add(info_err)
        g.db_session.commit()
        return {"error": weather_data["error"]}, 404
    else:
        info_suc = WeatherRequest(
            city=str(city),
            source="api",
            temp_c=round(weather_data["current"]["temp_c"], 2),
            condition=weather_data["current"]["condition"]["text"],
            success=1,
            error_message=None,
        )
        g.db_session.add(info_suc)
        g.db_session.commit()
    forecast_days = weather_data.get("forecast", {}).get("forecastday", [])
    current = weather_data.get("current", {})

    if forecast_days:
        today_day = forecast_days[0].get("day", {})
        weather_data["snow_state"] = WeatherService.get_snow_state(
            temp_c=current.get("temp_c", 0),
            min_temp_c=today_day.get("mintemp_c", current.get("temp_c", 0)),
            max_temp_c=today_day.get("maxtemp_c", current.get("temp_c", 0)),
            humidity=current.get("humidity", 50),
            snow_depth_cm=today_day.get("totalsnow_cm", 0.0),
            snow_24h_cm=today_day.get("totalsnow_cm", 0.0),
            wind_kph=current.get("wind_kph", 0),
            cloud_cover=current.get("cloud", 0),
            condition_text=current.get("condition", {}).get("text", ""),
            prev_day_max_temp=today_day.get("maxtemp_c", current.get("temp_c", 0)),
            totalprecip_mm=today_day.get("totalprecip_mm", 0.0),
            will_it_snow=today_day.get("daily_will_it_snow", 0),
            totalsnow_cm=today_day.get("totalsnow_cm", 0.0),
        )
    else:
        weather_data["snow_state"] = {"status": "No snow data"}

    snow_forecast = []
    for i, day in enumerate(forecast_days):
        day_info = day.get("day", {})
        if i > 0:
            prev_day_info = forecast_days[i - 1].get("day", {})
            prev_day_max_temp = prev_day_info.get(
                "maxtemp_c", day_info.get("avgtemp_c", 0)
            )
        else:
            prev_day_max_temp = day_info.get("maxtemp_c", 0)

        day_snow_state = WeatherService.get_snow_state(
            temp_c=day_info.get("avgtemp_c", 0),
            min_temp_c=day_info.get("mintemp_c", 0),
            max_temp_c=day_info.get("maxtemp_c", 0),
            humidity=day_info.get("avghumidity", 50),
            snow_depth_cm=day_info.get("totalsnow_cm", 0.0),
            snow_24h_cm=day_info.get("totalsnow_cm", 0.0),
            wind_kph=day_info.get("maxwind_kph", 0),
            cloud_cover=50,
            condition_text=day_info.get("condition", {}).get("text", ""),
            prev_day_max_temp=prev_day_max_temp,
            totalprecip_mm=day_info.get("totalprecip_mm", 0.0),
            will_it_snow=day_info.get("daily_will_it_snow", 0),
            totalsnow_cm=day_info.get("totalsnow_cm", 0.0),
        )
        snow_forecast.append(
            {
                "date": day.get("date"),
                "snow_state": day_snow_state,
            }
        )

    weather_data["snow_forecast"] = snow_forecast
    return weather_data, 200


@api_bp.route("/apispec.json")
@limiter.limit("25 per minute")
def get_apispec():
    return spec.to_dict()


@api_bp.route("/ping", methods=["GET", "HEAD"])
def ping() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200
