import http from 'k6/http';
import { check, sleep } from 'k6';

const cities = ["London", "Miami", "New York", "Tokio", "Berlin", "Zurich"];

export const options = {
    stages: [
        { duration: "20s", target: 10 },
        { duration: "1m", target: 10 },
        { duration: "20s", target: 0 },
    ],
};

export default function () {
    const city = cities[Math.floor(Math.random() * cities.length)];

    const res_health = http.get("https://weather-7icc.onrender.com/health");
        check(res_health, {
            "status is 200": (r) => r.status === 200,
            "response time <3000ms": (r) => r.timings.duration < 3000,
        });
    sleep(1);

    const res_ping = http.get("https://weather-7icc.onrender.com/api/ping");
        check(res_ping, {
            "status is 200": (r) => r.status === 200,
            "response time <3000ms": (r) => r.timings.duration < 3000,
        });
    sleep(1);

    const res_weather = http.get(`https://weather-7icc.onrender.com/api/weather?city=${city}`);
        check(res_weather, {
            "status is 200": (r) => r.status === 200,
            "response time <5000ms": (r) => r.timings.duration < 5000,
        });
    sleep(1);

}
