/* Training load screen — league news wire. Rotating national-news graphics over a
   quiet "training in progress" pulse. Every card type is reachable from Tweaks. */

const WIRE_DEFAULTS = /*EDITMODE-BEGIN*/{
  "graphic": "auto",
  "duration": 6,
  "transition": "crossfade",
  "phase": "in-season",
  "headshots": "photo",
  "teamArt": "both",
  "pulseSpot": "header",
  "showHeader": true
}/*EDITMODE-END*/;

const D = window.GOBNewsWire;

/* Fixed editorial order. Users typically see only 2–4 cards, so the running order is
   deliberate rather than shuffled: the two team-level graphics open, then the eight
   leaderboards in a stable sequence. */
const IN_SEASON_DECK = ['top10', 'key_games', 'pts', 'treb', 'ast', 'def_pct', 'stl', 'blk', 'tpm', 'fg_pct'];
const PRESEASON_DECK = ['pre_top10', 'marquee'];
const GRAPHIC_LABELS = {
  auto: 'Auto rotate', top10: 'National Top 10', key_games: 'Upcoming Key Games',
  pts: 'Scoring Leaders', treb: 'Rebounding Leaders', ast: 'Assist Leaders',
  def_pct: 'Defense Leaders', stl: 'Steal Leaders', blk: 'Block Leaders',
  tpm: '3PT Leaders', fg_pct: 'FG% Leaders',
  pre_top10: 'Preseason Top 10', marquee: 'Marquee Matchups'
};

function buildDeck(phase) {
  return (phase === 'preseason' ? PRESEASON_DECK : IN_SEASON_DECK).slice();
}

function Banner({ slug }) {
  const [src, setSrc] = React.useState(D.bannerArt(slug));
  React.useEffect(() => { setSrc(D.bannerArt(slug)); }, [slug]);
  return <img className="wr-bnr" src={src} alt=""
    onError={() => { if (src !== D.BANNER_FALLBACK) setSrc(D.BANNER_FALLBACK); }} />;
}

function Headshot({ id, slug, mode }) {
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => { setFailed(false); }, [id]);
  if (mode === 'none') return null;
  if (mode === 'team') return <Banner slug={slug} />;
  const showPhoto = mode === 'photo' && !failed;
  return (
    <span className="wr-hs">
      {showPhoto
        ? <img src={D.headshotUrl(id)} alt="" onError={() => setFailed(true)} />
        : <svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="14.5" r="7.2" /><path d="M5.5 40c0-8.2 6.5-13.4 14.5-13.4S34.5 31.8 34.5 40z" /></svg>}
    </span>
  );
}

function Rows({ children }) { return <div className="wr-col">{children}</div>; }

function Split({ items, render }) {
  return (
    <div className="wr-cols">
      <Rows>{items.slice(0, 5).map(render)}</Rows>
      <Rows>{items.slice(5, 10).map(render)}</Rows>
    </div>
  );
}

function TeamRow({ row, trailing, teamArt }) {
  return (
    <div className={'wr-row wr-row-team' + (teamArt === 'both' ? ' is-both' : '')} key={row.rank}>
      <span className="wr-rk">{row.rank}</span>
      <span className="wr-idy">
        <Banner slug={row.team_slug} />
        {teamArt === 'both' ? (
          <span className="wr-tid">
            <b>{row.team_name}</b>
            <em>Region {row.region} · Conference {row.conference}</em>
          </span>
        ) : null}
      </span>
      <span className="wr-rec">{trailing}</span>
    </div>
  );
}

function GameRow({ g }) {
  return (
    <div className="wr-row wr-row-game" key={g.away_slug + g.home_slug}>
      <span className="wr-seed">#{g.away_rank}</span>
      <Banner slug={g.away_slug} />
      <span className="wr-at">@</span>
      <Banner slug={g.home_slug} />
      <span className="wr-seed">#{g.home_rank}</span>
    </div>
  );
}

function PlayerRow({ p, headshots }) {
  const mod = headshots === 'none' ? ' is-flat' : (headshots === 'team' ? ' is-team' : '');
  return (
    <div className={'wr-row wr-row-plr' + mod} key={p.player_id}>
      <span className="wr-rk">{p.rank}</span>
      <Headshot id={p.player_id} slug={p.team_slug} mode={headshots} />
      <span className="wr-plr">
        <b>{p.name}</b>
        {headshots === 'team' ? null : <em>{p.team_name}</em>}
      </span>
      <span className="wr-val">{p.display}</span>
    </div>
  );
}

function cardFor(id, t) {
  const wk = D.week;
  if (id === 'top10') return {
    kicker: 'League standings · through week ' + wk, title: 'National Top 10',
    body: <Split items={D.top10} render={(r) => <TeamRow key={r.rank} row={r} teamArt={t.teamArt} trailing={r.wins + '-' + r.losses} />} />
  };
  if (id === 'key_games') return {
    kicker: 'Week ' + (wk + 1) + ' · ranked by combined national rank', title: 'Upcoming Key Games',
    body: <Split items={D.key_games} render={(g) => <GameRow key={g.away_slug + g.home_slug} g={g} />} />
  };
  if (id === 'pre_top10') return {
    kicker: 'Preseason edition · projected by program rank', title: 'Preseason Top 10',
    body: <Split items={D.preseason.top10} render={(r) => <TeamRow key={r.rank} row={r} teamArt={t.teamArt} trailing={r.last_record} />} />
  };
  if (id === 'marquee') return {
    kicker: 'Preseason edition · the season’s ten biggest games', title: 'Marquee Matchups',
    body: <Split items={D.preseason.marquee} render={(g) => <GameRow key={g.week + g.away_slug} g={g} />} />
  };
  const b = D.leaders[id];
  return {
    kicker: b.kicker.replace('{W}', wk), title: b.title,
    body: <Split items={b.rows} render={(p) => <PlayerRow key={p.player_id} p={p} headshots={t.headshots} />} />
  };
}

