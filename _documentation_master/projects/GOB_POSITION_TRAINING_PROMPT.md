Please implement the position-based training-focus system described in .

Read the entire specification before making changes. Begin by inspecting the repository to understand the existing player model, MongoDB document structure, training calculation, position-efficiency data, player training UI, API schemas, and Advanced Topics tutorial implementation.

Important requirements:

1. Determine whether players already have a canonical `position` field and document where it is defined and consumed. Reuse that field without renaming it, duplicating it, or changing its existing gameplay meaning.

2. Add a separate `training_focus` field with these allowed stored values:

   * `standard`
   * `offensive`
   * `defensive`
   * `athletic`
   * `fundamentals`
   * `rebounding`

3. Missing or null `training_focus` values must safely resolve to `standard`, including all existing player records and saved games. Follow the repository’s established migration or backward-compatibility pattern.

4. Replace the current position-only training-efficiency lookup with a position-plus-focus lookup. Do not apply both the old multiplier and the new multiplier. The selected profile should be the single source of the training multiplier.

5. Use the exact percentage matrices in the specification. Do not adjust, normalize, or reinterpret the supplied numbers. Every profile must total 808, and FT, IQ, and ND must remain at 100 in every profile.

6. Centralize the matrix so gameplay and the tutorial cannot drift apart. Prefer a single shared source. If the frontend and backend cannot import the same module, establish one authoritative source with a clear API, serialization, or generation path rather than maintaining two manually copied matrices.

7. Locate the existing player training/development interface and add the least disruptive control for viewing and changing a player’s training focus. Changing focus must not change the player’s position and must only affect future training.

8. If there is no obvious existing interface for selecting a player’s focus, do not invent a major new navigation flow. Report the best candidate locations and what decision is needed before proceeding with that specific UI portion. Continue implementing the unambiguous backend, data-model, matrix, and tutorial work where possible.

9. Update the existing Advanced Topics tutorial display to support two orientations:

   * By Position: select PG, SG, SF, PF, or C and display all six focus profiles for that position side by side.
   * By Focus: select Standard, Offensive, Defensive, Athletic, Fundamentals, or Rebounding and display all five positions for that focus side by side.

10. Add a clear “By Position / By Focus” mode control. Preserve the current styling, percentage colors, legend, responsive behavior, and accessibility conventions. Default to By Position → PG unless the existing tutorial architecture provides a stronger reason not to.

11. Add automated validation for all 30 profiles, including totals, required attributes, fixed core attributes, legacy defaults, invalid values, persistence, representative training calculations, tutorial rendering, and protection against double-applying multipliers.

12. Preserve all unrelated uses of player position and avoid unrelated simulation or player-generation changes.

Before editing, give me a concise findings summary covering:

* Whether `position` already exists and its format
* Where the current training multiplier is calculated
* Where the current percentage matrix lives
* How player data is persisted and validated
* Where `training_focus` should be selected
* How the tutorial is currently constructed
* Any conflict between the specification and the existing architecture

Then implement the change. Afterward, report:

* Files changed and why
* Data-model and backward-compatibility handling
* Location of the canonical matrix
* Training calculation changes
* Player focus-selection UI changes
* Tutorial changes
* Tests added or updated
* Exact validation commands and results
* Any remaining product, migration, or deployment decisions

Do not consider the task complete until the relevant backend tests, frontend tests, type checks, linting, and builds pass, or you have clearly documented a pre-existing failure with evidence.
