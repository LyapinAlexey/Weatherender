from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestApiRoutes:

    @pytest.mark.asyncio
    @patch("API.main.AsyncSessionLocal")
    async def test_health_check_v2(self, mock_session_local, api_client):
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        response = await api_client.get("/api/v2/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    @patch("API.main.AsyncSessionLocal")
    @patch("API.main.AsyncWeatherService.get_weather_async")
    async def test_get_weather_v2_success(
        self, mock_get_weather, mock_session_local, api_client, fake_weather_response
    ):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        mock_get_weather.return_value = fake_weather_response
        response = await api_client.get("/api/v2/weather?city=Berlin")
        data = response.json()
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        assert response.status_code == 200
        assert data["location"]["name"] == "Berlin"
        assert "snow_state" in data
        assert "status" in data["snow_state"]
        assert "snow_forecast" in data
        assert isinstance(data["snow_forecast"], list)
        assert len(data["snow_forecast"]) == 1
        assert data["snow_forecast"][0]["date"] == "2026-07-16"

    @pytest.mark.asyncio
    @patch("API.main.AsyncSessionLocal")
    @patch("API.main.AsyncWeatherService.get_weather_async")
    async def test_get_weather_v2_city_not_found(
        self, mock_get_weather, mock_session_local, api_client
    ):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        mock_get_weather.return_value = {
            "error": {"message": "City 'Invalid-city' not found."}
        }
        response = await api_client.get("/api/v2/weather?city=Invalid-city")
        data = response.json()
        assert response.status_code == 404
        assert data["detail"]["message"] == "City 'Invalid-city' not found."
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_v2_missing_city_returns_422(self, api_client):
        response = await api_client.get("/api/v2/weather")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_weather_v2_blank_city_returns_422(self, api_client):
        response = await api_client.get("/api/v2/weather?city=")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_weather_v2_city_all_spaces_returns_422(self, api_client):
        response = await api_client.get("/api/v2/weather?city=%20%20%20")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_weather_v2_city_too_long_returns_422(self, api_client):
        city = "long" * 30
        response = await api_client.get(f"/api/v2/weather?city={city}")
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("API.main.AsyncSessionLocal")
    async def test_health_check_v2_db_error_returns_503(
        self, mock_session_local, api_client
    ):
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("db down")
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        response = await api_client.get("/api/v2/health")
        assert response.status_code == 503

    @pytest.mark.asyncio
    @patch("API.main.AsyncSessionLocal")
    @patch("API.main.AsyncWeatherService.get_weather_async")
    async def test_get_weather_v2_no_forecast_days(
        self, mock_get_weather, mock_session_local, api_client
    ):
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session
        mock_session_local.return_value.__aexit__.return_value = None
        mock_get_weather.return_value = {
            "current": {"temp_c": 20, "condition": {"text": "Sunny"}},
            "forecast": {"forecastday": []},
        }
        response = await api_client.get("/api/v2/weather?city=London")
        data = response.json()
        assert response.status_code == 200
        assert data["snow_state"]["status"] == "No snow data"
        assert data["snow_forecast"] == []
