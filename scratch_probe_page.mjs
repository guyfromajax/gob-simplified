/** Why does court.html render no play button under Playwright when it does in the IDE browser? */
import { chromium } from "playwright";

const BASE = "http://localhost:8000";
const gameId = process.argv[2] || (await fetch(`${BASE}/api/init-game`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ home_team: "Lancaster", away_team: "Bentley-Truman", mode: "single", user_team_side: "home" }),
}).then((r) => r.json()).then((j) => j.game_id));
console.log("game_id:", gameId);

const browser = await chromium.launch({ headless: process.env.HEADED !== "1" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const logs = [];
page.on("console", (m) => logs.push(m.type() + ": " + m.text().slice(0, 240)));
page.on("pageerror", (e) => logs.push("PAGEERROR: " + String(e.message).slice(0, 300)));
page.on("requestfailed", (r) => logs.push("REQFAIL: " + r.url().slice(0, 140) + " " + (r.failure()?.errorText || "")));

await page.goto(`${BASE}/static/court.html?game_id=${gameId}&my_team=home&mode=single`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(6000);

const info = await page.evaluate(() => ({
  buttons: Array.from(document.querySelectorAll("button")).map((b) => ({ t: (b.innerText || "").trim().slice(0, 22), c: b.className.slice(0, 34) })).filter((x) => x.t || x.c).slice(0, 20),
  nButtons: document.querySelectorAll("button").length,
  canvases: document.querySelectorAll("canvas").length,
  hasScene: !!window.currentGameScene,
  bodyLen: document.body.innerHTML.length,
  bodyText: document.body.innerText.slice(0, 300),
  gameContainer: !!document.getElementById("phaser-container"),
}));
console.log(JSON.stringify(info, null, 1));
console.log("\n---- console/errors ----");
console.log(logs.slice(0, 40).join("\n") || "(none)");
await page.screenshot({ path: "/tmp/probe_court.png", fullPage: false });
await browser.close();
