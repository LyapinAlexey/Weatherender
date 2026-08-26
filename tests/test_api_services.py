from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from httpx import Response

from API.async_services import AsyncWeatherService
from config import Config


@pytest.mark.asyncio
class TestAsyncWeatherService:
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_cache_hit(self, mock_cache_get):
        mock_cache_get.return_value = {"cached": "data"}
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "fake-key"
            )
            assert result == {"cached": "data"}

    async def test_get_weather_async_missing_api_key(self, monkeypatch):
        monkeypatch.setattr(Config, "WEATHER_API_KEY", None)
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", api_key=None
            )
            assert "error" in result
            assert "API key is missing" in result["error"]["message"]

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_success_api_call(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(
            return_value=Response(
                200,
                json={"location": {"name": "Berlin"}},
                headers={"Content-Type": "application/json"},
            )
        )
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "fake-key"
            )
            assert result["location"]["name"] == "Berlin"

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_unauthorized(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(return_value=Response(401))
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "bad-key"
            )
            assert "Invalid API key" in result["error"]["message"]

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_city_not_found(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(return_value=Response(400))
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "UnknownCity", "fake-key"
            )
            assert "not found" in result["error"]["message"]

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_invalid_content_type(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(
            return_value=Response(
                200, text="<html>Blocked</html>", headers={"Content-Type": "text/html"}
            )
        )
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "fake-key"
            )
            assert "invalid response format" in result["error"]["message"]

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_other_status_error(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(
            return_value=Response(500, headers={"Content-Type": "application/json"})
        )
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "fake-key"
            )
            assert "error" in result
            assert (
                "Weather service error. Status code: 500" in result["error"]["message"]
            )

    @respx.mock
    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_json_decode_error(self, mock_cache_get):
        mock_cache_get.return_value = None
        respx.get(Config.WEATHER_URL).mock(
            return_value=Response(
                200, text="invalid json", headers={"Content-Type": "application/json"}
            )
        )
        async with httpx.AsyncClient() as client:
            result = await AsyncWeatherService.get_weather_async(
                client, "Berlin", "fake-key"
            )
            assert "Error parsing response" in result["error"]["message"]

    @patch("API.async_services.cache_service.get", new_callable=AsyncMock)
    async def test_get_weather_async_tuple_city(self, mock_cache_get):
        mock_cache_get.return_value = None

        @respx.mock
        async def run_test():
            respx.get(Config.WEATHER_URL).mock(
                return_value=Response(
                    200,
                    json={"loc": "ok"},
                    headers={"Content-Type": "application/json"},
                )
            )
            async with httpx.AsyncClient() as client:
                res = await AsyncWeatherService.get_weather_async(
                    client, ("55.75", "37.61"), "fake-key"
                )
                assert res == {"loc": "ok"}

        await run_test()
