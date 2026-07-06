"""Announcement timing constants shared by backend UESS emitters."""

# Default wall-clock pause for gameplay-freezing schema announcements.
# Frontend fallback mirror: animationPlayback.js::DEFAULT_ANNOUNCEMENT_FREEZE_HOLD_MS.
ANNOUNCEMENT_FREEZE_HOLD_MS: int = 300

# Display-only primary banners that should not pause gameplay.
SHORT_PRIMARY_DISPLAY_MS: int = 700
