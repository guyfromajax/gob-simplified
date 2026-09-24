/** Stub auth BEFORE navigation so authGuard sees a token.
 * When BASE_URL is not the hardcoded localhost:8000 API, point the page at
 * that origin. api-config.js otherwise always calls http://localhost:8000.
 */
async function stubAuth(page) {
  const apiBase = process.env.BASE_URL || '';
  await page.addInitScript((base) => {
    if (base) window.API_BASE_URL = base;
    localStorage.setItem('auth_token', 'e2e-stub-token');
    localStorage.setItem('auth_user', JSON.stringify({
      user_id: 'e2e-user',
      email: 'e2e@example.com',
      username: 'e2e',
    }));
  }, apiBase);
}
module.exports = { stubAuth };
