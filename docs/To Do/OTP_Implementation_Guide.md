# One-Time Password (OTP) Implementation Guide

**Purpose:** Control alpha access using one-time use passwords  
**Scope:** ~200 OTPs, each usable once by one email address  
**Alpha Flag:** Only active when `IS_ALPHA=true`

---

## Overview

The OTP system ensures that only authorized users can sign up during the alpha phase. Each OTP code:
- Can only be used **once**
- Can only be linked to **one email address**
- Is only validated when `IS_ALPHA=true`
- Becomes non-functional after use

---

## Database Schema

### Collection: `alpha_otps`

```python
{
    "_id": ObjectId("..."),
    "otp_code": "ABC123XYZ",  # Unique, 8-12 character alphanumeric
    "used": false,            # Boolean flag
    "used_by_email": null,   # String (email) or null
    "used_at": null,          # ISO timestamp or null
    "created_at": "2025-01-XX..."  # ISO timestamp
}
```

### Indexes
- Unique index on `otp_code` (prevent duplicates)
- Index on `used` (for quick lookups of available OTPs)

---

## Implementation Steps

### Step 1: Create OTP Generation Script

**File:** `BackEnd/scripts/generate_otps.py`

```python
import os
import secrets
import string
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("MONGO_DB_NAME", "gob")

def generate_otp_code(length=10):
    """Generate a random alphanumeric OTP code."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude confusing characters: 0, O, 1, I, L
    alphabet = alphabet.replace('0', '').replace('O', '').replace('1', '').replace('I', '').replace('L', '')
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_otps(count=200):
    """Generate and insert OTPs into database."""
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    otps_collection = db["alpha_otps"]
    
    # Create unique index on otp_code
    otps_collection.create_index("otp_code", unique=True)
    otps_collection.create_index("used")
    
    otps = []
    created_at = datetime.utcnow().isoformat()
    
    for i in range(count):
        otp_code = generate_otp_code()
        otp_doc = {
            "otp_code": otp_code,
            "used": False,
            "used_by_email": None,
            "used_at": None,
            "created_at": created_at
        }
        
        try:
            otps_collection.insert_one(otp_doc)
            otps.append(otp_code)
            print(f"✅ Generated OTP {i+1}/{count}: {otp_code}")
        except Exception as e:
            print(f"❌ Failed to insert OTP {otp_code}: {e}")
    
    print(f"\n✅ Generated {len(otps)} OTPs successfully")
    print(f"\n📋 OTP List (save this securely):")
    for otp in otps:
        print(otp)
    
    # Save to file
    with open("alpha_otps_list.txt", "w") as f:
        for otp in otps:
            f.write(f"{otp}\n")
    print(f"\n💾 OTPs saved to alpha_otps_list.txt")
    
    return otps

if __name__ == "__main__":
    generate_otps(200)
```

**Usage:**
```bash
cd BackEnd/scripts
python generate_otps.py
```

---

### Step 2: Add OTP Collection to `BackEnd/db.py`

```python
# Add to existing collections
alpha_otps_collection = db["alpha_otps"]
```

---

### Step 3: Create OTP Validation Function

**File:** `BackEnd/utils/otp_validator.py`

```python
import os
from datetime import datetime
from typing import Tuple, Optional
from BackEnd.db import alpha_otps_collection

def is_alpha_mode() -> bool:
    """Check if alpha mode is enabled."""
    return os.getenv("IS_ALPHA", "false").lower() == "true"

def validate_otp(otp_code: str, email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an OTP code for signup.
    
    Returns:
        (is_valid, error_message)
        - (True, None) if valid and unused
        - (False, error_message) if invalid, used, or used by different email
    """
    if not is_alpha_mode():
        # OTP validation disabled - always return valid
        return (True, None)
    
    if not otp_code:
        return (False, "OTP code is required for alpha access")
    
    # Find OTP in database
    otp_doc = alpha_otps_collection.find_one({"otp_code": otp_code})
    
    if not otp_doc:
        return (False, "Invalid OTP code")
    
    # Check if already used
    if otp_doc.get("used", False):
        used_by = otp_doc.get("used_by_email")
        if used_by == email:
            # Same email trying to reuse - this shouldn't happen in normal flow
            # but could happen if signup process is interrupted
            return (False, "This OTP code has already been used")
        else:
            return (False, "This OTP code has already been used by another account")
    
    # OTP is valid and unused
    return (True, None)

def mark_otp_as_used(otp_code: str, email: str) -> bool:
    """
    Mark an OTP as used and link it to an email.
    
    Returns:
        True if successfully marked, False if OTP not found or already used
    """
    if not is_alpha_mode():
        return True  # No-op when not in alpha mode
    
    result = alpha_otps_collection.update_one(
        {
            "otp_code": otp_code,
            "used": False  # Only update if not already used
        },
        {
            "$set": {
                "used": True,
                "used_by_email": email,
                "used_at": datetime.utcnow().isoformat()
            }
        }
    )
    
    return result.modified_count > 0
```

---

### Step 4: Update Signup Endpoint

