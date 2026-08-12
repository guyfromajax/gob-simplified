/* GOB Team Builder — the establish sequence.

   The wait after Apply, used rather than padded. Three beats:
     1  the banner arrives — the artwork the user made, at full size
     2  the charter writes itself — five facts, each one real
     3  the takeover, literally — their row in the standings becomes yours

   Register: gravity, not celebration. No confetti, no "Congratulations!".
   The payoff for this audience is specificity — a plausible program appearing
   in a real table. Timing is a floor, not a fiction: the sequence runs to its
   own rhythm and the close is gated on the server actually finishing, so if
   Apply is instant the user still gets the beat, and if it is slow the last
   line waits with an honest label. */
const { useState, useEffect, useRef } = React;
const { Banner } = window;
const L = window.GOBLeague;

const PROGRAM = {
  name: 'Cascade Valley', mascot: 'Timberwolves', abbr: 'CVU',
  primary: '#1e5a8c', secondary: '#f2a83b', bannerVariant: 'C',
  replaced: 'Rainier Central', conference: 14, region: 'G',
  mode: 'capped', players: 15, hardwood: 'Medium', jersey: 'Solid with trim'
};

/* how long Apply actually takes, in ms — the one number this screen needs */
const SERVER_MS = 2600;

const CHARTER = [
  { k: 'Program registered', v: PROGRAM.name, e: PROGRAM.abbr },
  { k: 'Conference seat', v: 'Conference ' + PROGRAM.conference, e: 'Region ' + PROGRAM.region },
  { k: 'Taking the place of', v: PROGRAM.replaced },
  { k: 'Roster assigned', v: PROGRAM.players + ' players', e: '12 scholarship · 3 walk-ons' },
  { k: 'Court and uniforms', v: PROGRAM.hardwood + ' hardwood', e: PROGRAM.jersey },
  { k: 'Build mode', v: PROGRAM.mode === 'capped' ? 'Capped' : 'Uncapped',
    e: PROGRAM.mode === 'capped' ? 'eligible for online play' : 'not eligible for online play',
    ok: PROGRAM.mode === 'capped' }
];

const CONF = L.PROGRAMS.filter(p => p.conf === PROGRAM.conference)
  .sort((a, b) => b.confWins - a.confWins || b.ovWins - a.ovWins || a.name.localeCompare(b.name));

function App() {
  const [phase, setPhase] = useState(-1);
  const [lines, setLines] = useState(0);
  const [swapped, setSwapped] = useState(false);
  const [ready, setReady] = useState(false);
  const [pct, setPct] = useState(0);
  const [zMode, setZMode] = useState(() => localStorage.getItem('tbEstZoom') || 'fit');
  const [fitZ, setFitZ] = useState(1);
  const [run, setRun] = useState(0);
  const timers = useRef([]);

  useEffect(() => {
    const fit = () => {
      setFitZ(Math.min(1, window.innerWidth / 1200));
      const vb = document.querySelector('.vbar');
      document.documentElement.style.setProperty('--chrome-h',
        (vb ? vb.getBoundingClientRect().height : 0) + 'px');
    };
    fit(); window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => { localStorage.setItem('tbEstZoom', zMode); }, [zMode]);
  const z = zMode === 'fit' ? fitZ : Number(zMode);

  useEffect(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setPhase(-1); setLines(0); setSwapped(false); setReady(false); setPct(0);
    const at = (ms, fn) => timers.current.push(setTimeout(fn, ms));

    at(60, () => setPhase(0));                       // banner
    at(720, () => setPhase(1));                      // charter opens
    CHARTER.forEach((_, i) => at(760 + i * 210, () => setLines(i + 1)));
    at(760 + CHARTER.length * 210 + 180, () => setPhase(2));   // standings
    at(760 + CHARTER.length * 210 + 900, () => setSwapped(true));
    at(SERVER_MS, () => setReady(true));

    /* the rule reports elapsed against the real Apply, not a scripted curve */
    const step = 120;
    for (let t = step; t <= SERVER_MS; t += step) {
      const p = Math.min(100, Math.round(t / SERVER_MS * 100));
      at(t, () => setPct(p));
    }
    return () => timers.current.forEach(clearTimeout);
  }, [run]);

  /* the close waits for both the last beat and the server */
  useEffect(() => {
    if (ready && swapped) {
      const t = setTimeout(() => setPhase(3), 420);
      return () => clearTimeout(t);
    }
  }, [ready, swapped]);

  const waitLabel = !swapped ? 'Writing the charter'
    : (!ready ? 'Waiting on the league office' : 'Complete');

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

      <div className={phase < 0 ? 'est' : 'est p' + phase} style={{ zoom: z }}
        data-screen-label="Establish sequence">
        <div className="stage">
          <div className="art"><Banner cfg={PROGRAM} width={660} /></div>

          <div className="cols">
          <div className="charter">
            {CHARTER.map((c, i) => (
              <div className={'ch-r' + (i < lines ? ' in' : '')} key={c.k}>
                <div className="ch-k">{c.k}</div>
                <div className="ch-v">{c.v}
                  {c.e && <em className={c.ok === undefined ? '' : (c.ok ? 'yes' : 'no')}>{c.e}</em>}
                </div>
              </div>
            ))}
          </div>

          <div className="swap">
            <div className="sw-k">Conference {PROGRAM.conference} · {swapped ? 'your seat' : 'the seat you are taking'}</div>
            <table className="sw-t">
              <tbody>
                {CONF.map((p, i) => {
                  const isSlot = p.name === PROGRAM.replaced;
                  return (
                    <tr key={p.name} className={isSlot ? ('slot ' + (swapped ? 'now' : 'was')) : ''}>
                      <td className="sw-mark">{i + 1}</td>
                      <td className="n">{isSlot && swapped ? PROGRAM.name : p.name}</td>
                      <td className="r">{p.lastConf} · {p.lastOv}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </div>

          <div className="wait">
            <div className="w-rule"><i style={{ width: pct + '%' }} /></div>
            <div className="w-t">{waitLabel}</div>
          </div>

          <div className="close">
            <div className="cl-t">
              <div className="cl-h">{PROGRAM.name} {PROGRAM.mascot}</div>
              <div className="cl-s">Established 2026 · Conference {PROGRAM.conference}</div>
            </div>
            <button className="btn">Enter Franchise</button>
          </div>
        </div>

        <button className="replay" onClick={() => setRun(r => r + 1)}>Replay</button>
      </div>
    </>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
