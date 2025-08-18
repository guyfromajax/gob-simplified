// Minimal interactions for marketing homepage.
// Toggles a class based on input method to manage focus outlines.

document.addEventListener('mousedown', () => {
  document.body.classList.add('using-mouse');
});

document.addEventListener('keydown', () => {
  document.body.classList.remove('using-mouse');
});
