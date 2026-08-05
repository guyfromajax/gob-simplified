/* GOB Team Builder — Review · the curtain.
   Nothing on this screen is work. It exists to make the program feel like it
   already exists in a league that was running before the user arrived —
   context, not bigger artwork. */
const { useState, useMemo, useEffect } = React;
const { Banner, Court, courtDefaults, DEFAULT_VARIANT, TGA, TCG } = window;
const R = window.GOBRoster;

const PROGRAM = {
  name: 'Cascade Valley', mascot: 'Timberwolves', abbr: 'CVU',
  primary: '#1e5a8c', secondary: '#f2a83b', jerseyPreset: 2, bannerVariant: 'C',
  mode: 'capped', replaced: 'Rainier Central', conference: 14, region: 'G'
};
/* court params in the shipped generator's own shape */
const COURT = Object.assign({ primary: PROGRAM.primary, secondary: PROGRAM.secondary },
  courtDefaults(PROGRAM.primary, PROGRAM.secondary));

/* what the user built — a handful of departures from the inherited fifteen */
const EDITS = {
  0: { ht: 73 }, 10: { ht: 74 }, 11: { ht: 81 },
  5: { cls: 'SO' }, 2: { cls: 'FR' },
  1: { attrs: { SH: 92, SC: 65 } }
};

/* the real Conference 14, read from the league — the user's program stands in
   the slot of the program it replaced */
const L = window.GOBLeague;
const CONF = L.PROGRAMS.filter(p => p.conf === PROGRAM.conference)
  .sort((a, b) => b.confWins - a.confWins || b.ovWins - a.ovWins || a.name.localeCompare(b.name));
const STANDINGS = CONF.map(p => (p.name === PROGRAM.replaced
  ? { name: PROGRAM.name, conf: p.lastConf, ov: p.lastOv, me: true }
  : { name: p.name, conf: p.lastConf, ov: p.lastOv }));

const initials = (n) => n.split(/\s+/).map(w => w[0]).join('').slice(0, 3);

