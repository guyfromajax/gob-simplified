# Franchise Mode Testing Expectations

**Date:** February 2025  
**Purpose:** Set expectations for what should work perfectly vs. what might still need attention

---

## ✅ **What Should Work Perfectly (Navigation)**

### **GMO (Game Mode Only) Navigation**
All GMO transitions should preserve the core navigation anchor set (`mode`, `franchise_id`, `team_id`):

- ✅ **FCC → Game Plan** - Fixed: Uses `team_id`, includes `mode`
- ✅ **FCC → Playbooks** - Already correct
- ✅ **FCC → Training** - Already correct
- ✅ **FCC → Lineup (Play Next Game)** - Fixed: Uses `team_id`, includes `mode`
- ✅ **Game Plan → FCC** - Fixed: Includes `mode`
- ✅ **Game Plan → Playbooks** - Uses helper, should preserve all variables
- ✅ **Playbooks → Game Plan** - Uses helper, should preserve all variables
- ✅ **Playbooks → FCC** - Fixed: Uses `team_id`, includes `mode`
- ✅ **Training → Training Report** - Backend redirect (needs verification)
- ✅ **Training Report → FCC** - Fixed: Includes `mode`
- ✅ **Training → FCC (Back)** - Fixed: Includes `mode`

### **GP (Gameplay) Navigation**
All GP transitions should preserve the core navigation anchor set:

- ✅ **Lineup → Gameplay** - Uses helper, preserves all variables
- ✅ **Lineup → Game Plan** - Uses helper, preserves all variables
- ✅ **Lineup → Box Score** - Uses helper, preserves all variables
- ✅ **Game Plan → Gameplay** - Uses helper, preserves all variables
- ✅ **Game Plan → Playbooks** - Uses helper, preserves all variables
- ✅ **Playbooks → Game Plan** - Uses helper, preserves all variables
- ✅ **Playbooks → Play Details** - Uses helper, preserves all variables
- ✅ **Play Details → Playbooks** - Uses helper, preserves all variables
- ✅ **Gameplay → Game Plan (Timeout)** - Fixed: Includes `team_id` in overrides
- ✅ **Gameplay → Box Score (Game Completion)** - Includes all variables
- ✅ **Box Score → FCC** - Fixed: Includes `mode`
- ✅ **Gameplay → Lineup (Quarter Break)** - Uses helper, preserves all variables

**Expected Result:** Navigation should be seamless - no lost context when moving between screens.

---

## ⚠️ **What Might Still Need Attention**

### **1. Backend API Compatibility**

**Issue:** Backend uses multiple team identifier patterns:
- `user_team_id` (team name string) - stored in franchise document
- `user_team_object_id` (ObjectId string) - stored in franchise document
- `team_id` (ObjectId string) - used in URL parameters and some API endpoints

**Backend Functions:**
- `get_user_team_from_franchise()` returns `(user_team_id, user_team_object_id)` - team name and ObjectId
- Some endpoints accept `team_id` (ObjectId)
- Some endpoints accept `team_name` (string)
- Backend has resolution logic to convert between formats

**Potential Issues:**
- ✅ **Game Plan API** (`/api/gameplan`) - Accepts `team_id` (ObjectId) for franchise mode
- ✅ **Playbooks API** (`/api/playbooks`) - Accepts `team_id` (ObjectId) for franchise mode
- ⚠️ **Training API** (`/franchise/run-training`) - Redirect URL needs verification
- ⚠️ **Command Center Data** (`/franchise/command-center/data`) - May need `team_id` parameter
- ⚠️ **Team Data API** (`/franchise/team-data`) - Accepts both `team_id` and `team_name`, but resolution might be needed

**What to Test:**
- Navigate to Game Plan → Verify settings load correctly
- Navigate to Playbooks → Verify plays load correctly
- Navigate to Training → Complete training → Verify redirect includes all variables
- Navigate to FCC → Verify team data displays correctly

---

### **2. Data Loading on Page Load**

**Issue:** Frontend pages need to extract `team_id` from URL and use it to load data.

**What We Fixed:**
- Navigation URLs now include `team_id` consistently
- `TimeoutNavigationHelper` preserves `team_id` in GP flows

**What Might Still Need Work:**
- ⚠️ **Page initialization** - Some pages might still be looking for `user_team_id` instead of `team_id`
- ⚠️ **Backward compatibility** - Pages should support both `team_id` and `user_team_id` for old URLs
- ⚠️ **Team resolution** - If `team_id` is missing, pages should fall back to franchise document lookup

**What to Test:**
- Load Game Plan directly with URL containing `team_id` → Verify settings load
- Load Playbooks directly with URL containing `team_id` → Verify plays load
- Load Training directly with URL containing `team_id` → Verify training options load
- Load FCC directly with URL containing `team_id` → Verify team data displays

---

### **3. Data Saving**

**Issue:** When saving data (Game Plan settings, Playbook settings, etc.), backend needs to know which team to save to.

**What We Fixed:**
- Navigation preserves `team_id` so it's available when saving

**What Might Still Need Work:**
- ⚠️ **Save API calls** - Verify that save endpoints receive `team_id` correctly
- ⚠️ **Backend save logic** - Verify that backend uses `team_id` (ObjectId) to save to correct location
- ⚠️ **Data persistence** - Verify that saved data persists correctly across sessions

**What to Test:**
- Change Game Plan settings → Save → Navigate away → Navigate back → Verify settings persisted
- Change Playbook percentages → Save → Navigate away → Navigate back → Verify percentages persisted
- Complete Training → Verify training results saved to correct team

---

### **4. Edge Cases**

