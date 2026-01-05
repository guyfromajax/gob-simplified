# Architecture Review: GOB Deployment Strategy

## Executive Summary

**Overall Assessment: ✅ SOLID APPROACH** with some important improvements needed.

The proposed architecture (Netlify + Railway + MongoDB Atlas) is a **modern, production-ready setup** that aligns well with your current tech stack. However, there are several critical implementation details that need to be addressed before deployment.

---

## ✅ What's Good About This Approach

### 1. **Separation of Concerns**
- Frontend and backend on separate platforms (Netlify + Railway) is correct
- Each platform optimized for its purpose (static hosting vs. API server)
- Clean separation makes scaling and maintenance easier

### 2. **Technology Choices**
- **Netlify**: Excellent for static SPAs, great CDN, easy deployments, free tier is generous
- **Railway**: Good for Python/FastAPI, simple deployment, good pricing, supports environment variables
- **MongoDB Atlas**: Industry standard, managed service, good free tier, easy scaling

### 3. **Environment Strategy**
- Separate staging and production environments is essential
- Branch-based deployment (`main` → prod, `develop` → staging) is a common pattern

---

## ⚠️ Critical Issues to Address

### 1. **CORS Configuration (HIGH PRIORITY)**

**Current State:**
```python
# BackEnd/api/api.py line 60
allow_origin_regex=".*",  # allows all origins including null
```

**Problem:** This is a **security risk** in production. It allows any website to make requests to your API.

**Solution:**
```python
# Production
allow_origins=[
    "https://www.geekedoutbasketball.com",
    "https://staging.geekedoutbasketball.com"
]

# Development (local)
allow_origins=["http://localhost:8000", "http://localhost:3000"]
```

**Recommendation:** Use environment variables to configure CORS per environment.

---

### 2. **Frontend API URL Configuration (HIGH PRIORITY)**

**Current State:** Mixed patterns in frontend code:
- Some files use relative URLs: `/api/playbooks`
- Some use conditional logic: `window.location.hostname === "localhost" ? "http://localhost:8000" : window.location.origin`

**Problem:** 
- Relative URLs won't work when frontend is on `geekedoutbasketball.com` and API is on `api.geekedoutbasketball.com`
- Conditional logic is inconsistent and error-prone

**Solution:** Create a centralized API configuration:

```javascript
// FrontEnd/static/js/config/api-config.js
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

// Usage in all API calls:
const response = await fetch(`${API_CONFIG.getBaseUrl()}/api/playbooks?...`);
```

**Action Required:** 
- Create `api-config.js`
- Update all fetch calls to use centralized config
- Test in all environments

---

### 3. **Domain Setup Strategy**

**Proposed:**
- Production: `www.geekedoutbasketball.com` (frontend) + `api.geekedoutbasketball.com` (backend)
- Staging: `staging.geekedoutbasketball.com` (frontend) + `api-staging.geekedoutbasketball.com` (backend)

**Recommendation:** ✅ This is correct, but consider:

**Alternative (Simpler for Alpha):**
- Use Railway's default domain for backend: `your-app.railway.app`
- Use Netlify's default domain for staging: `your-app.netlify.app`
- Only use custom domains for production

**Why:** 
- Faster setup (no DNS configuration needed)
- Easier to test
- Can add custom domains later when ready

**For Production:** Custom domains are better for:
- Branding
- SEO
- Professional appearance

---

### 4. **Environment Variables Management**

**Critical Variables Needed:**

**Backend (Railway):**
```
MONGO_URI=<production/staging connection string>
ENVIRONMENT=production|staging
CORS_ORIGINS=https://www.geekedoutbasketball.com,https://staging.geekedoutbasketball.com
PORT=8000 (Railway sets this automatically)
```

**Frontend (Netlify):**
```
VITE_API_URL=https://api.geekedoutbasketball.com (if using Vite)
# OR use build-time injection via netlify.toml
```

**Recommendation:** 
- Use Railway's environment variable UI for backend
- Use Netlify's environment variable UI for frontend
- Document all required variables in a `.env.example` file (never commit actual `.env`)

