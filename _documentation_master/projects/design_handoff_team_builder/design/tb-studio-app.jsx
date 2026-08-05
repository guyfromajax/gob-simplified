/* GOB Team Builder — Chapter II · Found (the studio).

   Every preview is drawn by the SHIPPED generators (teamGeneratedArt.js +
   teamCourtGenerator.js), so the controls expose exactly the inputs those
   generators accept — no more, no fewer:

     name · mascot · abbreviation · primary · secondary
     jerseyPreset  1 = SOLID, 2 = SOLID WITH TRIM
     court         hardwoodStyle {inside}_{outside} · oobColor · laneColor
                   outsideWoodColor · halfArcFillColor · lineColor

   Abbreviation uniqueness is the one debounced SERVER check in the flow.
   Contrast needs no UI: the generator picks black or white ink by WCAG
   best-of-two, so an unreadable banner cannot be produced. */
const { useState, useMemo, useRef, useEffect } = React;
const { Banner, Court, Jersey, courtDefaults, SHIPPING_VARIANTS,
  DEFAULT_VARIANT, TGA, TCG, HARDWOOD_TONES } = window;

const PALETTES = [
  { name: 'Cascade', p: '#1e5a8c', s: '#f2a83b' },
  { name: 'Ridge', p: '#1f3a2e', s: '#c9a227' },
  { name: 'Foundry', p: '#8c1d26', s: '#e8dcc3' },
  { name: 'Meridian', p: '#2c1b4d', s: '#e0b94a' },
  { name: 'Tidewater', p: '#0f4c4a', s: '#de6b35' },
  { name: 'Sandstone', p: '#a6462c', s: '#1b2733' },
  { name: 'Glacier', p: '#124e78', s: '#a8c6df' },
  { name: 'Ironwood', p: '#2b2b2b', s: '#d9a13b' }
];
const SWATCHES = ['#1e5a8c', '#124e78', '#1f3a2e', '#0f4c4a', '#2c1b4d', '#8c1d26', '#a6462c', '#2b2b2b',
  '#f2a83b', '#c9a227', '#de6b35', '#e8dcc3'];
const TONES = ['light', 'medium', 'dark'];
const TAKEN = ['NLS', 'RID', 'DUK', 'UNC', 'CVA', 'FHL', 'ORE', 'PAC', 'ABI', 'ADA'];
const SURPRISE = [
  ['Cascade Valley', 'Timberwolves', 0], ['Ironwood State', 'Prospectors', 7],
  ['Puget Bay', 'Mariners', 6], ['Marrow Creek', 'Ravens', 1],
  ['Fort Hollis', 'Sentinels', 3], ['Larkspur', 'Cardinals', 2],
  ['Alderton', 'Foundry', 5], ['Bell Harbor', 'Anchors', 4]
];

/* the generator's own initials rule, so the ghost mark always agrees */
const deriveAbbr = (name) => TGA.initialsFromName(name, null, null);

/* same affordance as the court's Custom chip: swatches, then a Custom chip that
   opens the OS color picker */
function ColorRow({ label, value, onChange }) {
  const custom = SWATCHES.indexOf(String(value).toLowerCase()) === -1;
  return (
    <div className="swrow"><b>{label}</b>
      <div className="sws">
        {SWATCHES.map(c => (
          <button key={c} className={'sw' + (String(value).toLowerCase() === c ? ' on' : '')}
            style={{ background: c }} onClick={() => onChange(c)} aria-label={c} />
        ))}
        <label className={'csw' + (custom ? ' on' : '')} style={{ background: value }}
          title="Pick any color">
          <input type="color" value={value} onChange={e => onChange(e.target.value)} />
        </label>
      </div>
    </div>
  );
}

/* One court field. Tokens resolve at render, so changing the palette moves the
   court with it; Custom is the only case that stores a literal hex. */
