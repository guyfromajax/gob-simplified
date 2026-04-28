/**
 * Global helpers for static pages (FCC, tournament, training-report, box-score).
 * Duplicates logic in `js/phaser/utils/defenseUi.js` — update both when labels/order change.
 */
(function (global) {
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

  function getDefenseBlock(defense, slug) {
    if (!defense || typeof defense !== "object") return {};
    const keys = [slug, ...(LEGACY_ALIASES_BY_SLUG[slug] || [])];
    for (const k of keys) {
      if (!Object.prototype.hasOwnProperty.call(defense, k)) continue;
      const v = defense[k];
      if (v && typeof v === "object") return v;
    }
    return {};
  }

  function displayLabelForDefenseSlug(slug) {
    if (!slug) return "";
    return DISPLAY_LABEL_BY_SLUG[slug] || slug;
  }

  function buildPlaybookStyleDefenseRows(scoutingDefense) {
    const man_defenses = [];
    const zone_defenses = [];
    if (!scoutingDefense || typeof scoutingDefense !== "object") {
      return { man_defenses, zone_defenses };
    }
    const manRow = getDefenseBlock(scoutingDefense, HCO_MAN_SLUG);
    if (Object.keys(manRow).length > 0) {
      man_defenses.push({ name: displayLabelForDefenseSlug(HCO_MAN_SLUG), ...manRow });
    }
    for (const slug of HCO_ZONE_SLUGS) {
      const row = getDefenseBlock(scoutingDefense, slug);
      if (Object.keys(row).length > 0) {
        zone_defenses.push({ name: displayLabelForDefenseSlug(slug), ...row });
      }
    }
    return { man_defenses, zone_defenses };
  }

  global.GOBDefenseDisplay = {
    getDefenseBlock,
    displayLabelForDefenseSlug,
    buildPlaybookStyleDefenseRows,
    DISPLAY_LABEL_BY_SLUG,
    HCO_ZONE_SLUGS,
    HCO_MAN_SLUG,
  };
})(typeof window !== "undefined" ? window : globalThis);
