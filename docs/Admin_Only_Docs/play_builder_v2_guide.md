# Play Builder V2 - User Guide

> **Last Updated:** February 2025  
> **Status:** Current - Reflects production implementation

## Overview

Play Builder V2 is an enhanced version of the Play Builder that supports creating and editing skeleton variants for each play. The system differs based on play type:

### Set Plays
Set Plays support 4 variant types:
- **Successful** - Play executes perfectly (lean ≥ 1) - Single version only
- **Mid-Play Change** - Play adjusts mid-execution (lean 0-0.99) - **6 versions (v1-v6)**
- **Contested** - Defense engaged, tougher execution (lean -0.01 to -1) - **6 versions (v1-v6)**
- **Broken** - Defense disrupts, offense forced to react (lean < -1) - **6 versions (v1-v6)**

### Motion Plays
Motion Plays use a single variant:
- **Base Loop** - The circular motion sequence (replaces "Successful" for Motion plays)

---

## Features

### ✅ Create New Plays or Load Existing Ones
- **Create new:** Fill out play name, type, focus and click "Create Play"
- **Load existing:** Select from dropdown and click "Load Play"

### ✅ Variant Tab System
- **Set Plays:** Switch between 4 variants using tabs (Successful, Mid-Play Change, Contested, Broken)
- **Motion Plays:** Single "Base Loop" tab
- Status indicators show completion state:
  - 🟢 **Green** = Complete
  - 🟡 **Yellow** = In Progress (has steps, not marked complete)
  - ⚪ **White/Gray** = Not Started

### ✅ Version System (Set Plays Only)
- **Mid-Play Change, Contested, and Broken variants** support **6 versions each (v1-v6)**
- Version selector dropdown appears when editing these variants
- Each version can have different steps (e.g., different shooters, different shot locations)
- Version dropdown shows which versions exist and their shooter info
- Switch between versions to build multiple variations of the same variant type
- **Successful variant** does NOT have versions (single skeleton only)
- **Motion plays** do NOT use versions (Base Loop only)

### ✅ Auto-Copy from Successful/Base Loop
- When you switch to an empty variant (mid-play change, contested, broken), it automatically copies all steps from "Successful" (Set Plays) or "Base Loop" (Motion Plays) as a starting point
- Auto-copy happens when switching to an empty **version** (v1) of a variant
- You can then edit the steps to create the variant
- Each version (v1-v6) can be auto-copied independently

### ✅ Clone from Successful/Base Loop Button
- Manually clone "Successful" (Set Plays) or "Base Loop" (Motion Plays) variant steps to current variant/version
- Useful if you want to start over with the successful template
- **Note:** Hidden when editing "Successful" or "Base Loop" variant
- Clones to the currently selected version (v1-v6) of the variant

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

### Creating a New Set Play

1. **Start with Successful Variant**
   - Fill out play name, type (Set Play), focus
   - Click "Create Play"
   - Build the "Successful" skeleton (your ideal play execution)
   - Click "Variant Complete" when done
   - Mark as complete: "✓ Mark as Complete"
   - **Note:** Successful variant has only one version (no version selector)

2. **Build Mid-Play Change Variant (v1-v6)**
   - Click "Mid-Play Change" tab
   - Version selector appears (defaults to v1)
   - Steps auto-copy from Successful to v1
   - Edit steps where the play changes (e.g., PG drives instead of passing)
   - Click "Variant Complete" for v1
   - **Optional:** Switch to v2, v3, etc. to build additional variations
   - Each version can have different steps (different shooters, different outcomes)
   - Mark as complete when satisfied with all versions

3. **Build Contested Variant (v1-v6)**
   - Click "Contested" tab
   - Version selector appears (defaults to v1)
   - Steps auto-copy from Successful to v1
   - Edit steps to show defense bodied up, tighter passes, contested shots
   - **Optional:** Build multiple versions (v1-v6) with different contested scenarios
   - Mark as complete when satisfied

4. **Build Broken Variant (v1-v6)**
   - Click "Broken" tab
   - Version selector appears (defaults to v1)
   - Steps auto-copy from Successful to v1
   - Edit steps to show play disrupted, offense improvising
   - **Optional:** Build multiple versions (v1-v6) with different broken scenarios
   - Mark as complete when satisfied

5. **Save**
   - Click "✅ Save & Close"
   - Play is saved with all variants and versions!

### Creating a New Motion Play

1. **Build Base Loop**
   - Fill out play name, type (Motion), focus (optional for Motion)
   - Click "Create Play"
   - Build the "Base Loop" skeleton (circular motion sequence)
   - Click "Variant Complete" when done
   - Mark as complete: "✓ Mark as Complete"
   - **Note:** Motion plays only use Base Loop (no other variants, no versions)

2. **Save**
   - Click "✅ Save & Close"
   - Motion play is saved!

### Editing an Existing Play

1. **Load the Play**
   - Select play from dropdown at top
   - Click "Load Play"
   - Play loads with all existing variants and versions

2. **Edit Any Variant/Version**
   - Click the variant tab
   - **For Set Plays with versions:** Use version selector to switch between v1-v6
   - Existing steps are loaded for the selected version
   - Continue building or edit existing steps
   - Use "Clone from Successful" if you want to start over
   - **Tip:** Version dropdown shows which versions exist and their shooter info

3. **Add New Versions**
   - Switch to an empty version (e.g., v2, v3) in Mid-Play Change, Contested, or Broken
   - Steps auto-copy from Successful (or use Clone button)
   - Build the new version variation
   - Each version is independent (different steps, different shooters, etc.)

4. **Save Changes**
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
- **Auto-copy:** Happens automatically when switching to empty variant/version (one-time per version)
- **Clone button:** Manual action that overwrites current variant/version with Successful/Base Loop

