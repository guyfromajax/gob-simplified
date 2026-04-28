/**
 * Defense row keys (Phase 4): canonical `defense_id` slugs in scouting / game_state.
 * Keep in sync with `FrontEnd/static/defense-display.js` for non-module pages.
 */

const HCO_MAN_SLUG = "man";
const HCO_ZONE_SLUGS = ["2-3-zone", "3-2-zone", "1-3-1-zone"];

const LEGACY_ALIASES_BY_SLUG = {
  man: ["Man", "man"],
  "2-3-zone": ["2-3 Zone", "2-3-zone"],
  "3-2-zone": ["3-2 Zone", "3-2-zone"],
  "1-3-1-zone": ["1-3-1 Zone", "1-3-1-zone"],
};

const DISPLAY_LABEL_BY_SLUG = {
  man: "Man",
  "2-3-zone": "2-3 Zone",
  "3-2-zone": "3-2 Zone",
  "1-3-1-zone": "1-3-1 Zone",
  vs_Fast_Break: "vs Fast Break",
  FCP: "FCP",
  HCT: "HCT",
};

/**
 * First matching block on `scouting_data.defense` (canonical slug, then legacy display keys).
 */
export function getDefenseBlock(defense, slug) {
  if (!defense || typeof defense !== "object") return {};
  const keys = [slug, ...(LEGACY_ALIASES_BY_SLUG[slug] || [])];
  for (const k of keys) {
    if (!Object.prototype.hasOwnProperty.call(defense, k)) continue;
    const v = defense[k];
    if (v && typeof v === "object") return v;
  }
  return {};
}

export function displayLabelForDefenseSlug(slug) {
  if (!slug) return "";
  return DISPLAY_LABEL_BY_SLUG[slug] || slug;
}

/**
 * Rows for FCC / tournament / training playbook summary: man + zones in fixed order.
 * Each item: `{ name: display label, ...row fields }` for `createPlayRow`.
 */
export function buildPlaybookStyleDefenseRows(scoutingDefense) {
  const man_defenses = [];
  const zone_defenses = [];
  if (!scoutingDefense || typeof scoutingDefense !== "object") {
    return { man_defenses, zone_defenses };
  }
  const manRow = getDefenseBlock(scoutingDefense, HCO_MAN_SLUG);
  if (Object.keys(manRow).length > 0) {
    man_defenses.push({
      ...manRow,
      name: displayLabelForDefenseSlug(HCO_MAN_SLUG),
      defense_row_key: HCO_MAN_SLUG,
    });
  }
  for (const slug of HCO_ZONE_SLUGS) {
    const row = getDefenseBlock(scoutingDefense, slug);
    if (Object.keys(row).length > 0) {
      zone_defenses.push({
        ...row,
        name: displayLabelForDefenseSlug(slug),
        defense_row_key: slug,
      });
    }
  }
  return { man_defenses, zone_defenses };
}

/** Scoreboard strip: collapse to Man vs Zone for compact UI. */
export function scoreboardDefenseBucket(raw) {
  if (raw == null || raw === "") return "-";
  const s = String(raw).trim().toLowerCase();
  if (s === "man" || s === "base-man") return "Man";
  if (s.includes("man") && !s.includes("zone")) return "Man";
  if (s.includes("zone") || s.includes("-zone")) return "Zone";
  if (s === "zone") return "Zone";
  return "-";
}

const LEGACY_DISPLAY_LABELS = new Set(["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]);

/** Playcall center / status line: human-readable from slug or legacy string. */
export function statusLineDefenseLabel(raw) {
  if (raw == null || raw === "") return "";
  const s = String(raw).trim();
  if (LEGACY_DISPLAY_LABELS.has(s)) return s;
  if (DISPLAY_LABEL_BY_SLUG[s]) return DISPLAY_LABEL_BY_SLUG[s];
  const lower = s.toLowerCase();
  if (lower === "man" || lower === "base-man") return "Man";
  if (lower === "zone") return "2-3 Zone";
  const fromSlug = displayLabelForDefenseSlug(lower);
  if (fromSlug !== lower) return fromSlug;
  return s.charAt(0).toUpperCase() + s.slice(1);
}
