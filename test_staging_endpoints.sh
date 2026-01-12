#!/bin/bash

# Test Script for Staging API Endpoints
# Usage: ./test_staging_endpoints.sh

STAGING_URL="https://gob-simplified-staging.up.railway.app"

echo "============================================"
echo "STEP 1: Create a game to get a game_id"
echo "============================================"
echo ""

RESPONSE=$(curl -s -X POST ${STAGING_URL}/api/init-game \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Bentley-Truman",
    "away_team": "Lancaster",
    "mode": "single"
  }')

echo "Response: $RESPONSE"
echo ""

# Extract game_id from response (basic extraction - may need manual copy)
GAME_ID=$(echo $RESPONSE | grep -o '"game_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$GAME_ID" ]; then
  echo "❌ Could not extract game_id automatically"
  echo "Please copy the game_id from the response above and run these commands manually:"
  echo ""
  echo "GAME_ID=\"your_game_id_here\""
  echo ""
  echo "# Test game state endpoint:"
  echo "curl -s ${STAGING_URL}/api/game/\${GAME_ID}?quarter=1 | head -100"
  echo ""
  echo "# Test simulate quarter endpoint:"
  echo "curl -s -X POST ${STAGING_URL}/api/simulate-quarter \\"
  echo "  -H \"Content-Type: application/json\" \\"
  echo "  -d '{"
  echo "    \"game_id\": \"\${GAME_ID}\","
  echo "    \"home_team\": \"Bentley-Truman\","
  echo "    \"away_team\": \"Lancaster\","
  echo "    \"quarter\": 1,"
  echo "    \"mode\": \"single\","
  echo "    \"full_sim\": true"
  echo "  }' | head -100"
  exit 1
fi

echo "✅ Extracted game_id: $GAME_ID"
echo ""
echo "============================================"
echo "STEP 2: Test game state endpoint"
echo "============================================"
echo ""

echo "Testing: GET /api/game/${GAME_ID}?quarter=1"
echo ""

curl -s -w "\n\nResponse Time: %{time_total}s\nHTTP Status: %{http_code}\n" \
  ${STAGING_URL}/api/game/${GAME_ID}?quarter=1 | head -100

echo ""
echo "============================================"
echo "STEP 3: Test simulate quarter endpoint"
echo "============================================"
echo ""

echo "Testing: POST /api/simulate-quarter"
echo "Note: This will fully simulate Q1 (takes ~10-30 seconds)"
echo ""

curl -s -w "\n\nResponse Time: %{time_total}s\nHTTP Status: %{http_code}\n" \
  -X POST ${STAGING_URL}/api/simulate-quarter \
  -H "Content-Type: application/json" \
  -d "{
    \"game_id\": \"${GAME_ID}\",
    \"home_team\": \"Bentley-Truman\",
    \"away_team\": \"Lancaster\",
    \"quarter\": 1,
    \"mode\": \"single\",
    \"full_sim\": true
  }" | head -100

echo ""
echo "============================================"
echo "Testing Complete!"
echo "============================================"

