from flask import Blueprint, request
from marshmallow import ValidationError

try:
    from .swagger_config import spec
except ImportError:
    from swagger_config import spec  # type: ignore[no-redef]
from schemas import CityRequestSchema
from services import WeatherService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/weather")
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
          description: Successful response with weather data
        400:
          description: Invalid or missing city parameter
        404:
          description: City not found
    """
    schema = CityRequestSchema()
    data = request.args.to_dict()
    try:
        load_data = schema.load(data)
    except ValidationError as e:
        return {"error": e.messages}, 400
    city = load_data["city"]
    weather_data = WeatherService.get_weather(city=city)
    if "error" in weather_data:
        return {"error": weather_data["error"]}, 404
    return weather_data, 200


@api_bp.route("/apispec.json")
def get_apispec():
    return spec.to_dict()
