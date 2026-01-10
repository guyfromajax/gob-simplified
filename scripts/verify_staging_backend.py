#!/usr/bin/env python3
"""
Staging Backend Verification Script

This script helps verify Section 1 of the Go-Live Foundations checklist:
Staging Backend (Railway) Verification

Usage:
    python scripts/verify_staging_backend.py [--url https://gob-simplified-staging.up.railway.app]
"""

import requests
import json
import sys
import time
from typing import Optional, Dict, Any
from urllib.parse import urljoin

# Default staging URL from api-config.js
DEFAULT_STAGING_URL = "https://gob-simplified-staging.up.railway.app"

def test_endpoint(url: str, endpoint: str, method: str = "GET", payload: Optional[Dict] = None, expected_status: int = 200) -> Dict[str, Any]:
    """Test an API endpoint and return results."""
    full_url = urljoin(url, endpoint)
    
    try:
        start_time = time.time()
        
        if method == "GET":
            response = requests.get(full_url, timeout=10)
        elif method == "POST":
            response = requests.post(full_url, json=payload, timeout=10, headers={"Content-Type": "application/json"})
        else:
            return {"error": f"Unsupported method: {method}"}
        
        elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        result = {
            "url": full_url,
            "status_code": response.status_code,
            "response_time_ms": round(elapsed_time, 2),
            "success": response.status_code == expected_status,
            "headers": dict(response.headers)
        }
        
        # Try to parse JSON response
        try:
            result["response_body"] = response.json()
            result["response_size"] = len(response.content)
        except:
            result["response_body"] = response.text[:200]  # First 200 chars
            result["response_size"] = len(response.content)
        
        return result
        
    except requests.exceptions.Timeout:
        return {
            "url": full_url,
            "error": "Request timeout (>10 seconds)",
            "success": False
        }
    except requests.exceptions.ConnectionError:
        return {
            "url": full_url,
            "error": "Connection error - backend may not be deployed or URL is incorrect",
            "success": False
        }
    except Exception as e:
        return {
            "url": full_url,
            "error": f"Unexpected error: {str(e)}",
            "success": False
        }

