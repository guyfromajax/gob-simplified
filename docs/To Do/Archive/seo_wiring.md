Yes, I can help with SEO strategy here, then we can execute it together afterward.1) Audit: what's public right now?
Based on authGuard.js, the intended public routes are:/ and homepage(.html)login(.html)signup(.html)reset-password(.html)Repo audit of *.html shows:47 HTML files total46 include authGuard.jsThe only HTML file that does not include authGuard.js is maintenance.html (which is correct: maintenance page should be public)So your statement "homepage + signup/login pages are the only pages not behind auth" is effectively correct, with the extra note that reset-password and maintenance.html are also public by design.2) www vs non-www
No universal best practice. Pick one as canonical and permanently redirect the other to it.If you want simplest branding: use the apex geekedoutbasketball.com as canonical and redirect www to apex.If you want maximum DNS flexibility (common in bigger setups): use www.geekedoutbasketball.com as canonical and redirect apex to www.Either is fine; consistency is what matters for SEO.3) "Server-rendered marketing page"
Right now your homepage is a static HTML file served by Netlify. "Server-rendered" means HTML is generated at request time (or pre-rendered at build time) by a framework/CMS (Next.js, Remix, Astro, etc.), which can make it easier to scale content pages and metadata later. We can keep your current static setup now and still plan for a future marketing section.4) Keywords (too many?)
They're not "too many," but you should focus the homepage around 1 primary intent + 2 secondary intents, then expand with additional pages later.A good starting focus:Primary: "basketball simulation game"Secondary: "basketball coach game", "basketball sim"The rest (sports sim, basketball video game, etc.) become supporting phrases you naturally include in copy, headings, FAQ, and later dedicated pages.Proposed next strategy step (no code): decide canonical domain (www vs non-www) and write a "homepage SEO brief":1 H13–5 section headings150–250 words of above-the-fold copy using the primary/secondary phrases naturally3–6 FAQ questions you want to rank forIf you tell me which domain you want as canonical (www or non-www), I'll outline that homepage SEO brief in a way that maps cleanly to what we'll implement.

---

## SEO implementation checklist

Complete these one by one. Copy direction for carousel/homepage is in `docs/Website_Copy/carousel_copy.md`. Full brief is in `docs/To Do/seo_homepage_brief.md`.

- [X] **Homepage / carousel copy:** Update live homepage HTML so carousel headlines and sub-copy match `carousel_copy.md` (basketball simulation game, basketball sim, basketball simulation in sub-copy).
- [X] **Meta title:** Set homepage `<title>` to one of the options in `seo_homepage_brief.md` (e.g. "Basketball Sim | Basketball Simulation Game — Geeked Out Basketball") or close variant; keep ~60 characters.
- [X] **Meta description:** Add `<meta name="description" content="...">` with "basketball sim" and "basketball simulation game"; keep ~155 characters. See `seo_homepage_brief.md` for example.
- [ ] **FAQ block:** Add an FAQ section to the homepage with 3–6 questions/answers from `seo_homepage_brief.md` (optional: add FAQ schema/structured data later).
-  [X] **Canonical / other:** Confirm canonical URL is `https://geekedoutbasketball.com` (already set via Netlify). No www in canonical.
