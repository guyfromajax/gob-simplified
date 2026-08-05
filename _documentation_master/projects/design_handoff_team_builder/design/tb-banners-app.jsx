/* Banner composition options — five candidates on one bench.
   Each is drawn by its own function in tb-banner-variants.jsx, all following
   production's card-space contract, so whichever wins is a drop-in for
   drawChevronBanner. */
const { useState, useEffect, useRef, useMemo } = React;
const V = window.BANNER_VARIANTS;
const TG = window.TeamGeneratedArt;

/* deliberately includes the pairs that break compositions: a pale secondary
   that fights the type, and a dark-on-dark pair */
const TESTS = [
  { k: 'Cascade', p: '#1e5a8c', s: '#f2a83b' },
  { k: 'Pale', p: '#1f3a2e', s: '#e8dcc3' },
  { k: 'Dark', p: '#a6462c', s: '#1b2733' },
  { k: 'Hot', p: '#2c1b4d', s: '#de6b35' },
  { k: 'Mono', p: '#2b2b2b', s: '#d9a13b' }
];
const RECOMMEND = 'C';

function Draw({ variant, cfg, width, meta }) {
  const ref = useRef(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { TG.ensureBannerFonts().then(() => setReady(true)); }, []);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const h = Math.round(width * (141 / 400));
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(width * dpr);
    c.height = Math.round(h * dpr);
    const m = variant.draw(c.getContext('2d'), c.width, c.height, {
      name: cfg.name, mascot: cfg.mascot, abbreviation: cfg.abbr,
      primary: cfg.primary, secondary: cfg.secondary
    });
    if (meta) meta(m);
  }, [variant, cfg.name, cfg.mascot, cfg.abbr, cfg.primary, cfg.secondary, width, ready]);
  return <canvas ref={ref} />;
}

function Row({ variant, cfg }) {
  const [m, setM] = useState(null);
  const rec = variant.key === RECOMMEND;
  return (
    <div className={'vr' + (rec ? ' pick' : '')}>
      <div className="vr-hd">
        <div className="vr-k">{variant.key}</div>
        <h2>{variant.name}</h2>
        <div className="vr-tag">{variant.tag}</div>
        <div className="sp" />
        {variant.key === 'A' && <div className="badge b-ship">In production</div>}
        {rec && <div className="badge b-rec">My pick</div>}
      </div>
      <div className="vr-b">
        <div>
          <div className="slabel">1920 × 679 — primary banner</div>
          <div className="big"><Draw variant={variant} cfg={cfg} width={880} meta={setM} /></div>
          <p className="note" style={{ marginTop: 11 }}>{variant.note}</p>
        </div>
        <div className="side">
          <div>
            <div className="slabel">400 × 141 — true card size</div>
            <div className="true"><Draw variant={variant} cfg={cfg} width={400} /></div>
          </div>
          <div>
            <div className="slabel">in situ — mode select</div>
            <div className="card16">
              <Draw variant={variant} cfg={cfg} width={400} />
              <div className="ov"><span>0–0 · Conference 14 · Region G</span></div>
            </div>
          </div>
        </div>
      </div>
      {m && (
        <div className="diag">
          <span><b>ink</b> {m.ink === '#ffffff' ? 'white' : 'black'}</span>
          <span><b>wordmark</b> {Math.round(m.wordSize) + 'px' + (m.atFloor ? ' (floor)' : '')}</span>
          <span><b>contrast</b> <i className={(m.contrastPrimary || m.contrast) >= 4.5 ? 'ok' : 'warn'}>{(m.contrastPrimary || m.contrast).toFixed(2) + ':1'}</i></span>
          {m.mascotAlpha || m.alpha ? <span><b>mascot</b> {Math.round((m.mascotAlpha || m.alpha) * 100) + '% · ' + (m.mascotContrast || m.ratio).toFixed(2) + ':1'}</span> : null}
          {m.plateContrast ? <span><b>plate initials</b> <i className={m.plateContrast >= 4.5 ? 'ok' : 'warn'}>{m.plateContrast.toFixed(2) + ':1'}</i></span> : null}
          <span style={{ marginLeft: 'auto' }}><b>ghost</b> {m.initials}</span>
        </div>
      )}
    </div>
  );
}

