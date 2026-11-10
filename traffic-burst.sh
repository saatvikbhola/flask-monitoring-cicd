#!/bin/bash
echo "Generating diverse traffic across all endpoints and status codes..."

for i in {1..15}; do
  # 1. Health checks (HTTP 200 OK)
  curl -s "http://localhost:5000/health" > /dev/null

  # 2. Real cities worldwide (HTTP 200 OK + real API latency)
  curl -s "http://localhost:5000/weather?city=Tokyo" > /dev/null
  curl -s "http://localhost:5000/weather?city=Delhi" > /dev/null
  curl -s "http://localhost:5000/weather?city=London" > /dev/null

  # 3. Client errors: Invalid city (HTTP 404 Not Found)
  curl -s "http://localhost:5000/weather?city=fakecity_$i" > /dev/null

  # 4. Client errors: Missing parameter (HTTP 400 Bad Request)
  curl -s "http://localhost:5000/weather" > /dev/null

  # 5. Server error endpoint (HTTP 500 Internal Server Error)
  curl -s "http://localhost:5000/error" > /dev/null

  echo -ne "Batch $i/15 sent...\r"
  sleep 0.2
done

echo -e "\nDone! Check Grafana: all lines, status codes, and charts are now populated."
