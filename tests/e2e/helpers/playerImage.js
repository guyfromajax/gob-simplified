/** 1×1 PNG so showFoulOutPopup never races onerror → generic_headshot.png. */
const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
  'base64'
);

async function stubPlayerImage(page, playerId = 'test-1') {
  await page.route(`**/images/players/${playerId}.png`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: TINY_PNG,
    });
  });
}

module.exports = { stubPlayerImage };
