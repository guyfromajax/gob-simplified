/**
 * Accessible show/hide toggle for password fields.
 *
 * Markup:
 *   <div class="password-field">
 *     <input type="password" id="password">
 *     <button type="button" class="password-toggle" aria-controls="password"
 *             aria-label="Show password" aria-pressed="false"></button>
 *   </div>
 *
 * Include after the fields exist:
 *   <script src="/js/shared/passwordToggle.js"></script>
 */
(function (global) {
  const SHOW_LABEL = "Show password";
  const HIDE_LABEL = "Hide password";

  const ICON_SVG = {
    show:
      '<svg class="password-toggle-icon password-toggle-icon-show" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M12 5c-5.2 0-9.2 4.1-10.7 6.3-.3.4-.3 1 0 1.4C2.8 14.9 6.8 19 12 19s9.2-4.1 10.7-6.3c.3-.4.3-1 0-1.4C21.2 9.1 17.2 5 12 5zm0 12c-3.7 0-6.9-2.8-8.4-5C5.1 9.8 8.3 7 12 7s6.9 2.8 8.4 5C18.9 14.2 15.7 17 12 17zm0-8a3 3 0 100 6 3 3 0 000-6z"/></svg>',
    hide:
      '<svg class="password-toggle-icon password-toggle-icon-hide" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
      '<path fill="currentColor" d="M3.3 2.3L2 3.6l3.1 3.1C3.4 8.4 2.2 10 1.3 11.3c-.3.4-.3 1 0 1.4C2.8 14.9 6.8 19 12 19c2 0 3.8-.6 5.4-1.5l3 3 1.3-1.3L3.3 2.3zM12 17c-3.7 0-6.9-2.8-8.4-5 .8-1.2 2-2.4 3.5-3.3l1.6 1.6A3 3 0 0012 15a3 3 0 002.7-1.8l1.6 1.6C15.2 16.2 13.7 17 12 17zm8.4-5.7c-.4.6-.9 1.2-1.5 1.8l-1.5-1.5c.4-.5.6-1 .6-1.6a3 3 0 00-3-3c-.6 0-1.1.2-1.6.6L11.9 6C12 6 12 6 12 6c5.2 0 9.2 4.1 10.7 6.3.1.2.1.4 0 .6-.1.2-.2.3-.3.4z"/></svg>',
  };

  function bind(button) {
    if (!(button instanceof HTMLButtonElement) || button.dataset.passwordToggleBound === "true") {
      return;
    }
    const inputId = button.getAttribute("aria-controls");
    const field = button.closest(".password-field");
    const input = (inputId && document.getElementById(inputId)) || (field && field.querySelector("input"));
    if (!(input instanceof HTMLInputElement)) {
      return;
    }
    if (!button.innerHTML.trim()) {
      button.innerHTML = ICON_SVG.show + ICON_SVG.hide;
    }
    button.setAttribute("aria-label", SHOW_LABEL);
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", function () {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", show ? "true" : "false");
      button.setAttribute("aria-label", show ? HIDE_LABEL : SHOW_LABEL);
    });
    button.dataset.passwordToggleBound = "true";
  }

  function attachAll(root) {
    const scope = root || document;
    scope.querySelectorAll(".password-toggle").forEach(bind);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      attachAll(document);
    });
  } else {
    attachAll(document);
  }

  global.GOB_PasswordToggle = { attachAll: attachAll };
})(window);
