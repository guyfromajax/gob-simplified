# Play Builder V2 - User Guide

## Overview

Play Builder V2 is an enhanced version of the Play Builder that supports creating and editing 4 skeleton variants for each play:
- **Successful** - Play executes perfectly (lean ≥ 1)
- **Mid-Play Change** - Play adjusts mid-execution (lean 0-0.99)
- **Contested** - Defense engaged, tougher execution (lean -0.01 to -1)
- **Broken** - Defense disrupts, offense forced to react (lean < -1)

---

## Features

### ✅ Create New Plays or Load Existing Ones
- **Create new:** Fill out play name, type, focus and click "Create Play"
- **Load existing:** Select from dropdown and click "Load Play"

### ✅ Variant Tab System
- Switch between 4 variants using tabs
- Status indicators show completion state:
  - 🟢 **Green** = Complete
  - 🟡 **Yellow** = In Progress (has steps, not marked complete)
  - ⚪ **White/Gray** = Not Started

### ✅ Auto-Copy from Successful
- When you switch to an empty variant (mid-play change, contested, broken), it automatically copies all steps from "Successful" as a starting point
- You can then edit the steps to create the variant

### ✅ Clone from Successful Button
- Manually clone "Successful" variant steps to current variant
- Useful if you want to start over with the successful template
- **Note:** Hidden when editing "Successful" variant

### ✅ Mark as Complete
- Click "✓ Mark as Complete" when variant is ready
- Changes to "↩️ Mark as Incomplete" to allow toggling
- Prevents saving with < 1 step

### ✅ Multiple Save Options
1. **💾 Save Draft** (or Ctrl+S / Cmd+S)
   - Saves current state without closing
   - Great for incremental saves while building

2. **✅ Save & Close**
   - Validates that "Successful" is marked complete
   - Saves and returns to success screen
   - Use when all variants are ready

### ✅ Variant Complete Button
- Replaces old "Play Complete" button
- Completes current variant and enables save options
- Auto-fills incomplete positions from previous step

---

## Workflow

### Creating a New Play

1. **Start with Successful Variant**
   - Fill out play name, type, focus
   - Click "Create Play"
   - Build the "Successful" skeleton (your ideal play execution)
   - Click "Variant Complete" when done
   - Mark as complete: "✓ Mark as Complete"

2. **Build Mid-Play Change Variant**
   - Click "Mid-Play Change" tab
   - Steps auto-copy from Successful
   - Edit steps where the play changes (e.g., PG drives instead of passing)
   - Click "Variant Complete"
   - Mark as complete

3. **Build Contested Variant**
   - Click "Contested" tab
   - Steps auto-copy from Successful
   - Edit steps to show defense bodied up, tighter passes, contested shots
   - Click "Variant Complete"
   - Mark as complete

4. **Build Broken Variant**
   - Click "Broken" tab
   - Steps auto-copy from Successful
   - Edit steps to show play disrupted, offense improvising
   - Click "Variant Complete"
   - Mark as complete

5. **Save**
   - Click "✅ Save & Close"
   - Play is saved with all 4 variants!

### Editing an Existing Play

1. **Load the Play**
   - Select play from dropdown at top
   - Click "Load Play"
   - Play loads with all existing variants

2. **Edit Any Variant**
   - Click the variant tab
   - Existing steps are loaded
   - Continue building or edit existing steps
   - Use "Clone from Successful" if you want to start over

3. **Save Changes**
   - Use "💾 Save Draft" frequently (or Ctrl+S)
   - Use "✅ Save & Close" when done

---

## Tips & Tricks

### Auto-Copy Behavior
- When you switch to an empty variant, it auto-copies from Successful
- This saves you time - you only need to edit the steps that differ
- If you want to start from scratch, delete all steps and rebuild

### Completion Status
- Mark variants as complete when you're satisfied with them
- "Save & Close" warns if Successful isn't complete
- You can still save incomplete variants with "Save Draft"

### Keyboard Shortcuts
- **Ctrl+S (Windows) / Cmd+S (Mac):** Quick save draft
- Saves time during iterative building

### Step Count Display
- Variant info shows current step count
- Helps track progress across variants
- Page title shows which variant you're editing

### Clone vs Auto-Copy
- **Auto-copy:** Happens automatically when switching to empty variant (one-time)
- **Clone button:** Manual action that overwrites current variant with Successful

---

## Validation Rules

1. **Successful Variant**
   - Must be marked complete before "Save & Close"
   - Can save incomplete with "Save Draft"

2. **Other Variants**
   - No completion requirement for "Save & Close"
   - But recommended to mark complete when ready

3. **Empty Variants**
   - OK to have empty variants (just 0 steps)
   - They'll use "successful" skeleton as fallback in game

---

## Database Structure

Each play now stores:
```javascript
{
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": "inside",
  "skeletons": {
    "successful": {
      "steps": [...],
      "complete": true
    },
    "mid_play_change": {
      "steps": [...],
      "complete": true
    },
    "contested": {
      "steps": [...],
      "complete": false
    },
    "broken": {
      "steps": [],
      "complete": false
    }
  }
}
```

---

## Differences from V1

| Feature | V1 | V2 |
|---------|----|----|
| Variants | 1 ("standard") | 4 (successful, mid_play_change, contested, broken) |
| Load existing | ❌ No | ✅ Yes |
| Save options | 1 (save & close) | 3 (draft, save & close, quick save) |
| Completion tracking | ❌ No | ✅ Yes |
| Auto-copy | ❌ No | ✅ Yes |
| Variant tabs | ❌ No | ✅ Yes |

---

## Common Issues

**Q: I switched variants and my work disappeared!**
A: Your work is saved in the previous variant. Switch back to see it. Each variant has independent steps.

**Q: The "Clone from Successful" button is missing!**
A: It's hidden when editing the "Successful" variant (you can't clone from yourself).

**Q: Can I have different number of steps in each variant?**
A: Yes! Variants can have completely different step counts.

**Q: What happens if I don't build all 4 variants?**
A: Empty variants will fall back to "successful" skeleton during gameplay. But it's recommended to build all 4 for variety.

**Q: Can I edit a variant after marking it complete?**
A: Yes! "Complete" is just a status flag. You can always edit and re-save.

---

## Next Steps

1. **Populate Existing Plays:** Load your 7 existing plays and build the 3 missing variants
2. **Test in Game:** Run games to see different skeletons in action
3. **Tune Lean Logic:** Implement real `generate_logic()` function to properly select variants

---

## File Location

- **V1 (Original):** `/FrontEnd/static/play-builder.html`
- **V2 (Enhanced):** `/FrontEnd/static/play-builder-v2.html`

Both versions coexist - use V2 for new work, V1 as backup.

