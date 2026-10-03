# Recruiting wire row cap

The Office recruiting wire (column 03, lean updates) now shows at most:

- **5** rows at the 1280 density
- **8** rows at 1920

`recruitCap()` in `FrontEnd/static/js/shared/officeHome.js` was 8 / 12. Fold trim is unchanged: only whole rows above the fold stay.

The Office rule in `UX_System.md` and the cap assertions in `tests/e2e/office-frontend.spec.js` (`recruiting keeps the latest event and whole rows`) match. That Playwright test passed.

On `develop` at the tree this report was written. Full suite not run. Targeted Playwright: 1 passed.
