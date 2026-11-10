for i in {1..50}; do
  curl -s http://localhost:5000/ > /dev/null
  curl -s http://localhost:5000/health > /dev/null
  curl -s http://localhost:5000/error > /dev/null
  sleep 0.2
done