function App() {
  const [cfg, setCfg] = useState({
    name: 'Cascade Valley', mascot: 'Timberwolves', abbr: 'CVU',
    primary: TESTS[0].p, secondary: TESTS[0].s
  });
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbBannerZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  useEffect(() => {
    const fit = () => setFitZ(Math.min(1, window.innerWidth / 1400));
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbBannerZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);
  const set = (k, v) => setCfg(c => ({ ...c, [k]: v }));

  return (
    <>
      <div className="vbar">
        <span>Prototype view — not part of the design</span>
        <div className="seg">
          {[['fit', 'Fit'], ['1', '100%'], ['1.25', '125%'], ['1.5', '150%']].map(([v, l]) => (
            <button key={v} className={zMode === v ? 'on' : ''} onClick={() => setZMode(v)}>{l}</button>
          ))}
        </div>
      </div>

      <div className="pg" style={{ zoom: z }} data-screen-label="Banner composition options">
        <div className="hd">
          <h1>Five banner compositions</h1>
          <p>All five follow the shipped contract exactly — card space is <b>400 × 141</b>, the wordmark shrinks to fit between 50px and a 20px floor, and ink is <b>pure black or white chosen by WCAG best-of-two</b>. Only the field changes, so whichever wins is a drop-in replacement for <b>drawChevronBanner</b>. Switch palettes below: the pale and dark pairs are the ones that expose a weak composition.</p>
        </div>

        <div className="bench">
          <div className="bf"><label>School name</label>
            <input type="text" value={cfg.name} maxLength="26" onChange={e => set('name', e.target.value)} /></div>
          <div className="bf narrow"><label>Mascot</label>
            <input type="text" value={cfg.mascot} maxLength="20" onChange={e => set('mascot', e.target.value)} /></div>
          <div className="bf tiny"><label>Abbr</label>
            <input type="text" value={cfg.abbr} maxLength="3"
              onChange={e => set('abbr', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ''))} /></div>
          <div className="bf"><label>Test palette</label>
            <div className="tests">
              {TESTS.map(t => (
                <div key={t.k}>
                  <button className={'tp' + (cfg.primary === t.p && cfg.secondary === t.s ? ' on' : '')}
                    onClick={() => setCfg(c => ({ ...c, primary: t.p, secondary: t.s }))} title={t.k}>
                    <i style={{ background: t.p }} /><i style={{ background: t.s }} />
                  </button>
                  <div className="tpn">{t.k}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="bspace" />
          <div className="hint">Try a long name — <b>Archbishop McClellan</b> — to see which compositions still hold when the wordmark shrinks.</div>
        </div>

        <div className="rows">
          {V.map(v => <Row key={v.key} variant={v} cfg={cfg} />)}
        </div>

        <div className="foot">
          <h3>What I'd ship, and why</h3>
          <p><b>C · Baseline.</b> It is the only composition where nothing at all sits over the wordmark, at any palette, at any name length — so it can never do the thing you flagged. It's also the most institutional of the five, which matches where this flow is trying to land: a program that looks like it has existed for eighty years, not a jersey graphic. The ghost initials still carry the identity, and the secondary reads at full strength along the bottom where it also anchors the gradient the Mode Select card lays over it.</p>
          <p>If the chevron's diagonal energy is non-negotiable, <b>E · Sash</b> is the compromise — same gesture, moved below the type so it underlines the mascot instead of crossing the name. <b>B · Keel</b> is the most conservative change from what ships: identical vocabulary, band relocated to the right edge, initials given a home. <b>D · Plate</b> is the strongest identity of the five and the riskiest — it's the only one where the secondary carries type, so its legibility depends on the plate contrast shown in each row's diagnostics.</p>
          <p>Production cost is the same for any of them: one new draw function beside <code>drawChevronBanner</code>, plus a stored <code>banner_variant</code> on the team if you want more than one. If only one ships, no stored field is needed at all.</p>
        </div>
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
