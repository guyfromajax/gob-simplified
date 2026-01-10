#!/bin/bash

# Staging Backend Verification Script
# This script helps verify Section 1 of the Go-Live Foundations checklist

# Default staging URL from api-config.js
STAGING_URL="${1:-https://gob-simplified-staging.up.railway.app}"

echo "============================================================"
echo "Staging Backend Verification: $STAGING_URL"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASSED=0
FAILED=0
WARNINGS=0

# Function to test an endpoint
test_endpoint() {
    local endpoint=$1
    local method=${2:-GET}
    local expected_status=${3:-200}
    local description=$4
    
    echo "Testing: $description"
    echo "  URL: ${STAGING_URL}${endpoint}"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X GET "${STAGING_URL}${endpoint}" -H "Content-Type: application/json" --max-time 10)
    elif [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "${STAGING_URL}${endpoint}" -H "Content-Type: application/json" -d "{}" --max-time 10)
    else
        echo "  ${RED}❌ FAIL - Unsupported method: $method${NC}"
        ((FAILED++))
        return 1
    fi
    
    # Extract response code and time from last two lines
    http_code=$(echo "$response" | tail -n 2 | head -n 1)
    time_total=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d' | sed '$d')
    
    time_ms=$(echo "$time_total * 1000" | bc | cut -d. -f1)
    
    if [ "$http_code" = "$expected_status" ]; then
        echo "  ${GREEN}✅ PASS${NC} - Status: $http_code, Response time: ${time_ms}ms"
        echo "  Response preview: $(echo "$body" | head -c 200)"
        ((PASSED++))
        return 0
    else
        echo "  ${RED}❌ FAIL${NC} - Status: $http_code (expected $expected_status)"
        if [ ! -z "$body" ]; then
            echo "  Response: $(echo "$body" | head -c 200)"
        fi
        ((FAILED++))
        return 1
    fi
    echo ""
}

# 1.2.1 Test Root Endpoint
echo "1.2.1 Root Endpoint (GET /)"
test_endpoint "/" "GET" "200" "Root endpoint"
echo ""

# 1.2.2 Test Teams Endpoint
echo "1.2.2 Teams Endpoint (GET /teams)"
test_endpoint "/teams" "GET" "200" "Teams endpoint"
echo ""

# 1.2.5 Test CORS Configuration
echo "1.2.5 CORS Configuration (OPTIONS /teams)"
echo "  URL: ${STAGING_URL}/teams"
cors_response=$(curl -s -w "\n%{http_code}" -X OPTIONS "${STAGING_URL}/teams" \
    -H "Origin: https://gob-test.netlify.app" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: Content-Type" \
    --max-time 10)

cors_code=$(echo "$cors_response" | tail -n 1)
cors_headers=$(curl -s -I -X OPTIONS "${STAGING_URL}/teams" \
    -H "Origin: https://gob-test.netlify.app" \
    -H "Access-Control-Request-Method: GET" \
    --max-time 10 | grep -i "access-control")

if [ ! -z "$cors_headers" ]; then
    echo "  ${GREEN}✅ PASS${NC} - CORS headers present"
    echo "  CORS Headers:"
    echo "$cors_headers" | sed 's/^/    /'
    ((PASSED++))
else
    echo "  ${YELLOW}⚠️  WARNING${NC} - CORS headers missing or incomplete"
    echo "  Status code: $cors_code"
    ((WARNINGS++))
fi
echo ""

# Summary
echo "============================================================"
echo "VERIFICATION SUMMARY"
echo "============================================================"
echo "${GREEN}✅ Passed: $PASSED${NC}"
echo "${RED}❌ Failed: $FAILED${NC}"
echo "${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "${GREEN}✅ All critical endpoints PASSED${NC}"
    echo ""
    echo "📋 NEXT STEPS:"
    echo "1. Review Railway dashboard for:"
    echo "   - Build logs (verify build succeeded)"
    echo "   - Environment variables (MONGO_URI, ENVIRONMENT, etc.)"
    echo "   - Application logs (check for errors)"
    echo "2. Test MongoDB connection via a game creation API call"
    echo "3. Update the verification checklist document with results"
    exit 0
else
    echo "${RED}❌ Some endpoints FAILED - review details above${NC}"
    echo ""
    echo "📋 TROUBLESHOOTING:"
    echo "1. Check if backend is deployed to Railway"
    echo "2. Verify Railway URL is correct: $STAGING_URL"
    echo "3. Check Railway logs for errors"
    echo "4. Verify environment variables are set"
    exit 1
fi

