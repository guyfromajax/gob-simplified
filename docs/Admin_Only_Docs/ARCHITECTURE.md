# Geeked-Out Basketball – Architecture Notes (Step 0)

## Purpose
This document defines the **target architecture** for Geeked-Out Basketball (GOB) as it transitions from a local development environment to a live, internet-accessible deployment.

The goal is to:
- Enable a clean **staging + production** setup
- Support rapid iteration during alpha
- Avoid premature infrastructure complexity
- Keep the system portable and scalable

This document intentionally focuses on **structure and responsibilities**, not implementation details.

---

## High-Level Architecture Overview

GOB uses a **decoupled frontend + backend** architecture:

- **Frontend:** Static Single Page Application (SPA)
- **Backend:** Dynamic API service
- **Database:** Managed cloud database
- **Hosting:** Separate platforms optimized for each concern

This is a modern, production-grade architecture.

---

## Frontend

### Description
- Static HTML / CSS / JavaScript (Phaser-based SPA)
- No server-side rendering
- UI state and rendering handled entirely in the browser
- Data fetched dynamically from backend API

### Hosting
- **Platform:** Netlify
- **Publish Directory:** `FrontEnd/static`

### Environments
- **Production:** https://www.geekedoutbasketball.com
- **Staging:** https://staging.geekedoutbasketball.com

### Deployment
- `main` branch → Production
- `develop` branch → Staging

---

## Backend API

### Description
- Serves all dynamic functionality
- Exposes REST-style endpoints under `/api/...`
- Handles:
  - Game simulation
  - Data persistence
  - Business logic
  - (Future) authentication, billing, analytics hooks

### Hosting
- **Platform:** Railway

### Environments
- **Production API:** https://api.geekedoutbasketball.com
- **Staging API:** https://api-staging.geekedoutbasketball.com

### Deployment
- `main` branch → Production API
- `develop` branch → Staging API

---

## Database

### Description
- Persistent data store for game state and user data

### Platform
- **MongoDB Atlas**

### Environments
- **Production DB:** `gob_prod`
- **Staging DB:** `gob_staging`

### Notes
- Separate databases (or credentials) per environment
- No shared data between staging and production
- Connection strings stored as environment variables on Railway

---

## Frontend ↔ Backend Communication

### Current Local Behavior
- Frontend and backend share the same origin (`localhost:8000`)
- Frontend makes relative API calls:


### Target Deployment Behavior
- Frontend and backend live on **different domains**
- Frontend must use a configurable API base URL

### Required Frontend Configuration
A single configuration value is introduced: `API_BASE_URL`

**Implementation:** Create `FrontEnd/static/js/config/api-config.js`:
```javascript
const API_CONFIG = {
  getBaseUrl() {
    // Check for explicit override (useful for testing)
    if (window.API_BASE_URL) {
      return window.API_BASE_URL;
    }
    
    // Production
    if (window.location.hostname === 'www.geekedoutbasketball.com') {
      return 'https://api.geekedoutbasketball.com';
    }
    
    // Staging
    if (window.location.hostname === 'staging.geekedoutbasketball.com') {
      return 'https://api-staging.geekedoutbasketball.com';
    }
    
    // Local development
    return 'http://localhost:8000';
  }
};
```

Values by environment:
- Local: `http://localhost:8000`
- Staging: `https://api-staging.geekedoutbasketball.com`
- Production: `https://api.geekedoutbasketball.com`

All frontend API calls must be constructed as:
```javascript
const response = await fetch(`${API_CONFIG.getBaseUrl()}/api/endpoint`, {...});
```



---

## CORS (Cross-Origin Requests)

Because frontend and backend are hosted on different domains in staging and production, the backend must explicitly allow requests from:

- https://www.geekedoutbasketball.com
- https://staging.geekedoutbasketball.com

This is a required production concern.

---

## Domain & DNS

### Registrar
- Namecheap

### DNS Targets
- `www.geekedoutbasketball.com` → Netlify (production frontend)
- `staging.geekedoutbasketball.com` → Netlify (staging frontend)
- `api.geekedoutbasketball.com` → Railway (production API)
- `api-staging.geekedoutbasketball.com` → Railway (staging API)

---

## Non-Goals (Explicitly Out of Scope for Step 0)

The following are **not** implemented in this phase, but are intentionally planned for:

- Authentication / account management
- Alpha access codes
- Payments (Stripe)
- Marketing pixels
- Advanced analytics
- Real-time multiplayer / websockets

Architecture decisions made here do **not** block these features later.

---

## Guiding Principles

- Prefer clarity over cleverness
- Prefer explicit configuration over hidden magic
- Separate environments cleanly
- Avoid infrastructure lock-in
- Optimize for iteration speed during alpha

---

## Status
- **Step 0 (Architecture): COMPLETE**
- Next step: **Phase 1 – Staging backend deployment on Railway**

