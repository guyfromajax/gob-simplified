#!/usr/bin/env python3
"""
Quick CORS test script to verify CORS headers are working.
Tests the /api/simulate-quarter endpoint from gob-test.netlify.app origin.
"""

import requests
import sys

# Staging backend URL
BACKEND_URL = "https://gob-simplified-staging.up.railway.app"

# Test origin (simulating gob-test.netlify.app)
TEST_ORIGIN = "https://gob-test.netlify.app"

def test_cors_preflight():
    """Test OPTIONS preflight request"""
    print(f"\n🧪 Testing CORS preflight (OPTIONS) for {TEST_ORIGIN}...")
    
    try:
        response = requests.options(
            f"{BACKEND_URL}/api/simulate-quarter",
            headers={
                "Origin": TEST_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            },
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        # Check for CORS headers
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            if allowed_origin == TEST_ORIGIN or allowed_origin == "*":
                print(f"   ✅ CORS preflight PASSED - Allowed origin: {allowed_origin}")
                return True
            else:
                print(f"   ❌ CORS preflight FAILED - Wrong origin: {allowed_origin} (expected {TEST_ORIGIN})")
                return False
        else:
            print(f"   ❌ CORS preflight FAILED - No Access-Control-Allow-Origin header")
            return False
            
    except Exception as e:
        print(f"   ❌ CORS preflight FAILED - Error: {e}")
        return False

def test_cors_actual_request():
    """Test actual POST request (simulates real API call)"""
    print(f"\n🧪 Testing CORS actual request (POST) for {TEST_ORIGIN}...")
    
    try:
        # Minimal request payload
        payload = {
            "game_id": "test_game_id",
            "home_team": "Test Team",
            "away_team": "Test Team 2",
            "quarter": 1,
            "full_sim": True
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/simulate-quarter",
            json=payload,
            headers={
                "Origin": TEST_ORIGIN,
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        # Check for CORS headers in response
        if "Access-Control-Allow-Origin" in response.headers:
            allowed_origin = response.headers["Access-Control-Allow-Origin"]
            if allowed_origin == TEST_ORIGIN or allowed_origin == "*":
                print(f"   ✅ CORS actual request PASSED - Allowed origin: {allowed_origin}")
                # Don't check response content (might be error, but CORS worked)
                return True
            else:
                print(f"   ❌ CORS actual request FAILED - Wrong origin: {allowed_origin} (expected {TEST_ORIGIN})")
                return False
        else:
            print(f"   ❌ CORS actual request FAILED - No Access-Control-Allow-Origin header")
            return False
            
    except requests.exceptions.RequestException as e:
        # If it's a CORS error, the request won't even complete
        print(f"   ❌ CORS actual request FAILED - Request blocked (CORS error): {e}")
        return False
    except Exception as e:
        print(f"   ❌ CORS actual request FAILED - Error: {e}")
        return False

def main():
    print("=" * 60)
    print("CORS Test for gob-test.netlify.app")
    print(f"Backend: {BACKEND_URL}")
    print("=" * 60)
    
    # Test preflight
    preflight_ok = test_cors_preflight()
    
    # Test actual request
    actual_ok = test_cors_actual_request()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Preflight (OPTIONS): {'✅ PASS' if preflight_ok else '❌ FAIL'}")
    print(f"  Actual Request (POST): {'✅ PASS' if actual_ok else '❌ FAIL'}")
    
    if preflight_ok and actual_ok:
        print("\n✅ All CORS tests passed!")
        return 0
    else:
        print("\n❌ CORS tests failed - check backend configuration")
        return 1

if __name__ == "__main__":
    sys.exit(main())