function CourtField({ label, hint, tokens, value, custom, onToken, onCustom, resolve }) {
  return (
    <div className="crow">
      <span>{label}{hint ? ' — ' + hint : ''}</span>
      <div className="chips">
        {tokens.map(t => (
          <button key={t} className={'chip' + (value === t ? ' on' : '')} onClick={() => onToken(t)}>
            <i style={{ background: resolve(t) }} />{t}
          </button>
        ))}
        {value === 'Custom' && (
          <label className="chip on" style={{ cursor: 'pointer', position: 'relative' }}>
            <i style={{ background: custom }} />
            <input type="color" value={custom} onChange={e => onCustom(e.target.value)}
              style={{ position: 'absolute', width: 0, height: 0, opacity: 0 }} />
            pick
          </label>
        )}
      </div>
    </div>
  );
}

function App() {
  const [cfg, setCfg] = useState(() => {
    const p = '#1e5a8c', s = '#f2a83b';
    const d = courtDefaults(p, s);
    return {
      name: 'Cascade Valley', mascot: 'Timberwolves', abbr: 'CVU',
      primary: p, secondary: s, jerseyPreset: 2, bannerVariant: DEFAULT_VARIANT,
      inside: 'medium', outside: 'medium',
      oob: 'Primary', lane: 'Primary', arc: 'Secondary',
      oobCustom: d.oobColor, laneCustom: p, outsideCustom: d.outsideWoodColor,
      arcCustom: s
    };
  });
  const [abbrTouched, setAbbrTouched] = useState(true);
  const [uniq, setUniq] = useState({ state: 'ok', code: 'CVU' });
  const [toast, setToast] = useState(null);
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbStudioZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  const timer = useRef(null);

  useEffect(() => {
    const fit = () => setFitZ(Math.min(1, window.innerWidth / 1440));
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbStudioZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);

  useEffect(() => {
    const code = cfg.abbr;
    if (code.length < 3) { setUniq({ state: 'short', code }); return; }
    setUniq({ state: 'checking', code });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      setUniq({ state: TAKEN.indexOf(code) > -1 ? 'taken' : 'ok', code });
    }, 480);
    return () => clearTimeout(timer.current);
  }, [cfg.abbr]);

  const set = (k, v) => setCfg(c => ({ ...c, [k]: v }));
  const setName = (v) => setCfg(c => ({ ...c, name: v, abbr: abbrTouched ? c.abbr : deriveAbbr(v) }));
  const applyPalette = (i) => setCfg(c => {
    const d = courtDefaults(PALETTES[i].p, PALETTES[i].s);
    return { ...c, primary: PALETTES[i].p, secondary: PALETTES[i].s, oobCustom: d.oobColor };
  });
  const surprise = () => {
    const [name, mascot, pi] = SURPRISE[Math.floor(Math.random() * SURPRISE.length)];
    setAbbrTouched(false);
    setCfg(c => ({
      ...c, name, mascot, abbr: deriveAbbr(name),
      primary: PALETTES[pi].p, secondary: PALETTES[pi].s,
      jerseyPreset: Math.random() < .5 ? 1 : 2,
      bannerVariant: ['B', 'C', 'D', 'E'][Math.floor(Math.random() * 4)],
      inside: TONES[Math.floor(Math.random() * 3)],
      outside: TONES[Math.floor(Math.random() * 3)]
    }));
  };

  /* hardwoodStyle only accepts the nine {inside}_{outside} tone keys; a custom
     midcourt rides in through outsideWoodColor, which overrides the outside
     half of the key (resolveWoodColors). Inside has no such override in the
     shipped generator — see github.md. */
  const outsideTone = cfg.outside === 'custom' ? 'medium' : cfg.outside;
  const hardwoodStyle = cfg.inside + '_' + outsideTone;
  const midcourtColor = cfg.outside === 'custom' ? cfg.outsideCustom : HARDWOOD_TONES[cfg.outside];
  const resolveTok = (t, customKey) => {
    if (t === 'Primary') return cfg.primary;
    if (t === 'Secondary') return cfg.secondary;
    if (t === 'Black') return '#101418';
    return cfg[customKey];
  };

  const courtCfg = {
    primary: cfg.primary, secondary: cfg.secondary,
    hardwoodStyle,
    oobColor: resolveTok(cfg.oob, 'oobCustom'),
    laneColor: resolveTok(cfg.lane, 'laneCustom'),
    outsideWoodColor: midcourtColor,
    halfArcFillColor: resolveTok(cfg.arc, 'arcCustom'),
    lineColor: TCG.COLORS.line
  };

  const uniqLine = {
    short: <span className="mute">three characters, exactly</span>,
    checking: <span className="mute">checking the league…</span>,
    ok: <span className="ok">✓ {uniq.code} is free</span>,
    taken: <span className="bad">✕ {uniq.code} is already in the league</span>
  }[uniq.state];
  const ready = cfg.name.trim() && cfg.mascot.trim() && uniq.state === 'ok';

  return (
    <>
      <div className="vbar">
        <span>Prototype view — not part of the design</span>
        <div className="seg">
          {[['fit', 'Fit'], ['1', '100%'], ['1.25', '125%'], ['1.5', '150%'], ['2', '200%']].map(([v, l]) => (
            <button key={v} className={zMode === v ? 'on' : ''} onClick={() => setZMode(v)}>{l}</button>
          ))}
        </div>
      </div>

      <div className="shell" style={{ zoom: z }} data-screen-label="Chapter II — Found (studio)">
        <div className="statebar">
          <div className="sb-cell chap"><div className="sb-k">Chapter</div>
            <div className="sb-v">Ⅱ · Found<small>Claim · <b style={{ color: '#fff' }}>Found</b> · The Floor</small></div></div>
          <div className="sb-cell link"><div className="sb-k">Replacing</div>
            <div className="sb-v">Rainier Central<small>Conference 14 · Region G</small></div></div>
          <div className="sb-cell"><div className="sb-k">Program</div>
            <div className="sb-v">{cfg.name || '—'}<small>{cfg.abbr || '—'} · {cfg.mascot || '—'}</small></div></div>
          <div className="sb-cell"><div className="sb-k">Build mode</div>
            <div className="sb-v"><span className="dot d-off" />Not chosen<small>next screen · decides online play</small></div></div>
          <div className="sb-cell"><div className="sb-k">Roster</div>
            <div className="sb-v"><span className="dot d-ok" />Inherited<small>15 from Rainier Central</small></div></div>
          <div className="sb-spacer" />
          <div className="sb-cell act">
            <span className="sb-rev">Editable until you found the program</span>
            <button className="btn" disabled={!ready}
              onClick={() => setToast({ t: 'Next — build mode', s: 'Capped or uncapped. It decides online eligibility and it is written permanently when the program is founded.' })}>
              Continue
            </button>
          </div>
        </div>

        <div className="studio">
          {/* the margin */}
          <div className="pane rail">
            <div className="pane-hd">
              <h2>Identity</h2><div className="sp" />
              <button className="btn ghost sm" onClick={surprise}>Surprise me</button>
            </div>

            <div className="grp">
              <div className="fld"><label>School name</label>
                <input value={cfg.name} maxLength="26" onChange={e => setName(e.target.value)} /></div>
              <div className="row2">
                <div className="fld"><label>Mascot</label>
                  <input value={cfg.mascot} maxLength="20" onChange={e => set('mascot', e.target.value)} /></div>
                <div className={'fld abbr ' + (uniq.state === 'ok' ? 'ok' : uniq.state === 'taken' ? 'no' : '')}>
                  <label>Abbreviation</label>
                  <input value={cfg.abbr} maxLength="3"
                    onChange={e => { setAbbrTouched(true); set('abbr', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '')); }} />
                </div>
              </div>
              <div className="uniq">{uniqLine}</div>
            </div>

            <div className="grp">
              <div className="grp-k"><span>Palette</span></div>
              <div className="pals">
                {PALETTES.map((pl, i) => (
                  <button key={pl.name} title={pl.name} onClick={() => applyPalette(i)}
                    className={'pal' + (cfg.primary === pl.p && cfg.secondary === pl.s ? ' on' : '')}>
                    <i style={{ background: pl.p }} /><i style={{ background: pl.s }} />
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 11 }}>
                <ColorRow label="Primary" value={cfg.primary} onChange={v => set('primary', v)} />
                <ColorRow label="Secondary" value={cfg.secondary} onChange={v => set('secondary', v)} />
              </div>
            </div>

            <div className="grp">
              <div className="grp-k"><span>Court</span></div>
              <div className="crow"><span>Hardwood — inside the arcs</span>
                <div className="chips">
                  {TONES.map(t => (
                    <button key={t} className={'chip' + (cfg.inside === t ? ' on' : '')} onClick={() => set('inside', t)}>
                      <i style={{ background: HARDWOOD_TONES[t] }} />{t}</button>
                  ))}
                </div>
              </div>
              <div className="crow"><span>Hardwood — midcourt</span>
                <div className="chips">
                  {TONES.map(t => (
                    <button key={t} className={'chip' + (cfg.outside === t ? ' on' : '')} onClick={() => set('outside', t)}>
                      <i style={{ background: HARDWOOD_TONES[t] }} />{t}</button>
                  ))}
                  <label className={'chip' + (cfg.outside === 'custom' ? ' on' : '')} style={{ cursor: 'pointer', position: 'relative' }}>
                    <i style={{ background: cfg.outsideCustom }} />custom
                    <input type="color" value={cfg.outsideCustom}
                      onChange={e => setCfg(c => ({ ...c, outside: 'custom', outsideCustom: e.target.value }))}
                      onClick={() => set('outside', 'custom')}
                      style={{ position: 'absolute', width: 0, height: 0, opacity: 0 }} />
                  </label>
                </div>
              </div>
              <CourtField label="Out of bounds" tokens={['Primary', 'Secondary', 'Black', 'Custom']}
                value={cfg.oob} custom={cfg.oobCustom} resolve={t => resolveTok(t, 'oobCustom')}
                onToken={v => set('oob', v)} onCustom={v => set('oobCustom', v)} />
              <CourtField label="Free-throw lane" tokens={['Primary', 'Secondary', 'Custom']}
                value={cfg.lane} custom={cfg.laneCustom} resolve={t => resolveTok(t, 'laneCustom')}
                onToken={v => set('lane', v)} onCustom={v => set('laneCustom', v)} />
              <CourtField label="Half-circle arcs" hint="lane caps" tokens={['Secondary', 'Primary', 'Custom']}
                value={cfg.arc} custom={cfg.arcCustom} resolve={t => resolveTok(t, 'arcCustom')}
                onToken={v => set('arc', v)} onCustom={v => set('arcCustom', v)} />
            </div>

            <div className="rail-ft">
              <button className="btn ghost sm">← Back to Claim</button>
            </div>
          </div>

          {/* the content */}
          <div className="pv">
            <div className="pvtop">
              <div className="frame">
                <div className="frame-k">Program banner</div>
                <div className="frame-b"><Banner cfg={cfg} width={780} /></div>
                <div className="styles">
                  <span className="styles-k">Style</span>
                  {SHIPPING_VARIANTS().map(v => (
                    <button key={v.key} title={v.note}
                      className={'stbtn' + (cfg.bannerVariant === v.key ? ' on' : '')}
                      onClick={() => set('bannerVariant', v.key)}>{v.name}</button>
                  ))}
                </div>
              </div>
              <div className="situ-c jersey-c">
                <div className="situ-b jersey-b"><Jersey cfg={cfg} number={23} /></div>
                <div className="situ-styles">
                  {[[1, 'Solid'], [2, 'Solid with trim']].map(([v, l]) => (
                    <button key={v} className={'stbtn' + (cfg.jerseyPreset === v ? ' on' : '')}
                      onClick={() => set('jerseyPreset', v)}>{l}</button>
                  ))}
                </div>
              </div>
            </div>

            <div className="frame">
              <div className="frame-b"><Court cfg={courtCfg} width={980} /></div>
              <div className="legend">
                <span><i style={{ background: courtCfg.oobColor }} />Out of bounds</span>
                <span><i style={{ background: midcourtColor }} />Midcourt</span>
                <span><i style={{ background: HARDWOOD_TONES[cfg.inside] }} />Inside arcs</span>
                <span><i style={{ background: courtCfg.laneColor }} />Lane</span>
                <span><i style={{ background: courtCfg.halfArcFillColor }} />Arcs</span>
              </div>
            </div>
          </div>
        </div>

        {toast && (
          <div className="toast" onClick={() => setToast(null)}>
            <div className="t">{toast.t}</div><div className="s">{toast.s}</div>
          </div>
        )}
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
