from psycogreen.gevent import patch_psycopg

patch_psycopg()

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
from datetime import datetime

try:
    from .api_routes import api_bp, get_weather
    from .extensions import limiter
    from .scheduler import init_scheduler
    from .swagger_config import spec
except ImportError:
    from api_routes import api_bp, get_weather  # type: ignore[no-redef]
    from extensions import limiter  # type: ignore[no-redef]
    from scheduler import init_scheduler  # type: ignore[no-redef]
    from swagger_config import spec  # type: ignore[no-redef]

from flask import Flask, g, render_template, request, session
from flask_swagger_ui import get_swaggerui_blueprint
from flask_talisman import Talisman
from marshmallow import ValidationError
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import text

from bg_class import determine_bg_class
from config import Config
from logging_config import setup_logging
from models import SessionLocal, WeatherRequest
from schemas import CityRequestSchema
from services import WeatherService
from snow import get_snow_state

setup_logging()
logger = logging.getLogger(__name__)
SWAGGER_URL = "/apidocs"
API_URL = "/api/apispec.json"
app = Flask(__name__)


# Registered before Talisman: Flask runs after_request hooks in
# reverse registration order, so this hook must be registered
# before Talisman to ensure our CSP override is applied last.
@app.after_request
def add_security_headers(response):
    if request.path.startswith(SWAGGER_URL):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'"
        )
    return response


Talisman(app, force_https=False)
metrics = PrometheusMetrics(app)
limiter.init_app(app)
app.register_blueprint(api_bp)
swaggerui_bp = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_bp, url_prefix=SWAGGER_URL)
with app.app_context():
    spec.path(view=getattr(get_weather, "__wrapped__", get_weather), app=app)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB
Config.validate()
init_scheduler()
schema = CityRequestSchema()
app.secret_key = Config.SECRET_KEY


@app.teardown_appcontext
def shutdown_session(exception: BaseException | None = None) -> None:
    db_session = g.pop("db_session", None)
    if db_session is not None:
        db_session.close()


@app.before_request
def check_user_agent():
    if request.path == "/ping" or request.path == "/api/ping":
        return
    if not request.headers.get("User-Agent"):
        return {"error": "User-Agent header required"}, 400