function Pulse({ compact }) {
  return (
    <div className={'wr-pulse' + (compact ? ' is-compact' : '')}>
      <span className="wr-pulse-bar" aria-hidden="true"><span /></span>
      <span className="wr-pulse-copy">Training in progress</span>
    </div>
  );
}

function App() {
  const [t, setTweak] = useTweaks(WIRE_DEFAULTS);
  const phase = t.phase === 'preseason' ? 'preseason' : 'in_season';
  const manual = t.graphic !== 'auto';
  const dur = Math.max(2000, t.duration * 1000);

  const [deck, setDeck] = React.useState(() => buildDeck(phase));
  const [pos, setPos] = React.useState(0);
  const [leaving, setLeaving] = React.useState(false);
  const [paused, setPaused] = React.useState(false);

  React.useEffect(() => { setDeck(buildDeck(phase)); setPos(0); }, [phase]);

  const id = manual ? t.graphic : deck[((pos % deck.length) + deck.length) % deck.length];

  React.useEffect(() => {
    if (manual || paused) return;
    const fade = t.transition === 'cut' ? 0 : 260;
    const a = window.setTimeout(() => setLeaving(true), Math.max(0, dur - fade));
    const b = window.setTimeout(() => {
      setLeaving(false);
      setPos((p) => p + 1);
    }, dur);
    return () => { window.clearTimeout(a); window.clearTimeout(b); };
  }, [pos, dur, manual, paused, t.transition, deck, phase]);

  React.useEffect(() => {
    function onKey(e) {
      if (e.key === 'ArrowRight') { setLeaving(false); setPos((p) => p + 1); }
      else if (e.key === 'ArrowLeft') { setLeaving(false); setPos((p) => p - 1); }
      else if (e.code === 'Space') { e.preventDefault(); setPaused((v) => !v); }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const card = cardFor(id, t);
  const ctx = phase === 'preseason' ? 'Season ' + D.season + ' · Preseason' : 'Season ' + D.season + ' · Week ' + D.week;

  return (
    <div className="wr-overlay">
      <div className="wr-shell">
        {t.showHeader ? (
          <header className="wr-head">
            <span className="wr-mark">Around the League</span>
            <span className="wr-head-r">
              {t.pulseSpot === 'header' ? <Pulse compact /> : null}
              <span className="wr-ctx">{ctx}</span>
            </span>
          </header>
        ) : null}

        <div className={'wr-stage tr-' + t.transition + (leaving ? ' is-leaving' : '')}>
          <article className="wr-card" key={id + '-' + pos}>
            <p className="wr-kicker">{card.kicker}</p>
            <h2 className="wr-title">{card.title}</h2>
            {card.body}
            {manual || paused ? null : <span className="wr-sweep" style={{ animationDuration: dur + 'ms' }} />}
          </article>
        </div>

        <footer className="wr-foot">
          {t.pulseSpot === 'footer' ? <Pulse /> : <span />}
        </footer>
      </div>
      <span className="wr-hint">← → step · space {paused ? 'resume' : 'pause'}</span>

      <TweaksPanel>
        <TweakSection label="Rotation" />
        <TweakSelect label="Graphic" value={t.graphic}
          options={(t.phase === 'preseason' ? ['auto'].concat(PRESEASON_DECK) : ['auto'].concat(IN_SEASON_DECK)).map((k) => ({ value: k, label: GRAPHIC_LABELS[k] }))}
          onChange={(v) => setTweak('graphic', v)} />
        <TweakSlider label="Seconds per card" value={t.duration} min={3} max={10} step={1} unit="s"
          onChange={(v) => setTweak('duration', v)} />
        <TweakRadio label="Transition" value={t.transition} options={['crossfade', 'slide', 'cut']}
          onChange={(v) => setTweak('transition', v)} />
        <TweakSection label="Content" />
        <TweakRadio label="Season phase" value={t.phase} options={['in-season', 'preseason']}
          onChange={(v) => { setTweak('phase', v); setTweak('graphic', 'auto'); }} />
        <TweakSelect label="Player mark" value={t.headshots}
          options={[{ value: 'photo', label: 'Headshot photo (R2)' }, { value: 'silhouette', label: 'Silhouette fallback' }, { value: 'team', label: 'Team logo instead' }, { value: 'none', label: 'None — name + stat' }]}
          onChange={(v) => setTweak('headshots', v)} />
        <TweakRadio label="Team art" value={t.teamArt} options={['logo', 'both']}
          onChange={(v) => setTweak('teamArt', v)} />
        <TweakSection label="Chrome" />
        <TweakRadio label="Pulse placement" value={t.pulseSpot} options={['footer', 'header']}
          onChange={(v) => setTweak('pulseSpot', v)} />
        <TweakToggle label="Wire header" value={t.showHeader}
          onChange={(v) => setTweak('showHeader', v)} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
