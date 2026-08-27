import http from 'k6/http';
import { check, sleep, group } from 'k6';

const cities = ["London", "Miami", "New York", "Tokio", "Berlin", "Zurich"];

export const options = {
    stages: [
        { duration: "10s", target: 5 },
        { duration: "5s", target: 50 },
        { duration: "20s", target: 50 },
        { duration: "5s", target: 5 },
        { duration: "10s", target: 5 },
    ],
};

export default function () {
    const city = cities[Math.floor(Math.random() * cities.length)];

    group('health', () => {
        const res_health = http.get("http://localhost:5001/health", {
            tags: { name: "health" },
        });
        check(res_health, {
            "status is 200": (r) => r.status === 200 || r.status === 429,
            "response time <3000ms": (r) => r.timings.duration < 3000,
        });
        sleep(1);
    });

    group('ping', () => {
        const res_ping = http.get("http://localhost:5001/api/ping", {
            tags: { name: "ping" },
        });
        check(res_ping, {
            "status is 200": (r) => r.status === 200 || r.status === 429,
            "response time <3000ms": (r) => r.timings.duration < 3000,
        });
        sleep(1);
    });

    group('weather', () => {
        const res_weather = http.get(`http://localhost:5001/api/weather?city=${city}`, {
            tags: { name: "weather" },
        });
        check(res_weather, {
            "status is 200": (r) => r.status === 200 || r.status === 429,
            "response time <5000ms": (r) => r.timings.duration < 5000,
        });
        sleep(1);
    });

}
