import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 1,
  duration: '5s',
};

const HOST = __ENV.TARGET_HOST || '127.0.0.1';

export default function () {
  const res1 = http.get(`http://${HOST}:5001/api/weather?city=Berlin`);
  check(res1, { 'v1 ok': (r) => r.status === 200 });

  const res2 = http.get(`http://${HOST}:8001/api/v2/weather?city=Berlin`);
  check(res2, { 'v2 ok': (r) => r.status === 200 });

  sleep(0.5);
}
