import copy
from unittest.mock import MagicMock, patch

import pytest

from CLI.main import Main, WeatherReport


class TestCLI:
    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
        with patch("CLI.main.Config.validate"), patch(
            "CLI.main.SessionLocal"
        ) as mock_session_cls:
            mock_db = MagicMock()
            mock_session_cls.return_value = mock_db
            yield mock_db

    @pytest.fixture
    def prepared_weather_response(self, fake_weather_response):
        data = copy.deepcopy(fake_weather_response)
        data.setdefault("current", {})
        data["current"].setdefault("condition", {"text": "Sunny"})

        if "forecast" in data and "forecastday" in data["forecast"]:
            for fday in data["forecast"]["forecastday"]:
                day_dict = fday.setdefault("day", {})
                day_dict.setdefault("avgtemp_c", 15.0)
                day_dict.setdefault("mintemp_c", 10.0)
                day_dict.setdefault("maxtemp_c", 20.0)
                day_dict.setdefault("daily_chance_of_rain", 0)
                day_dict.setdefault("maxwind_kph", 10.0)
                day_dict.setdefault("uv", 3.0)
                day_dict.setdefault("totalprecip_mm", 0.0)
                day_dict.setdefault("condition", {"text": "Sunny"})
        return data

    @patch("CLI.main.get_snow_state", return_value={"status": "No snow"})
    def test_weather_report_display(self, mock_snow, prepared_weather_response, capsys):
        report = WeatherReport(prepared_weather_response, for_printing=False)
        report.display()
        captured = capsys.readouterr()

        city_name = prepared_weather_response.get("location", {}).get("name", "Berlin")
        assert city_name in captured.out

    @patch("CLI.main.get_snow_state", return_value={"status": "No snow"})
    def test_weather_report_for_printing(
        self, mock_snow, prepared_weather_response, capsys
    ):
        report = WeatherReport(prepared_weather_response, for_printing=True)
        report.display()
        captured = capsys.readouterr()

        city_name = prepared_weather_response.get("location", {}).get("name", "Berlin")
        assert city_name in captured.out
        # Проверяем, что в секции снега нет спецсимволов при печати
        assert "\033[1mNo snow\033[0m" not in captured.out

    @patch("CLI.main.get_snow_state", return_value={"status": "No snow"})
    @patch("CLI.main.WeatherService")
    def test_main_run_success_no_print(
        self,
        mock_service_cls,
        mock_snow,
        mock_dependencies,
        prepared_weather_response,
        monkeypatch,
        capsys,
    ):
        mock_service = MagicMock()
        mock_service.get_city_by_ip.return_value = "Moscow"
        mock_service.get_weather.return_value = prepared_weather_response
        mock_service_cls.return_value = mock_service

        monkeypatch.setattr("builtins.input", lambda _: "no")

        Main().run()

        captured = capsys.readouterr()
        assert "[+] Location context: Moscow" in captured.out
        assert mock_dependencies.add.called
        assert mock_dependencies.commit.called

    @patch("CLI.main.get_snow_state", return_value={"status": "No snow"})
    @patch("CLI.main.subprocess.run")
    @patch("CLI.main.WeatherService")
    def test_main_run_success_with_print(
        self,
        mock_service_cls,
        mock_subproc,
        mock_snow,
        prepared_weather_response,
        monkeypatch,
        capsys,
    ):
        mock_service = MagicMock()
        mock_service.get_city_by_ip.return_value = "Moscow"
        mock_service.get_weather.return_value = prepared_weather_response
        mock_service_cls.return_value = mock_service

        monkeypatch.setattr("builtins.input", lambda _: "yes")

        Main().run()

        captured = capsys.readouterr()
        assert "[+] Document successfully printed!" in captured.out
        assert mock_subproc.called

    @patch("CLI.main.WeatherService")
    def test_main_run_error_handling(self, mock_service_cls, capsys):
        mock_service = MagicMock()
        mock_service.get_city_by_ip.side_effect = Exception("IP resolution error")
        mock_service.get_weather.return_value = {"error": {"message": "City not found"}}
        mock_service_cls.return_value = mock_service

        Main().run()

        captured = capsys.readouterr()
        assert "[-] {'message': 'City not found'}" in captured.out