---

### 5. **Database Connection String Security**

**Current State:** Likely using local MongoDB connection string

**Action Required:**
1. Create MongoDB Atlas account
2. Create two clusters: `gob_prod` and `gob_staging`
3. Get connection strings (format: `mongodb+srv://user:pass@cluster.mongodb.net/`)
4. Store in Railway environment variables
5. Update backend to read from `MONGO_URI` environment variable

**Security:**
- Never commit connection strings to git
- Use IP whitelist in Atlas (allow Railway IPs)
- Use database user with minimal required permissions
- Enable MongoDB Atlas network access restrictions

---

### 6. **Build and Deployment Process**

**Backend (Railway):**
- Railway auto-detects Python projects
- Needs: `requirements.txt` ✅ (you have this)
- Needs: `Procfile` or `railway.json` (optional, Railway can auto-detect)
- Command: `uvicorn BackEnd.api.api:app --host 0.0.0.0 --port $PORT`

**Frontend (Netlify):**
- Publish directory: `FrontEnd/static` ✅ (matches your proposal)
- Build command: None (static files, no build needed)
- **BUT:** Consider if you need any build step (minification, bundling, etc.)

**Recommendation:** 
- For alpha: Deploy static files as-is (no build step)
- For production: Consider adding a build step for optimization later

---

### 7. **Static File Serving**

**Current State:** FastAPI serves static files via:
```python
app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")
```

**In Production:** 
- Netlify will serve static files directly
- Backend should NOT serve static files (remove this mount in production)
- OR: Keep it for local development, disable in production via environment check

**Recommendation:**
```python
import os

if os.getenv("ENVIRONMENT") != "production":
    # Only serve static files in development
    app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")
```

---

## 📋 Implementation Checklist

### Phase 1: Backend Setup (Railway)
- [ ] Create Railway account
- [ ] Create new project
- [ ] Connect GitHub repository
- [ ] Set environment variables:
  - [ ] `MONGO_URI` (production)
  - [ ] `ENVIRONMENT=production`
  - [ ] `CORS_ORIGINS` (comma-separated list)
- [ ] Configure build command: `uvicorn BackEnd.api.api:app --host 0.0.0.0 --port $PORT`
- [ ] Deploy and test API endpoints
- [ ] Set up custom domain: `api.geekedoutbasketball.com`

### Phase 2: Database Setup (MongoDB Atlas)
- [ ] Create Atlas account
- [ ] Create production cluster
- [ ] Create staging cluster
- [ ] Create database users with appropriate permissions
- [ ] Configure IP whitelist (allow Railway IPs)
- [ ] Get connection strings
- [ ] Test connection from local environment
- [ ] Migrate local data to Atlas (if needed)

### Phase 3: Frontend Setup (Netlify)
- [ ] Create Netlify account
- [ ] Connect GitHub repository
- [ ] Configure build settings:
  - [ ] Base directory: (root)
  - [ ] Publish directory: `FrontEnd/static`
  - [ ] Build command: (none, or add if needed)
- [ ] Set environment variables (if using build-time config)
- [ ] Deploy and test
- [ ] Set up custom domain: `www.geekedoutbasketball.com`

### Phase 4: Code Updates
- [ ] Create `FrontEnd/static/js/config/api-config.js`
- [ ] Update all API calls to use centralized config
- [ ] Update CORS configuration to use environment variables
- [ ] Remove or conditionally mount static file serving in backend
- [ ] Test in local environment
- [ ] Test in staging environment
- [ ] Test in production environment

### Phase 5: Staging Environment
- [ ] Create `develop` branch
- [ ] Set up Railway staging project
- [ ] Set up Netlify staging site
- [ ] Configure staging domains
- [ ] Test full staging workflow

---

## 🔄 Alternative Considerations

### Should You Use Vercel Instead of Netlify?

**Netlify Pros:**
- Excellent for static sites
- Great CDN
- Easy deployments
- Good free tier

**Vercel Pros:**
- Better developer experience (some say)
- Better integration with Next.js (not relevant for you)
- Similar features

**Recommendation:** ✅ Stick with Netlify - it's perfect for your use case.