**File:** `BackEnd/api/auth_routes.py` (new file)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from BackEnd.utils.otp_validator import is_alpha_mode, validate_otp, mark_otp_as_used
from BackEnd.db import db
import bcrypt
from datetime import datetime
import secrets

router = APIRouter()

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    otp_code: str | None = None  # Required when IS_ALPHA=true

class SignupResponse(BaseModel):
    user_id: str
    email: str
    message: str

@router.post("/api/auth/signup")
async def signup(request: SignupRequest):
    """Signup endpoint with OTP validation for alpha."""
    users_collection = db["users"]
    
    # Check if alpha mode requires OTP
    if is_alpha_mode():
        if not request.otp_code:
            raise HTTPException(
                status_code=400,
                detail="OTP code is required for alpha access"
            )
        
        # Validate OTP
        is_valid, error_message = validate_otp(request.otp_code, request.email)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=error_message
            )
    
    # Check if email already exists
    existing_user = users_collection.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters"
        )
    
    # Hash password
    password_hash = bcrypt.hashpw(
        request.password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    # Create user document
    user_doc = {
        "user_id": secrets.token_urlsafe(16),  # Generate unique user_id
        "email": request.email,
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
        "role": "user",
        "version": "1.0"
    }
    
    # Insert user
    result = users_collection.insert_one(user_doc)
    
    # Mark OTP as used (if in alpha mode)
    if is_alpha_mode() and request.otp_code:
        mark_otp_as_used(request.otp_code, request.email)
    
    return SignupResponse(
        user_id=user_doc["user_id"],
        email=user_doc["email"],
        message="Account created successfully"
    )
```

---

### Step 5: Update Signup Frontend

**File:** `FrontEnd/static/signup.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Sign Up - GOB Alpha</title>
</head>
<body>
    <form id="signup-form">
        <label>Email:</label>
        <input type="email" id="email" required>
        
        <label>Password:</label>
        <input type="password" id="password" required minlength="8">
        
        <!-- OTP field - only shown when in alpha mode -->
        <div id="otp-field" style="display: none;">
            <label>Alpha Access Code:</label>
            <input type="text" id="otp-code" placeholder="Enter your alpha access code">
            <small>An access code is required to join the alpha.</small>
        </div>
        
        <button type="submit">Sign Up</button>
    </form>

    <script>
        // Check if alpha mode is enabled
        async function checkAlphaMode() {
            try {
                const response = await fetch('/api/alpha-status');
                const data = await response.json();
                if (data.is_alpha) {
                    document.getElementById('otp-field').style.display = 'block';
                    document.getElementById('otp-code').required = true;
                }
            } catch (e) {
                console.error('Failed to check alpha status:', e);
            }
        }
        
        // Check on page load
        checkAlphaMode();
        
        // Handle form submission
        document.getElementById('signup-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const otpCode = document.getElementById('otp-code').value;
            
            const payload = {
                email,
                password,
                ...(otpCode && { otp_code: otpCode })
            };
            
            try {
                const response = await fetch('/api/auth/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (response.ok) {
                    const data = await response.json();
                    alert('Account created! Redirecting to login...');
                    window.location.href = '/login.html';
                } else {
                    const error = await response.json();
                    alert(`Signup failed: ${error.detail}`);
                }
            } catch (e) {
                alert('Signup failed. Please try again.');
            }
        });
    </script>
</body>
</html>
```

---

### Step 6: Add Alpha Status Endpoint

**File:** `BackEnd/api/auth_routes.py`

```python
@router.get("/api/alpha-status")
async def get_alpha_status():
    """Return whether alpha mode is enabled (for frontend)."""
    return {
        "is_alpha": is_alpha_mode()
    }
```

---

## Testing Checklist

- [ ] Generate 200 OTPs successfully
- [ ] OTP list saved to file
- [ ] Valid OTP allows signup when `IS_ALPHA=true`
- [ ] Invalid OTP rejects signup
- [ ] Used OTP cannot be reused
- [ ] Same OTP cannot be used by different email
- [ ] OTP field hidden when `IS_ALPHA=false`
- [ ] Signup works without OTP when `IS_ALPHA=false`
- [ ] OTP marked as used after successful signup
- [ ] Database indexes created correctly

---

## Security Considerations

1. **OTP Generation:** Use `secrets` module (cryptographically secure)
2. **OTP Storage:** Store in database, not in code
3. **OTP Distribution:** Share OTPs securely (not in public repos)
4. **Rate Limiting:** Add rate limiting to signup endpoint (Step 6)
5. **OTP Expiration:** Consider adding expiration dates if needed (optional)

---

## Post-Alpha Transition

When moving out of alpha:
1. Set `IS_ALPHA=false` in environment variables
2. OTP validation will be automatically disabled
3. Signup will work normally without OTPs
4. Existing OTPs remain in database (for tracking/history)
5. Can optionally archive or delete `alpha_otps` collection

---

## Admin Tools (Optional)

Consider adding admin endpoints to:
- View remaining unused OTPs
- View used OTPs and their associated emails
- Generate additional OTPs if needed
- Manually invalidate OTPs if compromised

