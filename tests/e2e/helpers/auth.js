/** Stub auth BEFORE navigation so authGuard sees a token. */
async function stubAuth(page) {
  await page.addInitScript(() => {
    localStorage.setItem('auth_token', 'e2e-stub-token');
    localStorage.setItem('auth_user', JSON.stringify({
      user_id: 'e2e-user',
      email: 'e2e@example.com',
      username: 'e2e',
    }));
  });
}
module.exports = { stubAuth };
