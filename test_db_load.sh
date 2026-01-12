#!/bin/bash

# Test Database Connection Load Handling
# Tests 5 concurrent API calls to verify connection handles load

STAGING_URL="https://gob-simplified-staging.up.railway.app"

echo "============================================"
echo "Testing Database Connection Load Handling"
echo "============================================"
echo "Making 5 concurrent requests to /teams endpoint..."
echo ""

# Create temporary file to store results
RESULT_FILE=$(mktemp)

# Launch 5 concurrent requests
for i in {1..5}; do
  (
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 ${STAGING_URL}/teams 2>&1)
    if [ "$HTTP_CODE" = "200" ]; then
      echo "Request $i: ✅ Success (HTTP $HTTP_CODE)" >> $RESULT_FILE
    else
      echo "Request $i: ❌ Failed (HTTP $HTTP_CODE)" >> $RESULT_FILE
    fi
  ) &
done

# Wait for all background jobs to complete
wait

echo ""
# Display results
cat $RESULT_FILE

# Count successes
SUCCESS_COUNT=$(grep -c "✅ Success" $RESULT_FILE || echo "0")
FAILED_COUNT=$(grep -c "❌ Failed" $RESULT_FILE || echo "0")

echo ""
echo "============================================"
echo "Results"
echo "============================================"
echo "Successful: $SUCCESS_COUNT/5"
echo "Failed: $FAILED_COUNT/5"

if [ $SUCCESS_COUNT -eq 5 ]; then
  echo ""
  echo "✅ Status: HANDLES LOAD (5/5 concurrent requests succeeded)"
  EXIT_CODE=0
elif [ $SUCCESS_COUNT -gt 0 ]; then
  echo ""
  echo "⚠️ Status: PARTIAL ($SUCCESS_COUNT/5 concurrent requests succeeded)"
  EXIT_CODE=1
else
  echo ""
  echo "❌ Status: FAILED (0/5 concurrent requests succeeded)"
  EXIT_CODE=2
fi

# Cleanup
rm -f $RESULT_FILE

exit $EXIT_CODE

