#!/bin/bash
rm -f /tmp/results_v2.txt
for i in $(seq 1 400); do
  curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8001/api/v2/weather?city=Berlin" >> /tmp/results_v2.txt
done
echo "---RESULT---"
sort /tmp/results_v2.txt | uniq -c
