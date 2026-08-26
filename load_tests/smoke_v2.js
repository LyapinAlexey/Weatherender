import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    stages: [
        { duration: "10s", target: 5},
        { duration: "30s", target: 5},
        { duration: "10s", target: 0},
    ],
};

export default function () {
    const res = http.get("https://weather-7icc.onrender.com/api/v2/health");
    check(res, {
        "status is 200": (r) => r.status === 200,
        "response time <3000ms": (r) => r.timings.duration < 3000,
    });

    sleep(1);
}
