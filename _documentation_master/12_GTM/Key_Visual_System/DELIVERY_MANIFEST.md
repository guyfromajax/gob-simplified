# Delivery manifest — where every built file goes

Rebuilding a file changes nothing until it is re-uploaded. This is the list of what feeds
what, so a change to the master or the cutout can be traced to everything downstream of it.

**Last verified: 2026-09-03.** Update the "live" column when you upload something.

## Steam — `steam/` (8 files)

Store Page Admin → Graphical Assets → **Store assets** or **Library assets** → Publish.
No Valve review is needed for asset changes once the page is approved; they go live on
publish. Choose **base assets**, not "create new temporary override" — overrides are for
events and sales.

| file | Steam slot | live |
|---|---|---|
| `header_capsule_920x430.png` | Header Capsule 920×430 | ✅ 2026-09-02 |
| `small_capsule_462x174.png` | Small Capsule 462×174 → auto 184×69, 120×45 | ✅ 2026-09-03 (logo-only revision) |
| `main_capsule_1232x706.png` | Main Capsule 1232×706 | ✅ 2026-09-02 |
| `vertical_capsule_748x896.png` | Vertical Capsule 748×896 | ✅ 2026-09-02 |
| `page_background_1438x810.png` | Page Background (optional) | ✅ 2026-09-02 |
| `library_capsule_600x900.png` | Library Capsule 600×900 → auto 300×450 | ✅ 2026-09-02 |
| `library_header_920x430.png` | Library Header 920×430 | ✅ 2026-09-02 |
| `library_hero_3840x1240.png` | Library Hero 3840×1240 — **no text** | ✅ 2026-09-02 |

`header_capsule` and `library_header` are the **same image** in two slots — same
dimensions, same job. Expect identical hashes; that is not a mistake.

**Not built here:** the Library Logo (≥1280 wide, transparent PNG, logotype only) and the
client/shortcut icons. They are not KV derivatives and live with the brand assets.

Also not built here, and not a Steam slot at all: `10 sub-mark 2432x576`. It is a secondary
lockup for use *inside* other artwork. It does not get uploaded anywhere on its own.

## Social — `formats/` (10 files)

| file | destination | live |
|---|---|---|
| `yt_thumbnail_trailer_2560x1440.png` (+ `_1280x720`) | YouTube launch-trailer thumbnail | pending trailer publish |
| `yt_banner_2560x1440.png` | YouTube channel banner | ✅ 2026-09-02 |
| `x_header_1500x500.png` | X profile header | ✅ 2026-09-02 |
| `x_post_1600x900.png` | X in-feed image | as needed |
| `discord_banner_960x540.png` | Discord server banner | not confirmed |
| `discord_icon_512x512.png` | Discord server icon | not confirmed |
| `square_1080x1080.png` | square placements | as needed |
| `web_hero_2560x1174.png` | geekedoutbasketball.com hero | not confirmed |
| `kv_16x9_1280x720.png` | generic key art — **never upload as a thumbnail** | n/a |

`kv_16x9` is named "kv" rather than "thumbnail" deliberately, so it cannot be grabbed by
mistake for a YouTube upload. It carries no type.

## What a change propagates to

| if you change… | rebuild | re-upload |
|---|---|---|
| `marks.py`, `ball.py`, or anything upstream of the master | everything | all 18 |
| `cutouts.py` | formats, stage, steam | square, Discord icon, both trailer thumbnails, and every Steam capsule that stages Rozier |
| `formats.py` | formats, then stage (it overwrites three) | the affected social files |
| `stage.py` | stage | square, Discord icon, trailer thumbnails, YouTube banner |
| `steam.py` | steam | the affected Steam capsules only |
| `assets/gob_logo.png` | stage, steam | trailer thumbnails and all six logo-bearing capsules |

The master itself has not changed since it was locked, and every fix since has been
downstream of it. Verify with a pixel diff before assuming otherwise — `README.md` records
the bit-identical rebuild check.

## Trailer

The trailer is not built by this system. Two masters exist, differing by one word on the
end card: **Steam** says `WISHLIST NOW`, **off-Steam** says `WISHLIST ON STEAM`. YouTube,
Reddit and Discord get the off-Steam master.

Steam trailer poster images must be **an actual frame from the video** — the KV thumbnail
cannot be used as the Steam poster unless it appears in the cut.

## Known outstanding

- The trailer film renders its cards in `#F09018`; brand orange is `#F79420`. A card
  re-render and a remux. The capsules and thumbnails are correct.
- A Nike swoosh is visible on the coach's polo in the live "RECRUITING!" YouTube
  thumbnail — third-party trademark on commercial marketing art, now pointing at a live
  store page.
- Commercial-use terms for Google AI Studio output on the current tier are unconfirmed.
