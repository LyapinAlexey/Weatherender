import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import logging
import random
from datetime import datetime

try:
    from .api_routes import api_bp, get_weather
except ImportError:
    from api_routes import api_bp, get_weather  # type: ignore[no-redef]
from flask import Flask, g, render_template, request, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_swagger_ui import get_swaggerui_blueprint
from flask_talisman import Talisman
from marshmallow import ValidationError
from prometheus_flask_exporter import PrometheusMetrics
from sqlalchemy import text

from bg_class import determine_bg_class
from config import Config
from dbclear import clear
from logging_config import setup_logging
from models import SessionLocal, WeatherRequest
from schemas import CityRequestSchema
from services import WeatherService

try:
    from .swagger_config import spec
except ImportError:
    from swagger_config import spec  # type: ignore[no-redef]

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
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri="memory://",
)
app.register_blueprint(api_bp)
swaggerui_bp = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_bp, url_prefix=SWAGGER_URL)
with app.test_request_context():
    spec.path(view=get_weather)
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB
Config.validate()
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
    if request.method == "POST":
        city = request.form.get("city", "").strip()
        try:
            schema.load({"city": city})
        except ValidationError:
            error = "Error while fetching city: city must be a string and between 1 and 100 characters. City isn't valid"
            logger.warning(error)
            info_valide_err = WeatherRequest(
                city=city if len(city) <= 100 else city[:95] + "...",
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
                needs_key=(
                    True if not config_api_key and not session.get("api_key") else False
                ),
            )
        """If you will do api-key validation:
        user_api_key = request.form.get("api_key", "").strip()
        if user_api_key:
            session["api_key"] = user_api_key
            return redirect(url_for("index"))"""
    else:
        city = None
    active_api_key = config_api_key or session.get("api_key")
    if not active_api_key:
        return render_template(
            "index.html",
            error="API key is missing. Please enter your WeatherAPI key below.",
            bg_class="sunny",
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
            needs_key=True,
        )
    if not city:
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        city = WeatherService.get_city_by_ip(user_ip)
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
            )
        if not city:
            city = "London"
    data = WeatherService.get_weather(city, api_key=active_api_key)
    if "error" in data:
        logger.warning(
            f"Weather request failed for city='{city}': {data['error'].get('message')}"
        )
        info_err = WeatherRequest(
            city=city,
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
            error=data["error"].get("message", "Invalid API Key or City not found."),
            bg_class="sunny",
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
            needs_key=not config_api_key,
        )
    else:
        info_suc = WeatherRequest(
            city=city,
            source="web",
            temp_c=data["current"]["temp_c"],
            condition=data["current"]["condition"]["text"],
            success=1,
            error_message=None,
        )
        g.db_session.add(info_suc)
        g.db_session.commit()
    hourly_forecast = []
    api_localtime = datetime.strptime(data["location"]["localtime"], "%Y-%m-%d %H:%M")
    current_hour_str = api_localtime.strftime("%Y-%m-%d %H:00")
    all_hours = [
        hour for day in data["forecast"]["forecastday"] for hour in day["hour"]
    ]
    count = 0
    for hour in all_hours:
        if hour["time"] >= current_hour_str:
            prob_precip = max(
                hour.get("chance_of_rain", 0), hour.get("chance_of_snow", 0)
            )
            hourly_forecast.append(
                {
                    "time": hour["time"].split(" ")[1],
                    "temp": hour["temp_c"],
                    "precipitation": prob_precip,
                    "uv": round(hour["uv"]),
                    "pressure": round(hour["pressure_mb"] * 0.750062),
                }
            )
            count += 1
            if count == 24:
                break
    daily_forecast = []
    for day in data["forecast"]["forecastday"]:
        d_obj = datetime.strptime(day["date"], "%Y-%m-%d")
        daily_forecast.append(
            {
                "date": d_obj.strftime("%d.%m.%Y"),
                "temp": day["day"]["avgtemp_c"],
                "precipitation": day["day"]["totalprecip_mm"],
                "uv": round(day["day"]["uv"]),
                "wind": day["day"]["maxwind_kph"],
                "gust": round(
                    day["day"].get("gust_kph", day["day"]["maxwind_kph"] * 1.2)
                ),
            }
        )
    bg_class = determine_bg_class(data["current"]["condition"]["text"])
    if random.random() < 0.01:
        clear(g.db_session)
    return render_template(
        "index.html",
        weather=data,
        hourly=hourly_forecast,
        daily=daily_forecast,
        bg_class=bg_class,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        show_key_input=not config_api_key,
    )


@app.route("/health")
def health_check() -> tuple[dict[str, str], int]:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception:
        logger.exception("Health check error")
        return {"status": "error", "detail": "503 Service Unavailable"}, 503
    finally:
        session.close()


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    app.run(host="0.0.0.0", port=port)