function App() {
  const [toast, setToast] = useState(null);
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbReviewZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  useEffect(() => {
    const fit = () => setFitZ(Math.min(1, window.innerWidth / 1440));
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbReviewZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);

  const players = useMemo(() => R.PLAYERS.map(p => {
    const e = EDITS[p.id] || {};
    return { ...p, ht: e.ht ?? p.ht, cls: e.cls ?? p.cls, attrs: { ...p.attrs, ...(e.attrs || {}) } };
  }), []);

  const htUsed = players.reduce((s, p) => s + p.ht, 0);
  const clUsed = players.reduce((s, p) => s + R.CLASS_RANK[p.cls], 0);
  const changed = players.filter(p => {
    const e = EDITS[p.id]; return !!e;
  }).length;
  const avgHt = htUsed / players.length;
  const shape = ['SR', 'JR', 'SO', 'FR'].map(c => players.filter(p => p.cls === c).length + ' ' + c).join(' · ');
  const capped = PROGRAM.mode === 'capped';
  const grades = useMemo(() => players.map(p => R.gradesFor(p.attrs, p.ht)), [players]);

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

      <div className="rv" style={{ zoom: z }} data-screen-label="Review — the curtain">
        <div className="rv-top">
          <div className="rv-eb">Review</div>
          <div className="rv-note">Everything below is still editable until you establish the program.</div>
        </div>

        <div className="hero"><Banner cfg={PROGRAM} width={820} /></div>

        <div className="card" style={{ marginTop: 14 }}>
          <div className="c-hd">
            <h2>Roster</h2>
          </div>
          <div className="fifteen">
            {players.map((p, i) => (
              <div className="pl" key={p.id}>
                <div className="pt" style={{ background: R.TONES[p.tone - 1] }}><i></i><b>{initials(p.name)}</b></div>
                <div className="pl-t">
                  <div className="pl-n"><span>{p.n}</span>{p.name}</div>
                  <div className="pl-m">
                    <span className="pos-b" style={{ background: R.POS_COLOR[p.pos] }}>{p.pos}</span>
                    <span className="cl">{p.cls}</span>
                    <span className="ht">{R.feetInches(p.ht)}</span>
                    {p.wo && <span className="wo">WO</span>}
                  </div>
                </div>
                <div className="rt">{grades[i][p.pos]}</div>
              </div>
            ))}
          </div>
        </div>


        <div className="rv-grid">
          <div className="col">
            <div className={'elig' + (capped ? '' : ' no')}>
              <div className="elig-v">{capped ? 'Eligible for online play' : 'Not eligible for online play'}</div>
              <div className="elig-b">
                Built <b>{capped ? 'capped' : 'uncapped'}</b>. <b>This cannot be changed later.</b>
              </div>
            </div>
            <div className="card">
              <div className="c-hd">
                <h2 style={{ whiteSpace: 'nowrap' }}>Conference {PROGRAM.conference}</h2>
                <div className="sup">Region {PROGRAM.region}</div>
              </div>
              <table className="tbl">
                <thead><tr>
                  <th className="l">Program</th><th>Conf</th><th>Overall</th><th>Preseason</th>
                </tr></thead>
                <tbody>
                  {STANDINGS.map((s, i) => (
                    <tr key={s.name} className={s.me ? 'me' : ''}
                      style={s.me ? { '--me': 'rgba(30,90,140,.5)', '--me2': PROGRAM.primary } : undefined}>
                      <td className="l nm">
                        <span className="pos" style={{ marginRight: 8 }}>{i + 1}</span>{s.name}
                      </td>
                      <td>{s.conf}</td><td>{s.ov}</td><td>0–0</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>


          </div>

          <div className="col">


            <div className="card">
              <div className="c-hd"><h2>Team Measures</h2></div>
              <div className="ms">
                <div className="ms-r"><div className="ms-k">Height budget</div>
                  <div className="ms-v">{htUsed.toLocaleString()}″<em>{htUsed === R.HEIGHT_BUDGET ? 'at the cap' : (R.HEIGHT_BUDGET - htUsed) + '″ under'}</em></div></div>
                <div className="ms-r"><div className="ms-k">Year budget</div>
                  <div className="ms-v">{clUsed} / {R.CLASS_BUDGET}<em className={clUsed === R.CLASS_BUDGET ? 'ok' : ''}>exact</em></div></div>
                <div className="ms-r"><div className="ms-k">Attribute points</div>
                  <div className="ms-v">15 / 15<em className="ok">all at inherited totals</em></div></div>
                <div className="ms-r"><div className="ms-k">Changed from inherited</div>
                  <div className="ms-v">{changed}<em className="ch">of fifteen</em></div></div>
                <div className="ms-r"><div className="ms-k">Average Height</div>
                  <div className="ms-v">{R.feetInches(Math.round(avgHt))}</div></div>
                <div className="ms-r"><div className="ms-k">Year shape</div>
                  <div className="ms-v" style={{ fontSize: 15 }}>{shape}</div></div>
              </div>
            </div>

            <div className="card">
              <div className="c-hd"><h2>Program Details</h2></div>
              <div className="ms">
                <div className="ms-r"><div className="ms-k">Conference</div><div className="ms-v">{PROGRAM.conference}</div></div>
                <div className="ms-r"><div className="ms-k">Region</div><div className="ms-v">{PROGRAM.region}</div></div>
                <div className="ms-r"><div className="ms-k">Replacing</div><div className="ms-v" style={{ fontSize: 17 }}>{PROGRAM.replaced}</div></div>
                <div className="ms-r"><div className="ms-k">National Programs</div><div className="ms-v">128</div></div>
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginTop: 14 }}>
          <div className="c-hd">
            <h2>Home Court</h2>
          </div>
          <div style={{ padding: '12px 16px 16px' }}>
            <div className="courtwrap"><Court cfg={COURT} width={700} /></div>
          </div>
        </div>

      </div>

      <div className="footbar">
        <div className="fb-in">
          <button className="btn ghost">← Back to the Roster</button>
          <div className="fb-t" />
          <button className="btn" onClick={() => setToast({
            t: 'Establishing ' + PROGRAM.name,
            s: 'The establish sequence is the next screen — it depends on how long Apply actually takes.'
          })}>Establish {PROGRAM.name}</button>
        </div>
      </div>

      {toast && (
        <div className="toast" onClick={() => setToast(null)}>
          <div className="t">{toast.t}</div><div className="s">{toast.s}</div>
        </div>
      )}
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
