#!/usr/bin/env python3
"""
Local Development Server
Runs FastAPI with hot reload for fast iteration.
"""

import uvicorn

if __name__ == "__main__":
    print("🚀 Starting GOB local dev server...")
    print("📍 Backend: http://localhost:8000")
    print("📍 Frontend: http://localhost:8000/static/court.html")
    print("🔄 Hot reload: ENABLED (changes to Python files will auto-reload)")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "BackEnd.api.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # ✅ Hot reload enabled
        reload_dirs=["BackEnd"],  # Only watch backend files
        log_level="info"
    )

