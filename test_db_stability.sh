#!/bin/bash

# Test Database Connection Stability
# Tests 10 sequential API calls to verify connection stability

STAGING_URL="https://gob-simplified-staging.up.railway.app"

echo "============================================"
echo "Testing Database Connection Stability"
echo "============================================"
echo "Making 10 sequential requests to /teams endpoint..."
echo ""

SUCCESS_COUNT=0
TOTAL_TIME=0
FAILED_REQUESTS=0
TIMES=()

for i in {1..10}; do
  echo -n "Test $i: "
  START_TIME=$(date +%s.%N)
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 ${STAGING_URL}/teams 2>&1)
  END_TIME=$(date +%s.%N)
  TIME_TAKEN=$(echo "$END_TIME - $START_TIME" | bc)
  
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Success (HTTP $HTTP_CODE, ${TIME_TAKEN}s)"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    TIMES+=($TIME_TAKEN)
    TOTAL_TIME=$(echo "$TOTAL_TIME + $TIME_TAKEN" | bc)
  else
    echo "❌ Failed (HTTP $HTTP_CODE, ${TIME_TAKEN}s)"
    FAILED_REQUESTS=$((FAILED_REQUESTS + 1))
  fi
  
  sleep 0.5  # Small delay between requests
done

echo ""
echo "============================================"
echo "Results"
echo "============================================"
echo "Successful: $SUCCESS_COUNT/10"
echo "Failed: $FAILED_REQUESTS/10"

if [ $SUCCESS_COUNT -gt 0 ]; then
  AVG_TIME=$(echo "scale=3; $TOTAL_TIME / $SUCCESS_COUNT" | bc)
  echo "Average response time: ${AVG_TIME}s"
  # Convert to milliseconds
  AVG_MS=$(echo "scale=0; $AVG_TIME * 1000" | bc)
  echo "Average response time: ${AVG_MS}ms"
else
  AVG_TIME=0
  AVG_MS=0
fi

if [ $SUCCESS_COUNT -eq 10 ]; then
  echo ""
  echo "✅ Status: STABLE (10/10 requests succeeded)"
  EXIT_CODE=0
elif [ $SUCCESS_COUNT -gt 0 ]; then
  echo ""
  echo "⚠️ Status: PARTIALLY STABLE ($SUCCESS_COUNT/10 requests succeeded)"
  EXIT_CODE=1
else
  echo ""
  echo "❌ Status: FAILED (0/10 requests succeeded)"
  EXIT_CODE=2
fi

exit $EXIT_CODE

