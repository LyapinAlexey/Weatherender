#!/bin/bash
rm -f /tmp/results.txt
for i in $(seq 1 400); do
  curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/api/weather?city=Berlin" >> /tmp/results.txt
done
echo "---RESULT---"
sort /tmp/results.txt | uniq -c
