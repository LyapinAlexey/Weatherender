import logging
import platform
import subprocess
import sys
from datetime import datetime

from weatherender.config import Config
from weatherender.logging_config import setup_logging
from weatherender.models import SessionLocal, WeatherRequest
from weatherender.services import WeatherService
from weatherender.snow import get_snow_state

setup_logging()
logger = logging.getLogger(__name__)

RESET, BOLD, BLUE, CYAN, GREEN, YELLOW, RED, ORANGE = (
    "\033[0m",
    "\033[1m",
    "\033[34m",
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[35m",
)


class WeatherReport:
    def __init__(self, data: dict, for_printing: bool = False) -> None:
        self.data = data
        self.for_printing = for_printing
        self.loc, self.curr = data["location"], data["current"]
        self.line_len = 81 if for_printing else 70

    def _fmt(self, val: int | str, color: str) -> str:
        if self.for_printing:
            return str(val)
        return f"{color}{val}{RESET}"

    def get_color_metrics(self) -> tuple[str, str, str, str, str]:
        t = self.curr.get("temp_c", 0)
        uv = round(self.curr.get("uv", 0))
        p = round(self.curr.get("pressure_mb", 1013) * 0.750062)
        wind = self.curr.get("wind_kph", 0)
        pop = 0
        try:
            pop = self.data["forecast"]["forecastday"][0]["hour"][0].get(
                "chance_of_rain", 0
            )
        except (KeyError, IndexError):
            pass
        tc = (
            BLUE
            if t < -10
            else CYAN if t < 0 else GREEN if t < 16 else YELLOW if t < 26 else RED
        )
        uc = GREEN if uv <= 2 else YELLOW if uv <= 5 else ORANGE if uv <= 7 else RED
        pc = CYAN if p < 745 else GREEN if p <= 755 else YELLOW if p <= 765 else RED
        wc = (
            GREEN
            if wind < 19
            else YELLOW if wind < 39 else ORANGE if wind < 61 else RED
        )
        rc = GREEN if pop < 20 else CYAN if pop < 50 else YELLOW if pop < 80 else BLUE

        return (
            self._fmt(f"{t}°C", tc),
            self._fmt(uv, uc),
            self._fmt(f"{p} мм", pc),
            self._fmt(f"{wind} km/h", wc),
            self._fmt(f"{pop}%", rc),
        )

    def display(self) -> None:
        print(
            f" Date and time: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            + "-" * self.line_len
        )
        if self.for_printing:
            print(f" City: {self.loc['name']} ({self.loc['country']})")
        else:
            print(
                f" City: {BOLD}{self.loc['name']}{RESET} ({BOLD}{self.loc['country']}{RESET})"
            )

        curr_day = (
            self.data["forecast"]["forecastday"][0]["day"]
            if "forecast" in self.data
            else {}
        )
        curr_hour = (
            self.data["forecast"]["forecastday"][0]["hour"][0]
            if "forecast" in self.data
            and self.data["forecast"]["forecastday"][0]["hour"]
            else {}
        )

        snow_info = get_snow_state(
            temp_c=self.curr.get("temp_c", 0.0),
            min_temp_c=curr_day.get("mintemp_c", 0.0),
            max_temp_c=curr_day.get("maxtemp_c", 0.0),
            humidity=self.curr.get("humidity", 50),
            snow_depth_cm=curr_day.get("totalsnow_cm", 0.0),
            snow_24h_cm=curr_day.get("totalsnow_cm", 0.0),
            wind_kph=self.curr.get("wind_kph", 0.0),
            cloud_cover=self.curr.get("cloud", 0),
            condition_text=self.curr.get("condition", {}).get("text", ""),
            prev_day_max_temp=curr_day.get("maxtemp_c", 0.0),
            totalprecip_mm=curr_day.get("totalprecip_mm", 0.0),
            will_it_snow=curr_hour.get("will_it_snow", 0),
            totalsnow_cm=curr_day.get("totalsnow_cm", 0.0),
        )

        t_out, uv_out, p_out, wind_out, rain_out = self.get_color_metrics()
        print(
            f" Current temperature: {t_out}\n"
            f" Current UV index: {uv_out}\n"
            f" Precipitation chance: {rain_out}\n"
            f" Current pressure: {p_out}\n"
            f" Wind: {wind_out}\n"
            f" Current weather: {self.curr['condition']['text']}\n"
            f" Snow conditions: {BOLD}{snow_info['status']}{RESET if not self.for_printing else ''}\n"
            + "-" * self.line_len
        )
        print(" Forecast for 24 hours:\n")
        print(
            f" {'Time':<6} | {'Temp':<6} | {'UV-index':<3} | {'Pressure':<7} | {'Precipitations':<5}"
        )
        print("-" * self.line_len)
        local_hr = datetime.strptime(self.loc["localtime"], "%Y-%m-%d %H:%M").strftime(
            "%Y-%m-%d %H:00"
        )
        hours = [
            h
            for day in self.data["forecast"]["forecastday"]
            for h in day["hour"]
            if h["time"] >= local_hr
        ][:24]
        for h in hours:
            pop = h.get("chance_of_rain", 0)
            print(
                f" {h['time'].split(' ')[1]:<6} | {h['temp_c']:>2}°C | {round(h['uv']):<8} | {round(h['pressure_mb'] * 0.750062):<8} | {pop}%"
            )
        print("-" * self.line_len + "\n 3-Day Forecast:\n")
        print(
            f" {'Date':<5} | {'Max Temp':<8} | {'Rain Chance':<11} | {'Max UV-index':<8} | {'Wind gusts':<6} | {'Snow State':<18}"
        )
        print("-" * self.line_len)

        for day in self.data["forecast"]["forecastday"]:
            date_obj = datetime.strptime(day["date"], "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d.%m")
            temp = f"{day['day']['avgtemp_c']:.1f}°C"
            pop = f"{day['day']['daily_chance_of_rain']}%"
            maxuv = round(day["day"]["uv"])
            gusts = f"{day['day']['maxwind_kph']} km/h"
            day_snow = get_snow_state(
                temp_c=day["day"]["avgtemp_c"],
                min_temp_c=day["day"]["mintemp_c"],
                max_temp_c=day["day"]["maxtemp_c"],
                humidity=day["day"].get("avghumidity", 50),
                snow_depth_cm=day["day"].get("totalsnow_cm", 0.0),
                snow_24h_cm=day["day"].get("totalsnow_cm", 0.0),
                wind_kph=day["day"]["maxwind_kph"],
                cloud_cover=50,
                condition_text=day["day"]["condition"]["text"],
                prev_day_max_temp=day["day"]["maxtemp_c"],
                totalprecip_mm=day["day"]["totalprecip_mm"],
                will_it_snow=1 if day["day"].get("totalsnow_cm", 0) > 0 else 0,
                totalsnow_cm=day["day"].get("totalsnow_cm", 0.0),
            )
            print(
                f" {formatted_date:<5} | {temp:<8} | {pop:<11} | {maxuv:<12} | {gusts:<8} | {day_snow['status']:<18}"
            )
        print("-" * self.line_len)


class Main:
    def run(self) -> None:
        Config.validate()
        db_session = SessionLocal()
        srv = WeatherService()
        try:
            city = srv.get_city_by_ip()
        except Exception as e:
            logger.warning(f"Failed to resolve city by IP: {e}")
            city = "Moscow"
        logger.info(f"Location resolved: {city}")
        print(f"[+] Location context: {city}")
        data = srv.get_weather(city)
        if "error" in data:
            try:
                info_err = WeatherRequest(
                    city=city,
                    source="cli",
                    success=0,
                    error_message=data["error"]["message"],
                )
                db_session.add(info_err)
                db_session.commit()
            finally:
                db_session.close()
            logger.warning(f"Weather fetch failed: {data['error']}")
            return print(f"[-] {data['error']}")
        try:
            info_suc = WeatherRequest(
                city=city,
                source="cli",
                temp_c=data["current"]["temp_c"],
                condition=data["current"]["condition"]["text"],
                success=1,
                error_message=None,
            )
            db_session.add(info_suc)
            db_session.commit()
        finally:
            db_session.close()
        print_req = (
            input(" Need to print the forecast? (No; Yes): ").strip().lower() == "yes"
        )
        print("-" * 70)
        report = WeatherReport(data, for_printing=print_req)
        if not print_req:
            return report.display()
        fn, os_t = "weather_report.txt", platform.system()
        orig = sys.stdout
        with open(fn, "w", encoding="utf-8-sig" if os_t == "Windows" else "utf-8") as f:
            sys.stdout = f
            report.display()
        sys.stdout = orig
        try:
            subprocess.run(
                f'notepad.exe /p "{fn}"' if os_t == "Windows" else ["lp", fn],
                shell=(os_t == "Windows"),
                check=True,
            )
            print("[+] Document successfully printed!")
        except Exception as e:
            print(f"[-] Print spooler failed: {e}")


if __name__ == "__main__":
    Main().run()


def main() -> None:
    Main().run()