@app.route("/", methods=["GET", "POST", "HEAD"])
@limiter.limit(
    "25 per minute"
)  # Limit to 25 requests per minute per IP x 4 workers = 100 requests per minute
def index() -> str:
    try:
        if request.method == "HEAD":
            return "", 200  # type: ignore[return-value]
        user_agent = request.headers.get("User-Agent", "").lower()
        if (
            "uptimerobot" in user_agent
            or "render" in user_agent
            or "headless" in user_agent
            or not user_agent
        ):
            return "", 200  # type: ignore[return-value]

        config_api_key = getattr(Config, "WEATHER_API_KEY", None)
        if "db_session" not in g:
            g.db_session = SessionLocal()

        city: str | None = None
        if request.method == "POST":
            city = request.form.get("city", "").strip()
            try:
                schema.load({"city": city})
            except ValidationError:
                error = "Error while fetching city: city must be a string and between 1 and 100 characters. City isn't valid"
                logger.warning(error)
                info_valide_err = WeatherRequest(
                    city=(
                        city
                        if (city and len(city) <= 100)
                        else (city or "")[:95] + "..."
                    ),
                    source="web",
                    success=0,
                    error_message=error,
                )
                g.db_session.add(info_valide_err)
                g.db_session.commit()
                return render_template(
                    "index.html",
                    error=error,
                    bg_class="sunny",
                    now=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    needs_key=not config_api_key and not session.get("api_key"),
                    show_key_input=not config_api_key,
                    elevation=0.0,
                    city=city,
                )

        active_api_key = config_api_key or session.get("api_key")
        if not active_api_key:
            return render_template(
                "index.html",
                error="API key is missing. Please enter your WeatherAPI key below.",
                bg_class="sunny",
                now=datetime.now().strftime("%Y-%m-%d %H:%M"),
                needs_key=True,
                show_key_input=True,
                elevation=0.0,
                city="",
            )

        if not city:
            user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            raw_city = WeatherService.get_city_by_ip(user_ip)
            city = (
                f"{raw_city[0]},{raw_city[1]}"
                if isinstance(raw_city, tuple)
                else raw_city
            )
            if city == "Robot-Datacenter":
                city = "London"
                robot_data = WeatherService.get_weather(city, api_key=active_api_key)
                return render_template(
                    "index.html",
                    weather=robot_data,
                    city=city,
                    bg_class="sunny",
                    now=datetime.now().strftime("%Y-%m-%d %H:%M"),
                    needs_key=False,
                    show_key_input=False,
                    elevation=0.0,
                )
            if not city:
                city = "London"

        if isinstance(city, tuple):
            query_param = f"{city[0]},{city[1]}"
        else:
            query_param = city

        data = WeatherService.get_weather(query_param, api_key=active_api_key)

        if "error" in data:
            logger.warning(
                f"Weather request failed for query='{query_param}': {data['error'].get('message')}"
            )
            info_err = WeatherRequest(
                city=str(query_param),
                source="web",
                success=0,
                error_message=data["error"].get("message"),
            )
            g.db_session.add(info_err)
            g.db_session.commit()
            if not config_api_key and "api_key" in session:
                session.pop("api_key", None)
            return render_template(
                "index.html",
                error=data["error"].get(
                    "message", "Invalid API Key or City not found."
                ),
                bg_class="sunny",
                now=datetime.now().strftime("%Y-%m-%d %H:%M"),
                needs_key=not config_api_key,
                show_key_input=not config_api_key,
                elevation=0.0,
                city=query_param,
            )
        else:
            info_suc = WeatherRequest(
                city=city,
                source="web",
                temp_c=round(data["current"]["temp_c"], 2),
                condition=data["current"]["condition"]["text"],
                success=1,
                error_message=None,
            )
            g.db_session.add(info_suc)
            g.db_session.commit()

        location_info = data.get("location", {})
        lat = location_info.get("lat")
        lon = location_info.get("lon")
        elevation = 0.0
        if lat is not None and lon is not None:
            elevation = WeatherService.get_elevation(lat, lon)

        base_station_alt = 200
        if elevation > base_station_alt:
            lapse_correction = (elevation - base_station_alt) / 100 * 0.65
            data["current"]["temp_c"] -= lapse_correction

        current = data.get("current", {})
        forecast_days = data.get("forecast", {}).get("forecastday", [])
        snow_info = {"status": "No snow data"}
        if forecast_days:
            today_day = forecast_days[0].get("day", {})
            snow_info = get_snow_state(
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

        hourly_forecast = []
        location_data = data.get("location", {})
        raw_localtime = location_data.get("localtime")
        current_hour_str = ""

        if raw_localtime:
            api_localtime = datetime.strptime(raw_localtime, "%Y-%m-%d %H:%M")
            current_hour_str = api_localtime.strftime("%Y-%m-%d %H:00")

        all_hours = [hour for day in forecast_days for hour in day.get("hour", [])]
        count = 0
        for hour in all_hours:
            if hour.get("time", "") >= current_hour_str:
                prob_precip = max(
                    hour.get("chance_of_rain", 0), hour.get("chance_of_snow", 0)
                )
                hourly_forecast.append(
                    {
                        "time": hour["time"].split(" ")[1],
                        "temp": round(hour["temp_c"], 2),
                        "precipitation": prob_precip,
                        "uv": round(hour["uv"]),
                        "pressure": round(hour["pressure_mb"] * 0.750062),
                    }
                )
                count += 1
                if count == 24:
                    break

        daily_forecast = []

        forecast_days = data.get("forecast", {}).get("forecastday", [])
        if not forecast_days:
            today_day = {}
        else:
            today_day = forecast_days[0].get("day", {})

        for i, day in enumerate(forecast_days):
            raw_date = day.get("date")
            if not raw_date:
                continue
            d_obj = datetime.strptime(raw_date, "%Y-%m-%d")
            day_info = day.get("day", {})
            chance_precip = max(
                day_info.get("daily_chance_of_rain", 0),
                day_info.get("daily_chance_of_snow", 0),
            )
            if i > 0:
                prev_day = forecast_days[i - 1]
                prev_day_info = prev_day.get("day", {})
                prev_day_max_temp = prev_day_info.get(
                    "maxtemp_c", day_info.get("avgtemp_c", 0)
                )
            else:
                prev_day_max_temp = day_info.get("maxtemp_c", 0)

            day_snow_state = get_snow_state(
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

            daily_forecast.append(
                {
                    "date": d_obj.strftime("%d.%m.%Y"),
                    "temp": round(day_info.get("avgtemp_c", 0.0), 2),
                    "precipitation": day_info.get("totalprecip_mm", 0.0),
                    "chance_precip": chance_precip,
                    "uv": round(day_info.get("uv", 0.0)),
                    "wind": day_info.get("maxwind_kph", 0.0),
                    "gust": round(
                        day_info.get("gust_kph", day_info.get("maxwind_kph", 0.0) * 1.2)
                    ),
                    "snow_state": day_snow_state,
                }
            )

        bg_class = determine_bg_class(data["current"]["condition"]["text"])
        return render_template(
            "index.html",
            weather=data,
            hourly=hourly_forecast,
            daily=daily_forecast,
            snow_info=snow_info,
            bg_class=bg_class,
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
            show_key_input=not config_api_key,
            elevation=elevation,
            city=query_param,
        )
    except Exception as e:
        logger.exception("CRITICAL EXCEPTION in index route: %s", e)
        return f"Internal Server Error: {str(e)}", 500  # type: ignore[return-value]


@app.route("/health")
def health_check() -> tuple[dict[str, str], int]:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        logger.info("Health check passed")
        return {"status": "ok"}, 200
    except Exception:
        logger.exception("Health check error")
        return {"status": "error", "detail": "503 Service Unavailable"}, 503
    finally:
        session.close()


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    app.run(host="0.0.0.0", port=port)