---

### Should You Use Render or Fly.io Instead of Railway?

**Railway Pros:**
- Simple deployment
- Good Python support
- Easy environment variables
- Good pricing

**Render Pros:**
- More mature platform
- Better documentation
- Free tier available

**Fly.io Pros:**
- Global edge deployment
- More complex but more powerful

**Recommendation:** ✅ Railway is fine for your needs. Consider Render if you hit issues with Railway.

---

### Should You Use a Monorepo or Separate Repos?

**Current:** Single repo (monorepo)

**Recommendation:** ✅ Keep single repo for now. Benefits:
- Easier to coordinate changes
- Shared code/config
- Simpler deployment

**Consider splitting later if:**
- Teams grow
- Deployment cycles diverge significantly
- Need different access controls

---

## 🚨 Security Considerations

### 1. **API Rate Limiting**
- Consider adding rate limiting to prevent abuse
- FastAPI has middleware options: `slowapi` or `fastapi-limiter`

### 2. **Input Validation**
- Ensure all Pydantic models validate input
- Sanitize user inputs
- Validate file uploads (if any)

### 3. **Error Handling**
- Don't expose stack traces in production
- Log errors server-side
- Return user-friendly error messages

### 4. **HTTPS Everywhere**
- Netlify provides HTTPS automatically ✅
- Railway provides HTTPS automatically ✅
- Ensure all API calls use HTTPS

---

## 📊 Cost Estimates

### MongoDB Atlas
- **Free Tier:** 512MB storage, shared cluster
- **Paid:** ~$9/month for M0 cluster (suitable for alpha)
- **Recommendation:** Start with free tier, upgrade when needed

### Railway
- **Free Tier:** $5 credit/month
- **Paid:** ~$5-20/month depending on usage
- **Recommendation:** Free tier should work for alpha

### Netlify
- **Free Tier:** 100GB bandwidth, 300 build minutes/month
- **Paid:** $19/month for Pro (unlikely needed for alpha)
- **Recommendation:** Free tier should work for alpha

**Total Estimated Cost for Alpha:** $0-15/month

---

## ✅ Final Recommendation

**Proceed with the proposed architecture** with these modifications:

1. ✅ Use Netlify + Railway + MongoDB Atlas
2. ✅ Set up staging and production environments
3. ⚠️ **Fix CORS configuration** (use environment variables)
4. ⚠️ **Create centralized API URL config** for frontend
5. ⚠️ **Update all API calls** to use centralized config
6. ⚠️ **Remove/condition static file serving** in production backend
7. ⚠️ **Set up proper environment variables** in both platforms

**Timeline Estimate:**
- Backend setup: 2-4 hours
- Database setup: 1-2 hours
- Frontend setup: 1-2 hours
- Code updates: 4-8 hours
- Testing: 2-4 hours
- **Total: 10-20 hours** for initial deployment

---

## 📚 Additional Resources

- [Railway Python Deployment Guide](https://docs.railway.app/guides/python)
- [Netlify Static Site Deployment](https://docs.netlify.com/site-deploys/create-deploys/)
- [MongoDB Atlas Setup](https://www.mongodb.com/docs/atlas/getting-started/)
- [FastAPI CORS Configuration](https://fastapi.tiangolo.com/tutorial/cors/)
- [Environment Variables Best Practices](https://12factor.net/config)

---

## Questions to Consider

1. **Do you need authentication?** (Not mentioned in architecture doc)
   - If yes, consider Auth0, Firebase Auth, or custom JWT
   - Will affect API design

2. **Do you need file uploads?** (For player photos, team logos, etc.)
   - Consider S3 or Cloudinary
   - Or use Netlify's form handling

3. **Do you need analytics?**
   - Google Analytics
   - Plausible (privacy-friendly)
   - Custom analytics endpoint

4. **Do you need error tracking?**
   - Sentry (recommended)
   - LogRocket
   - Custom error logging

---

**Bottom Line:** The architecture is sound. Focus on the implementation details above, especially CORS and API URL configuration, and you'll have a production-ready deployment.