**Potential Issues:**
- ⚠️ **Missing `team_id` in URL** - Should fall back to franchise document lookup
- ⚠️ **Invalid `team_id`** - Should handle gracefully (show error or fall back)
- ⚠️ **Team not in franchise** - Should handle gracefully
- ⚠️ **Old URLs with `user_team_id`** - Should still work (backward compatibility)
- ⚠️ **Old URLs with `user_team_name`** - Should still work (backward compatibility)

**What to Test:**
- Navigate with old URL format (`user_team_id`) → Verify still works
- Navigate with missing `team_id` → Verify fallback works
- Navigate with invalid `team_id` → Verify error handling

---

## 🎯 **Testing Checklist**

### **Navigation Tests**
- [ ] FCC → Game Plan → Back to FCC (verify all parameters preserved)
- [ ] FCC → Playbooks → Back to FCC (verify all parameters preserved)
- [ ] FCC → Game Plan → Playbooks → Back to Game Plan → Back to FCC (verify all parameters preserved)
- [ ] FCC → Training → Training Report → Back to FCC (verify all parameters preserved)
- [ ] FCC → Lineup (Play Next Game) → Verify all parameters present
- [ ] Lineup → Gameplay → Verify game loads correctly
- [ ] Lineup → Game Plan → Verify settings load correctly
- [ ] Gameplay → Timeout → Game Plan → Verify timeout state preserved
- [ ] Gameplay → Box Score → FCC → Verify all parameters preserved

### **Data Loading Tests**
- [ ] Game Plan loads with `team_id` in URL → Verify settings load correctly
- [ ] Playbooks loads with `team_id` in URL → Verify plays load correctly
- [ ] Training loads with `team_id` in URL → Verify training options load correctly
- [ ] FCC loads with `team_id` in URL → Verify team data displays correctly

### **Data Saving Tests**
- [ ] Change Game Plan settings → Save → Navigate away → Navigate back → Verify settings persisted
- [ ] Change Playbook percentages → Save → Navigate away → Navigate back → Verify percentages persisted
- [ ] Complete Training → Verify training results saved to correct team

### **Backward Compatibility Tests**
- [ ] Navigate with old URL format (`user_team_id`) → Verify still works
- [ ] Navigate with missing `team_id` → Verify fallback works
- [ ] Navigate with invalid `team_id` → Verify error handling

---

## 📊 **Expected Results Summary**

### **✅ Should Work Perfectly:**
1. **Navigation** - All transitions preserve `mode`, `franchise_id`, `team_id`
2. **URL Consistency** - All URLs use standardized `team_id` parameter
3. **GP Flows** - All gameplay navigation uses `TimeoutNavigationHelper` correctly

### **⚠️ Might Need Attention:**
1. **Backend API Compatibility** - Some endpoints might need `team_id` resolution
2. **Data Loading** - Some pages might need to extract `team_id` from URL
3. **Data Saving** - Some save endpoints might need `team_id` parameter
4. **Backward Compatibility** - Old URLs should still work but might need fallback logic

### **✅ Verified Items:**
1. **Training Redirect** ✅ **VERIFIED - CORRECT**
   - **Location:** `BackEnd/api/franchise_routes.py` lines 1108, 1364
   - **Status:** Backend redirect includes all required parameters
   - **Redirect URL Format:**
     - Already completed: `/static/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={req.team_id}&week={current_week}`
     - Success: `/static/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={team_id}&week={current_week}`
   - **Includes:** ✅ `mode=franchise`, ✅ `franchise_id`, ✅ `team_id`, ✅ `week`
   - **Frontend:** `FrontEnd/static/training.js` line 358 reads `team_id` from URL params and sends it to backend
   - **Note:** Success case uses resolved `team_id` (ObjectId), which is correct. Already completed case uses `req.team_id` directly, but since frontend sends ObjectId, this should work fine.

### **🔍 Needs Verification:**
2. **Command Center Data** - May need `team_id` parameter
3. **Page Initialization** - Some pages might need to read `team_id` from URL

---

## 🚨 **Known Gaps (Not Yet Addressed)**

### **1. Tournament Mode**
- We've only fixed Franchise Mode navigation
- Tournament Mode likely has similar issues
- Should perform same verification exercise for Tournament Mode

### **2. ~~Backend Training Redirect~~** ✅ **VERIFIED - CORRECT**
- ~~Training completion redirect needs verification~~ ✅ **COMPLETE**
- ~~Should check that redirect URL includes `mode`, `franchise_id`, `team_id`~~ ✅ **ALL INCLUDED**
- See "Verified Items" section above for details

### **3. Error Handling**
- Missing `team_id` fallback logic might not be implemented everywhere
- Invalid `team_id` error handling might not be consistent

---

## 💡 **Recommendations**

### **Before Testing:**
1. Review backend API endpoints to verify they accept `team_id` (ObjectId)
2. ~~Check backend training redirect to ensure it includes all variables~~ ✅ **VERIFIED - CORRECT** (see Verified Items section)
3. Verify page initialization code reads `team_id` from URL

### **During Testing:**
1. Test all navigation flows systematically
2. Test data loading on each page
3. Test data saving after changes
4. Test backward compatibility with old URLs

### **After Testing:**
1. Document any issues found
2. Prioritize fixes based on severity
3. Create follow-up tasks for remaining issues

---

## 🎯 **Bottom Line**

**Navigation should be perfect** - All transitions preserve the core anchor set.

**Data persistence might have gaps** - Some pages might need updates to:
- Read `team_id` from URL
- Pass `team_id` to backend APIs
- Handle missing/invalid `team_id` gracefully

**Expect some issues** - This is a large refactoring, and edge cases might surface during testing.

**Report everything** - Document all issues found so we can prioritize fixes.