def verify_root_endpoint(base_url: str) -> Dict[str, Any]:
    """Verify root endpoint (1.2.1)."""
    print("\n1.2.1 Testing Root Endpoint (GET /)...")
    result = test_endpoint(base_url, "/", "GET", expected_status=200)
    
    if result.get("success"):
        expected_message = {"message": "GOB Simulation API is live"}
        actual_body = result.get("response_body", {})
        
        if isinstance(actual_body, dict) and actual_body.get("message") == expected_message["message"]:
            print(f"   ✅ PASS - Root endpoint works")
            print(f"   Response: {actual_body}")
            print(f"   Response time: {result['response_time_ms']}ms")
            return {"status": "pass", "details": result}
        else:
            print(f"   ⚠️  WARNING - Response format unexpected")
            print(f"   Expected: {expected_message}")
            print(f"   Got: {actual_body}")
            return {"status": "warning", "details": result}
    else:
        print(f"   ❌ FAIL - Root endpoint failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        return {"status": "fail", "details": result}

def verify_teams_endpoint(base_url: str) -> Dict[str, Any]:
    """Verify teams endpoint (1.2.2)."""
    print("\n1.2.2 Testing Teams Endpoint (GET /teams)...")
    result = test_endpoint(base_url, "/teams", "GET", expected_status=200)
    
    if result.get("success"):
        response_body = result.get("response_body", [])
        if isinstance(response_body, list) and len(response_body) > 0:
            print(f"   ✅ PASS - Teams endpoint works")
            print(f"   Teams returned: {len(response_body)}")
            print(f"   Response time: {result['response_time_ms']}ms")
            print(f"   Sample team: {response_body[0] if response_body else 'N/A'}")
            return {"status": "pass", "details": result}
        else:
            print(f"   ⚠️  WARNING - Teams endpoint returned empty or invalid data")
            return {"status": "warning", "details": result}
    else:
        print(f"   ❌ FAIL - Teams endpoint failed")
        print(f"   Error: {result.get('error', 'Unknown error')}")
        return {"status": "fail", "details": result}

def verify_cors_config(base_url: str) -> Dict[str, Any]:
    """Verify CORS configuration (1.3.3)."""
    print("\n1.2.5 Testing CORS Configuration...")
    
    # Test OPTIONS request (preflight)
    try:
        response = requests.options(
            urljoin(base_url, "/teams"),
            headers={
                "Origin": "https://gob-test.netlify.app",
                "Access-Control-Request-Method": "GET"
            },
            timeout=10
        )
        
        cors_headers = {
            "access-control-allow-origin": response.headers.get("Access-Control-Allow-Origin"),
            "access-control-allow-methods": response.headers.get("Access-Control-Allow-Methods"),
            "access-control-allow-headers": response.headers.get("Access-Control-Allow-Headers"),
        }
        
        if cors_headers["access-control-allow-origin"]:
            print(f"   ✅ PASS - CORS headers present")
            print(f"   CORS Headers: {cors_headers}")
            return {"status": "pass", "details": cors_headers}
        else:
            print(f"   ⚠️  WARNING - CORS headers missing or incomplete")
            print(f"   Response headers: {dict(response.headers)}")
            return {"status": "warning", "details": dict(response.headers)}
            
    except Exception as e:
        print(f"   ❌ FAIL - CORS test failed: {str(e)}")
        return {"status": "fail", "details": {"error": str(e)}}

def verify_backend_deployment(base_url: str) -> Dict[str, Any]:
    """Overall backend deployment verification."""
    print(f"\n{'='*60}")
    print(f"Staging Backend Verification: {base_url}")
    print(f"{'='*60}")
    
    results = {
        "base_url": base_url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root_endpoint": None,
        "teams_endpoint": None,
        "cors_config": None
    }
    
    # Test root endpoint
    results["root_endpoint"] = verify_root_endpoint(base_url)
    
    # Test teams endpoint
    results["teams_endpoint"] = verify_teams_endpoint(base_url)
    
    # Test CORS
    results["cors_config"] = verify_cors_config(base_url)
    
    # Summary
    print(f"\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*60}")
    
    all_passed = all(
        r.get("status") == "pass" 
        for r in [results["root_endpoint"], results["teams_endpoint"], results["cors_config"]]
        if r
    )
    
    if all_passed:
        print("✅ All critical endpoints PASSED")
        return_code = 0
    else:
        print("⚠️  Some endpoints have issues - review details above")
        return_code = 1
    
    print(f"\nFull results saved to: verify_staging_backend_results.json")
    
    # Save detailed results to file
    with open("verify_staging_backend_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results, return_code

def main():
    """Main verification function."""
    # Get staging URL from command line or use default
    staging_url = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "--url" else DEFAULT_STAGING_URL
    
    if len(sys.argv) > 2 and sys.argv[1] == "--url":
        staging_url = sys.argv[2]
    
    print("Staging Backend Verification Script")
    print(f"Testing URL: {staging_url}")
    print("\nNote: This script tests endpoints that can be verified externally.")
    print("For full verification (env vars, MongoDB connection, build logs),")
    print("you'll need to check Railway dashboard directly.\n")
    
    results, return_code = verify_backend_deployment(staging_url)
    
    print("\n📋 NEXT STEPS:")
    print("1. Review the results above")
    print("2. Check Railway dashboard for:")
    print("   - Build logs (verify build succeeded)")
    print("   - Environment variables (MONGO_URI, ENVIRONMENT, etc.)")
    print("   - Application logs (check for errors)")
    print("3. Test MongoDB connection via a game creation API call")
    print("4. Update the verification checklist document with results")
    
    sys.exit(return_code)

if __name__ == "__main__":
    main()

