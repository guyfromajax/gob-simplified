export const TRAINING_SHELL = `<div class="training-container resource-page-container fcc-brand-page-shell training-resource-shell">
    <!-- Header -->
    <header class="training-header">
      <div class="training-header-left">
        <button id="back-btn" class="back-button" type="button">Back to Locker Room</button>
        <button id="training-tutorial-btn" type="button" class="gob-btn gob-btn--ghost training-tutorial-btn">Training Tutorial</button>
      </div>
      <div class="header-center">
        <h1 class="page-title">Team Training</h1>
        <!-- The two submit requirements, in the one place a coach already looks. Replaces
             the full-width "Before you submit" bar; the ids are unchanged so the same
             updateRequirementsBar() drives it. -->
        <div class="req-pill bud" id="requirements-bar" aria-label="Before you submit">
          <span class="req-pill-seg req-chip req-chip--points" id="req-points">
            <span class="req-chip-check" aria-hidden="true"></span>
            <span class="req-pill-label">Points</span>
            <span class="req-chip-value"><span id="req-points-used">0</span>/<span id="req-points-total">24</span></span>
            <span class="req-meter"><span class="req-meter-fill" id="req-points-meter"></span></span>
            <span class="points-display"><span id="points-remaining">24</span> left</span>
          </span>
          <span class="req-pill-div" aria-hidden="true"></span>
          <span class="req-pill-seg req-chip req-chip--focus" id="req-focus">
            <span class="req-chip-check" aria-hidden="true"></span>
            <span class="req-pill-label">Focus</span>
            <span class="req-chip-value" id="req-focus-value">Not selected</span>
            <button type="button" class="req-focus-nudge" id="req-focus-nudge" hidden>Choose one &rarr;</button>
          </span>
        </div>
      </div>
      <div class="header-actions">
        <button id="auto-train-btn" class="gob-btn gob-btn--ghost auto-train-button" type="button">Auto-Train</button>
        <div class="submit-stack">
          <button id="submit-btn" class="submit-button advance" data-sfx="SFX_COMMIT" disabled>Submit Training</button>
          <button id="recruiting-invites-btn" class="recruiting-invites-button" type="button" style="display:none;">Recruiting Invites</button>
        </div>
      </div>
    </header>

    <!-- Three equal columns: Player Drills · Scheme Installs · General -->
    <!-- Shown instead of the weekly point allocation when this week has no allocation to
         make: training already submitted, or a tournament week where the server refuses
         training outright. Player Development below stays put in both cases. -->
    <div class="training-state-note" id="training-state-note" hidden>
      <p class="training-state-note-head" id="training-state-note-head"></p>
      <p class="training-state-note-body" id="training-state-note-body"></p>
      <a class="gob-btn gob-btn--ghost training-state-note-link" id="training-state-note-link" hidden></a>
    </div>

    <div class="main-content-grid">
      <div class="content-section player-drills-section">
        <h2 class="section-header">Player Drills</h2>
        <div class="section-container">
          <div class="drill-stack">
            <div class="drill-group">
              <h3 class="drill-title">Offense</h3>
              <label class="slider-label">
                <span class="label-text">Inside Offense</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="offense-inside" data-category="player-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Outside Offense</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="offense-outside" data-category="player-drills">
                </div>
              </label>
            </div>

            <div class="drill-group">
              <h3 class="drill-title">Defense</h3>
              <label class="slider-label">
                <span class="label-text">Inside Defense</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="defense-inside" data-category="player-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Outside Defense</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="defense-outside" data-category="player-drills">
                </div>
              </label>
            </div>

            <div class="drill-group">
              <h3 class="drill-title">Technical</h3>
              <label class="slider-label">
                <span class="label-text">Passing</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="technical-passing" data-category="player-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Ball Handling</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="technical-ball-handling" data-category="player-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Rebounding</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="technical-rebounding" data-category="player-drills">
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>

      <div class="content-section scheme-installs-section">
        <h2 class="section-header">Scheme Installs</h2>
        <div class="section-container">
          <div class="drill-stack">
            <div class="drill-group">
              <h3 class="drill-title">Core</h3>
              <label class="slider-label">
                <span class="label-text">Offense Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="team-offense-install" data-category="team-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Defense Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="team-defense-install" data-category="team-drills">
                </div>
              </label>
            </div>

            <div class="drill-group">
              <h3 class="drill-title">Fast Break</h3>
              <label class="slider-label">
                <span class="label-text">Fast Break Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="fast-break-offense-install" data-category="team-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Fast Break Defense Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="fast-break-defense-install" data-category="team-drills">
                </div>
              </label>
            </div>

            <div class="drill-group">
              <h3 class="drill-title">Press/Traps</h3>
              <label class="slider-label">
                <span class="label-text">Press/Traps Offense Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="press-offense-install" data-category="team-drills">
                </div>
              </label>
              <label class="slider-label">
                <span class="label-text">Press/Traps Defense Install</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="press-defense-install" data-category="team-drills">
                </div>
              </label>
            </div>

          </div>

          <!-- Which plays the install points train. Sits under the install rows it governs. -->
          <div class="playbook-mode-selection">
            <h3 class="drill-title">Training Plays</h3>
            <p id="custom-playbook-banner" class="custom-playbook-banner" hidden>
              Custom playbook is configured for this session (CMD gains only on selected plays).
            </p>
            <div class="playbook-mode-toggle" role="group" aria-label="Training plays">
              <button type="button" id="playbook-mode-current-btn" class="playbook-mode-btn is-selected" aria-pressed="true">
                Current Playbooks
              </button>
              <button type="button" id="playbook-mode-custom-btn" class="playbook-mode-btn is-ghost" aria-pressed="false">
                Custom Playbook
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="content-section general-section">
        <h2 class="section-header">Full Team Sessions</h2>
        <div class="section-container">
          <div class="drill-stack">
            <h3 class="drill-title drill-title--spacer" aria-hidden="true">&nbsp;</h3>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Strength Training</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="weight-strength" data-category="player-drills">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Agility Training</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="weight-agility" data-category="player-drills">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Conditioning</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="general-conditioning" data-category="general">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Free Throws</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="general-free-throws" data-category="general">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Film Study</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="general-film-study" data-category="general">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Breaks</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="general-breaks" data-category="general">
                </div>
              </label>
            </div>
            <div class="drill-group">
              <label class="slider-label">
                <span class="label-text">Scrimmages</span>
                <div class="slider-container">
                  <input type="range" min="0" max="5" step="1" value="0" class="slider" id="team-scrimmages" data-category="team-drills">
                </div>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Coaching Style / Focus Section -->
    <div class="coaching-section">
      <h2 class="coaching-title">Coaching Focus</h2>
      <p class="coaching-subtitle">Sets what you emphasize across drills, scrimmages and locker-room talks.</p>
      <div class="archetypes-grid">
        <!-- Authoritarian -->
        <div class="archetype-block" data-archetype="authoritarian">
          <div class="archetype-header">
            <span class="arch-mark" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="10" r="3.5"/><path d="M6 6.5h8v3H9.4"/><path d="M3.2 3.6l1.1 1.5M6.4 2.6v1.9"/></svg></span>
            <span class="archetype-name">Authoritarian</span>
          </div>
          <div class="archetype-options">
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="authoritarian-discipline" class="archetype-radio">
              <span>Discipline</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="authoritarian-rebounding" class="archetype-radio">
              <span>Rebounding</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="authoritarian-execution" class="archetype-radio">
              <span>Execution</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="authoritarian-teamwork" class="archetype-radio">
              <span>Teamwork</span>
            </label>
          </div>
        </div>

        <!-- Systems Coach -->
        <div class="archetype-block" data-archetype="systems-coach">
          <div class="archetype-header">
            <span class="arch-mark" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="2.5" width="11" height="11" rx="2"/><path d="M5 5l2 2M7 5L5 7"/><circle cx="10.6" cy="10.6" r="1.3"/><path d="M6.2 10.8c1-.2 2.6-1.6 3.4-4"/></svg></span>
            <span class="archetype-name">Systems Coach</span>
          </div>
          <div class="archetype-options">
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="systems-coach-offense" class="archetype-radio">
              <span>Offense</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="systems-coach-defense" class="archetype-radio">
              <span>Defense</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="systems-coach-fast-breaks" class="archetype-radio">
              <span>Fast Break</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="systems-coach-press-trap" class="archetype-radio">
              <span>Press/Traps</span>
            </label>
          </div>
        </div>

        <!-- Player Maximizer -->
        <div class="archetype-block" data-archetype="player-maximizer">
          <div class="archetype-header">
            <span class="arch-mark" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 13.5h11"/><path d="M4.5 13.5v-3M8 13.5v-5.5M11.5 13.5V6.5"/><path d="M9.5 4.2l2-2 2 2"/></svg></span>
            <span class="archetype-name">Player Maximizer</span>
          </div>
          <div class="archetype-options">
            <!-- Each option opens the attribute modal under its own name. -->
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="player-maximizer-top-3" class="archetype-radio">
              <span>Top 3 Attributes</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="player-maximizer-attributes-4-6" class="archetype-radio">
              <span>Attributes 4&ndash;6</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="player-maximizer-positional-focus" class="archetype-radio">
              <span>Positional Focus</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="player-maximizer-custom" class="archetype-radio">
              <span>Custom</span>
            </label>
          </div>
        </div>

        <!-- Culture Builder -->
        <div class="archetype-block" data-archetype="culture-builder">
          <div class="archetype-header">
            <span class="arch-mark" aria-hidden="true"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M8 13.4S2.5 10.2 2.5 6.3A2.9 2.9 0 0 1 8 5a2.9 2.9 0 0 1 5.5 1.3c0 3.9-5.5 7.1-5.5 7.1z"/></svg></span>
            <span class="archetype-name">Culture Builder</span>
          </div>
          <div class="archetype-options">
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="culture-builder-inspire" class="archetype-radio">
              <span>Inspire</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="culture-builder-confidence" class="archetype-radio">
              <span>Confidence</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="culture-builder-community" class="archetype-radio">
              <span>Community Engagement</span>
            </label>
            <label class="archetype-option">
              <input type="radio" name="coaching-focus" value="culture-builder-teamwork" class="archetype-radio">
              <span>Team Building</span>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Player Development: per-player training position + focus, for the 12 active
         players. On the weekly page it sits under Coaching Focus as four columns of
         three; in Prep it is the whole tab, as a table. Read and written through the
         shared Development Focus module, so the six values cannot drift between screens. -->
    <section class="player-dev-section" id="player-dev-section" hidden>
      <p class="training-advance-pointer" id="training-advance-pointer" hidden>Weekly training is set when you advance.</p>
      <div class="player-dev-head">
        <h2 class="coaching-title player-dev-title">Player Development</h2>
        <button type="button" class="gob-btn gob-btn--ghost player-dev-tutorial-btn" id="player-dev-tutorial-btn">
          Training by Position &#8599;
        </button>
      </div>
      <!-- Summaries ABOVE the roster: a summary belongs before the detail it summarises,
           and twelve rows would otherwise push it below the fold. Markup and rendering are
           shared with the FCC Training tab (js/shared/playerDevelopmentGrid.js). -->
      <div class="pdg-tally">
        <div class="pdg-tally-group pdg-tally-positions"></div>
        <div class="pdg-tally-group pdg-tally-focuses"></div>
      </div>
      <div class="pdg-grid"></div>
    </section>
  </div>

  <!-- Player Maximizer attribute modal. .gob-modal-overlay keeps it a viewport layer:
       the focus shell adopts every other body child into .main, where a fixed box
       becomes an in-flow one and opens below the fold. -->
  <div id="custom-focus-modal" class="gob-modal-overlay custom-focus-modal" aria-hidden="true">
    <div class="gob-modal-backdrop"></div>
    <div class="custom-focus-modal-content" role="dialog" aria-modal="true" aria-labelledby="custom-focus-modal-title">
      <header class="custom-focus-modal-head">
        <span class="custom-focus-modal-eyebrow">Player Maximizer</span>
        <h2 class="custom-focus-modal-title" id="custom-focus-modal-title">Top 3 Attributes</h2>
        <p class="custom-focus-modal-hint" id="custom-focus-modal-hint"></p>
      </header>
      <div class="custom-focus-table-wrap">
        <table class="custom-focus-table" id="custom-focus-table">
          <thead id="custom-focus-thead"></thead>
          <tbody id="custom-focus-tbody"></tbody>
        </table>
      </div>
      <div class="custom-focus-modal-actions">
        <button type="button" id="custom-focus-cancel-btn" class="custom-focus-cancel-btn">Cancel</button>
        <button type="button" id="custom-focus-assign-btn" class="custom-focus-assign-btn" disabled>Assign Focus Attributes</button>
      </div>
    </div>
  </div>

  <!-- Auto-Train confirmation modal -->
  <div id="auto-train-modal" class="gob-modal-overlay">
    <div class="gob-modal-backdrop"></div>
    <div class="gob-modal-box">
      <div class="gob-modal-accent"></div>
      <div class="gob-modal-body">
        <div class="gob-modal-title" id="auto-train-modal-title">Training Lock In</div>
        <div class="gob-modal-subtitle" id="auto-train-modal-focus">Focus: Attributes 4–6 (Player Maximizer)</div>
      </div>
      <div class="gob-modal-actions">
        <button id="auto-train-modal-close" class="gob-modal-btn-dismiss">Close</button>
      </div>
    </div>
  </div>`;
