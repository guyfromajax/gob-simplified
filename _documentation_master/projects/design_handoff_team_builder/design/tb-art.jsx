/* GOB Team Builder — React wrappers around the SHIPPED generators.

   No artwork is drawn here. Court calls teamCourtGenerator.js verbatim; Banner
   calls a composition from tb-banner-variants.jsx, each of which follows
   teamGeneratedArt.js's card-space contract exactly (400×141, shrink-to-fit
   wordmark, WCAG best-of-two ink).

   Shipping set, agreed: Keel · Baseline · Plate · Sash. The chevron that ships
   today is retired — its diagonal crosses the wordmark. BASELINE is the default.
*/
const TGA = window.TeamGeneratedArt;
const TCG = window.TeamCourtGenerator;
const CARD_W = TGA.CARD_W, CARD_H = TGA.CARD_H;
const DEFAULT_VARIANT = 'C';

/* the four shipping compositions, in the order the picker shows them */
const SHIPPING_VARIANTS = () =>
  (window.BANNER_VARIANTS || []).filter(v => v.key !== 'A');

const variantByKey = (key) => {
  const all = window.BANNER_VARIANTS || [];
  return all.find(v => v.key === (key || DEFAULT_VARIANT))
    || all.find(v => v.key === DEFAULT_VARIANT)
    || { key: 'A', draw: (ctx, w, h, o) => TGA.drawChevronBanner(ctx, w, h, o) };
};

const bannerOpts = (cfg) => ({
  name: cfg.name, mascot: cfg.mascot, abbreviation: cfg.abbr,
  primary: cfg.primary, secondary: cfg.secondary
});

/* Banner — draws the selected composition at any width, scaled from the 400×141
   card exactly as production does (same layout, never re-laid-out). */
function Banner({ cfg, width, dpr, meta }) {
  const ref = React.useRef(null);
  const [fontsReady, setFontsReady] = React.useState(false);
  React.useEffect(() => { TGA.ensureBannerFonts().then(() => setFontsReady(true)); }, []);
  React.useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const w = width || CARD_W;
    const h = Math.round(w * (CARD_H / CARD_W));
    const scale = dpr || Math.min(2, window.devicePixelRatio || 1);
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    /* backing store only — display size belongs to CSS, so containers can crop */
    const m = variantByKey(cfg.bannerVariant).draw(
      canvas.getContext('2d'), canvas.width, canvas.height, bannerOpts(cfg));
    if (meta) meta(m);
  }, [cfg.name, cfg.mascot, cfg.abbr, cfg.primary, cfg.secondary, cfg.bannerVariant,
    width, dpr, fontsReady]);
  return <canvas ref={ref} className="banner-canvas" aria-label={(cfg.name || '') + ' banner'} />;
}

/* diagnostics for the chosen composition — real numbers off a real draw */
function analyzeBanner(cfg) {
  const c = document.createElement('canvas');
  c.width = CARD_W; c.height = CARD_H;
  return variantByKey(cfg.bannerVariant).draw(c.getContext('2d'), CARD_W, CARD_H, bannerOpts(cfg));
}

/* Court — the real 3333×2083 parametric render, downscaled for display.
   Debounced: each render builds two full-size grain canvases. */
function Court({ cfg, width }) {
  const ref = React.useRef(null);
  const [busy, setBusy] = React.useState(false);
  const key = [cfg.hardwoodStyle, cfg.oobColor, cfg.laneColor, cfg.outsideWoodColor,
    cfg.halfArcFillColor, cfg.lineColor, cfg.primary, cfg.secondary].join('|');
  React.useEffect(() => {
    let cancelled = false;
    setBusy(true);
    const t = setTimeout(() => {
      if (cancelled) return;
      const full = TCG.renderCourtCanvas({
        primary: cfg.primary, secondary: cfg.secondary,
        hardwoodStyle: cfg.hardwoodStyle, oobColor: cfg.oobColor,
        laneColor: cfg.laneColor, outsideWoodColor: cfg.outsideWoodColor,
        halfArcFillColor: cfg.halfArcFillColor, lineColor: cfg.lineColor,
        useOverlays: false
      });
      const canvas = ref.current;
      if (!canvas || cancelled) return;
      const w = width || 960;
      canvas.width = w;
      canvas.height = Math.round(w * (TCG.HEIGHT / TCG.WIDTH));
      const ctx = canvas.getContext('2d');
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(full, 0, 0, canvas.width, canvas.height);
      setBusy(false);
    }, 140);
    return () => { cancelled = true; clearTimeout(t); };
  }, [key, width]);
  return (
    <div className={'court-wrap' + (busy ? ' busy' : '')}>
      <canvas ref={ref} className="court-canvas" aria-label="Court preview" />
    </div>
  );
}

/* Jersey — the shipped SVG preview. Two presets only: 1 SOLID, 2 SOLID WITH TRIM. */
function Jersey({ cfg, number }) {
  const src = TGA.jerseyPreviewDataUrl({
    primary: cfg.primary, secondary: cfg.secondary,
    jerseyPreset: cfg.jerseyPreset, number: number == null ? 23 : number
  });
  return <img className="jersey-svg" src={src} alt="Jersey preview" />;
}

/* Mark — the shipped 128×128 SVG lockup. */
function Mark({ cfg, size }) {
  const src = TGA.markDataUrl({
    name: cfg.name, abbreviation: cfg.abbr,
    primary: cfg.primary, secondary: cfg.secondary, size: size || 128
  });
  return <img className="mark-svg" src={src} alt={(cfg.name || '') + ' mark'} />;
}

/* Court defaults derived from the palette — the real defaultsFromTeamColors,
   which also darkens OOB when it would sit too close to the outside wood. */
function courtDefaults(primary, secondary) {
  return TCG.defaultsFromTeamColors(primary, secondary);
}

Object.assign(window, {
  Banner, Court, Jersey, Mark, courtDefaults, analyzeBanner,
  SHIPPING_VARIANTS, variantByKey, DEFAULT_VARIANT,
  TGA, TCG,
  HARDWOOD_VARIANTS: TCG.HARDWOOD_VARIANTS,
  HARDWOOD_TONES: TCG.HARDWOOD_TONES,
  inkOn: TGA.inkOn, contrast: TGA.contrastRatio, shadeHex: TGA.shadeHex,
  deriveThirdTone: TGA.deriveThirdTone
});
