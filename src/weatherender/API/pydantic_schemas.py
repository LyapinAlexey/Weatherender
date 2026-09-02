from pydantic import BaseModel, Field, field_validator


class SnowState(BaseModel):
    status: str


class SnowForecast(BaseModel):
    date: str
    snow_state: SnowState


class WeatherResponseV2(BaseModel):
    location: dict = Field(default_factory=dict)
    current: dict = Field(default_factory=dict)
    forecast: dict = Field(default_factory=dict)
    snow_state: SnowState
    snow_forecast: list[SnowForecast]


class WeatherQueryParams(BaseModel):
    city: str = Field(..., min_length=1, max_length=100)

    @field_validator("city")
    @classmethod
    def city_not_blank(cls, city: str) -> str:
        stripped = city.strip()
        if not stripped:
            raise ValueError("city must not be blank or whitespace-only")
        return stripped