### Version System (Set Plays)
- **Mid-Play Change, Contested, Broken:** Each has 6 versions (v1-v6)
- **Successful:** Single version only (no version selector)
- **Motion Plays:** No versions (Base Loop only)
- Version selector appears automatically when editing multi-version variants
- Each version is independent - can have different step counts, different shooters, different outcomes
- Version dropdown shows which versions exist and their shooter info (e.g., "v1 (exists, shooter: PG, location: top)")
- Switch versions to build multiple variations of the same variant type

---

## Validation Rules

1. **Successful Variant (Set Plays) / Base Loop (Motion Plays)**
   - Must be marked complete before "Save & Close"
   - Can save incomplete with "Save Draft"
   - Single version only (no version selector)

2. **Other Variants (Set Plays Only)**
   - No completion requirement for "Save & Close"
   - But recommended to mark complete when ready
   - Each version (v1-v6) is independent
   - OK to have some versions empty and others complete

3. **Empty Variants/Versions**
   - OK to have empty variants or versions (just 0 steps)
   - They'll use "successful" skeleton (Set Plays) or "base_loop" (Motion Plays) as fallback in game
   - Empty versions within a variant will fall back to the variant's other versions or successful

---

## Database Structure

### Set Play Structure
```javascript
{
  "name": "4-1 Motion",
  "play_type": "set_play",
  "play_focus": "inside",
  "skeletons": {
    "successful": {
      "steps": [...],
      "complete": true
    },
    "mid_play_change": {
      "versions": [
        { "version": "v1", "steps": [...] },
        { "version": "v2", "steps": [...] },
        { "version": "v3", "steps": [...] },
        // ... up to v6 (only versions with steps are included)
      ]
    },
    "contested": {
      "versions": [
        { "version": "v1", "steps": [...] },
        // ... up to v6
      ]
    },
    "broken": {
      "versions": [
        { "version": "v1", "steps": [...] },
        // ... up to v6
      ]
    }
  }
}
```

### Motion Play Structure
```javascript
{
  "name": "3-2 Motion",
  "play_type": "motion",
  "play_focus": null,  // Optional for Motion plays
  "skeletons": {
    "base_loop": {
      "steps": [...],
      "complete": true
    }
    // Motion plays only have base_loop, no other variants
  }
}
```

**Key Differences:**
- **Set Plays:** `successful` has simple structure (steps array), other variants have `versions` array
- **Motion Plays:** Only `base_loop` variant, no versions, no other variants
- **Versions:** Only `mid_play_change`, `contested`, and `broken` have versions (v1-v6)
- **Storage:** Only versions with steps are saved (empty versions are omitted)

---

## Differences from V1

| Feature | V1 | V2 |
|---------|----|----|
| Variants | 1 ("standard") | Set Plays: 4 variants (successful, mid_play_change, contested, broken)<br>Motion Plays: 1 variant (base_loop) |
| Versions | ❌ No | ✅ Yes - Mid-Play Change, Contested, Broken have 6 versions each (v1-v6) |
| Load existing | ❌ No | ✅ Yes |
| Save options | 1 (save & close) | 2 (draft, save & close) + keyboard shortcut |
| Completion tracking | ❌ No | ✅ Yes |
| Auto-copy | ❌ No | ✅ Yes |
| Variant tabs | ❌ No | ✅ Yes |
| Version selector | ❌ No | ✅ Yes (for multi-version variants) |
| Motion play support | ❌ No | ✅ Yes (base_loop variant) |

---

## Common Issues

**Q: I switched variants and my work disappeared!**
A: Your work is saved in the previous variant/version. Switch back to see it. Each variant and version has independent steps.

**Q: The "Clone from Successful" button is missing!**
A: It's hidden when editing the "Successful" or "Base Loop" variant (you can't clone from yourself).

**Q: Can I have different number of steps in each variant/version?**
A: Yes! Variants and versions can have completely different step counts.

**Q: What happens if I don't build all 4 variants?**
A: Empty variants will fall back to "successful" skeleton (Set Plays) or "base_loop" (Motion Plays) during gameplay. But it's recommended to build all variants for variety.

**Q: Can I edit a variant after marking it complete?**
A: Yes! "Complete" is just a status flag. You can always edit and re-save.

**Q: Where is the version selector?**
A: The version selector dropdown appears automatically when editing Mid-Play Change, Contested, or Broken variants (Set Plays only). It's hidden for Successful variant and Motion plays.

**Q: Do I need to build all 6 versions?**
A: No! You can build as many or as few versions as you want (v1-v6). Empty versions are not saved to the database. The game will use available versions or fall back to successful.

**Q: Can I delete a version?**
A: Yes - just delete all steps in that version. Empty versions are not saved to the database.

**Q: What's the difference between Motion and Set Play?**
A: Motion plays use a circular "Base Loop" sequence and don't have variants or versions. Set Plays have 4 variants (successful + 3 multi-version variants).

**Q: How do I switch between versions?**
A: Use the version selector dropdown that appears when editing Mid-Play Change, Contested, or Broken variants. Select v1-v6 to switch.

---

## Next Steps

1. **Populate Existing Plays:** Load existing plays and build missing variants/versions
2. **Build Multiple Versions:** Create v1-v6 variations for Mid-Play Change, Contested, and Broken variants to add variety
3. **Test in Game:** Run games to see different skeletons and versions in action
4. **Tune Lean Logic:** Ensure backend properly selects variants and versions based on lean scores

---

## File Location

- **V1 (Original):** `/FrontEnd/static/play-builder.html`
- **V2 (Enhanced):** `/FrontEnd/static/play-builder-v2.html`

Both versions coexist - use V2 for new work, V1 as backup.

