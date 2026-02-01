# Add username to existing user documents

**Purpose:** Backfill `username` and `username_lower` for users who signed up before the username feature was added.

**Manual approach (as noted by user):** Add usernames directly in MongoDB Compass or Atlas UI.

**Schema to add per user document:**
```json
{
  "username": "CoachJamie",
  "username_lower": "coachjamie"
}
```

**Rules:**
- `username` = display value (case-sensitive)
- `username_lower` = lowercase for uniqueness; must be unique across all users
- If manually adding, ensure no two users have the same `username_lower`

**Optional script approach:** A script could prompt for each user without username and let you enter one, then update the doc. Not included here since user will add manually.
