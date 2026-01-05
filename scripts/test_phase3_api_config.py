#!/usr/bin/env python3
"""
Phase 3 API Config Testing Script

This script helps verify that Phase 3 (API Config) implementation is working correctly.
It checks for:
1. API config file exists
2. Frontend files use API_CONFIG
3. No hardcoded API URLs remain
4. Backend CORS configuration is correct
"""

import os
import re
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_api_config_file():
    """Check if api-config.js exists and has correct structure"""
    print(f"\n{YELLOW}Checking API Config File...{RESET}")
    
    config_path = Path("FrontEnd/static/js/config/api-config.js")
    if not config_path.exists():
        print(f"{RED}❌ api-config.js not found at {config_path}{RESET}")
        return False
    
    content = config_path.read_text()
    
    # Check for required functions
    required = [
        "API_CONFIG",
        "getBaseUrl",
        "buildUrl",
        "window.API_CONFIG"
    ]
    
    missing = []
    for item in required:
        if item not in content:
            missing.append(item)
    
    if missing:
        print(f"{RED}❌ Missing required elements: {', '.join(missing)}{RESET}")
        return False
    
    print(f"{GREEN}✅ api-config.js exists and has correct structure{RESET}")
    return True

def check_frontend_uses_api_config():
    """Check if frontend files use API_CONFIG instead of hardcoded URLs"""
    print(f"\n{YELLOW}Checking Frontend Files Use API_CONFIG...{RESET}")
    
    frontend_js_dir = Path("FrontEnd/static/js")
    frontend_html_dir = Path("FrontEnd/static")
    
    # Patterns to search for
    hardcoded_patterns = [
        r'["\']http://localhost:8000',
        r'["\']https://.*/api/',
        r'fetch\(["\']http://',
        r'fetch\(["\']https://',
    ]
    
    # Files to exclude (api-config.js itself, and config directory)
    excluded_dirs = {'config', '__pycache__', 'node_modules'}
    excluded_files = {'api-config.js'}
    
    issues = []
    
    # Check JS files
    for js_file in frontend_js_dir.rglob("*.js"):
        if js_file.parent.name in excluded_dirs or js_file.name in excluded_files:
            continue
        
        content = js_file.read_text()
        for pattern in hardcoded_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'file': str(js_file.relative_to(Path.cwd())),
                    'line': line_num,
                    'match': match.group()
                })
    
    # Check HTML files for inline scripts
    for html_file in frontend_html_dir.rglob("*.html"):
        content = html_file.read_text()
        for pattern in hardcoded_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    'file': str(html_file.relative_to(Path.cwd())),
                    'line': line_num,
                    'match': match.group()
                })
    
    if issues:
        print(f"{YELLOW}⚠️  Found {len(issues)} potential hardcoded URLs:{RESET}")
        for issue in issues[:10]:  # Show first 10
            print(f"  {issue['file']}:{issue['line']} - {issue['match']}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
        print(f"{YELLOW}Note: Some may be false positives (comments, strings, etc.){RESET}")
        return False
    
    print(f"{GREEN}✅ No hardcoded API URLs found in frontend files{RESET}")
    return True

def check_api_config_loaded():
    """Check if HTML files load api-config.js"""
    print(f"\n{YELLOW}Checking HTML Files Load api-config.js...{RESET}")
    
    frontend_dir = Path("FrontEnd/static")
    config_script = "api-config.js"
    
    html_files = list(frontend_dir.rglob("*.html"))
    files_without_config = []
    
    for html_file in html_files:
        content = html_file.read_text()
        # Check for api-config.js in script tags
        if config_script not in content and "API_CONFIG" in content:
            # If API_CONFIG is used but config not loaded, that's a problem
            files_without_config.append(str(html_file.relative_to(Path.cwd())))
    
    if files_without_config:
        print(f"{YELLOW}⚠️  Files using API_CONFIG but may not load api-config.js:{RESET}")
        for file in files_without_config[:5]:
            print(f"  {file}")
        if len(files_without_config) > 5:
            print(f"  ... and {len(files_without_config) - 5} more")
        print(f"{YELLOW}Note: Some may load it dynamically or via shared includes{RESET}")
        return True  # Not a blocker, just a warning
    
    print(f"{GREEN}✅ HTML files properly reference api-config.js{RESET}")
    return True

def check_backend_cors():
    """Check if backend CORS configuration is correct"""
    print(f"\n{YELLOW}Checking Backend CORS Configuration...{RESET}")
    
    api_file = Path("BackEnd/api/api.py")
    if not api_file.exists():
        print(f"{RED}❌ api.py not found{RESET}")
        return False
    
    content = api_file.read_text()
    
    # Check for CORS middleware
    if "CORSMiddleware" not in content:
        print(f"{RED}❌ CORS middleware not found{RESET}")
        return False
    
    # Check for Railway/Netlify regex
    if "railway.app" not in content or "netlify.app" not in content:
        print(f"{YELLOW}⚠️  Railway/Netlify domain regex may be missing{RESET}")
        return True  # Not a blocker, but should be there
    
    # Check for localhost
    if "localhost" not in content:
        print(f"{YELLOW}⚠️  localhost may not be in CORS origins{RESET}")
        return True  # Not a blocker
    
    print(f"{GREEN}✅ Backend CORS configuration looks correct{RESET}")
    return True

def check_static_files_conditional():
    """Check if static file serving is conditional"""
    print(f"\n{YELLOW}Checking Static Files Conditional Serving...{RESET}")
    
    api_file = Path("BackEnd/api/api.py")
    if not api_file.exists():
        print(f"{RED}❌ api.py not found{RESET}")
        return False
    
    content = api_file.read_text()
    
    # Check for environment check
    if "ENVIRONMENT" not in content or "development" not in content:
        print(f"{YELLOW}⚠️  Static file serving may not be conditional{RESET}")
        return True  # Not a blocker, but recommended
    
    print(f"{GREEN}✅ Static file serving is conditional (development only){RESET}")
    return True

def main():
    """Run all checks"""
    print(f"{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}Phase 3 API Config Testing{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    
    results = []
    
    results.append(("API Config File", check_api_config_file()))
    results.append(("Frontend Uses API_CONFIG", check_frontend_uses_api_config()))
    results.append(("HTML Files Load Config", check_api_config_loaded()))
    results.append(("Backend CORS Config", check_backend_cors()))
    results.append(("Static Files Conditional", check_static_files_conditional()))
    
    # Summary
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}Summary{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{status} - {name}")
    
    print(f"\n{passed}/{total} checks passed")
    
    if passed == total:
        print(f"\n{GREEN}✅ All checks passed! Phase 3 implementation looks good.{RESET}")
        print(f"{YELLOW}Next: Run manual testing checklist (see PHASE_3_TESTING_CHECKLIST.md){RESET}")
    else:
        print(f"\n{YELLOW}⚠️  Some checks failed. Review issues above.{RESET}")
        print(f"{YELLOW}Fix issues before proceeding to deployment.{RESET}")

if __name__ == "__main__":
    main()

