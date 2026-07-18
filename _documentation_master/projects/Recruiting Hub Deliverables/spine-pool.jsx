/* Pool — collapsible region sections, sortable, filterable, RT-colored.
   window.SpinePool = { Pool } */
(function () {
  const { useState, useMemo } = React;
  const { ATTR_KEYS, REGIONS, REGION_NAMES, TEAM_NAME } = window.SpineData;
  const { LeanObject } = window.SpineLean;

  const SORTS = { name: 'text', pos: 'text', year: 'text', height: 'num', weight: 'num', rt: 'num' };
  const attrCls = v => v >= 6 ? 'attr-hi' : v >= 4 ? 'attr-mid' : v >= 2 ? 'attr-lo' : 'attr-zero';

  const Chevron = () => (
    <svg className="region-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6"></path></svg>
  );

  function RecRow({ rec, variant, condensed }) {
    const rowCls = rec.yourRank === 1 ? 'mine' : rec.yourRank > 1 ? 'list-mine' : '';
    return (
      <tr className={`rec ${rowCls}`}>
        <td className="name-col">
          <div className="pc-name">
            <span className="nm">{rec.name}</span>
            {rec.newLean && <span className="flag new">New</span>}
            {rec.lost && <span className="flag lost">Lost</span>}
          </div>
          <div className="pc-arch">{rec.archetype}</div>
        </td>
        <td className="pos">{rec.pos}</td>
        <td className="year">{rec.year}</td>
        <td className="num">{rec.height}</td>
        <td className="num">{rec.weight}</td>
        {ATTR_KEYS.map((k, i) => (
          <td key={k} className={`attr ${attrCls(rec[k])} ${i === 0 ? 'attr-sep' : ''}`}>{rec[k]}</td>
        ))}
        <td className="rt attr-sep"><span className={`v rt-${rec.rtTier}`}>{rec.rt}</span></td>
        <td className="lean-col"><LeanObject rec={rec} variant={variant} /></td>
      </tr>
    );
  }

  function Pool({ recruits, variant, condensed, showFilters = true }) {
    const [search, setSearch] = useState('');
    const [region, setRegion] = useState('all');
    const [mineOnly, setMineOnly] = useState(false);
    const [sort, setSort] = useState({ key: 'rt', dir: 'desc' });
    const [collapsed, setCollapsed] = useState({});

    const filtered = useMemo(() => recruits.filter(r => {
      if (region !== 'all' && r.region !== region) return false;
      if (mineOnly && !r.leansToUser) return false;
      if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    }), [recruits, region, mineOnly, search]);

    const groups = useMemo(() => {
      const by = {};
      filtered.forEach(r => { (by[r.region] = by[r.region] || []).push(r); });
      const cmp = (a, b) => {
        const t = SORTS[sort.key];
        const av = a[sort.key], bv = b[sort.key];
        if (t === 'num') return sort.dir === 'asc' ? av - bv : bv - av;
        return sort.dir === 'asc' ? String(av).localeCompare(bv) : String(bv).localeCompare(av);
      };
      return REGIONS.filter(r => by[r]).map(r => ({ region: r, recs: by[r].sort(cmp) }));
    }, [filtered, sort]);

    const setSortKey = k => { if (!SORTS[k]) return; setSort(s => s.key === k ? { key: k, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key: k, dir: k === 'name' || k === 'pos' || k === 'year' ? 'asc' : 'desc' }); };
    const arrow = k => sort.key === k ? <span className="arrow">{sort.dir === 'asc' ? '▲' : '▼'}</span> : null;

    const th = (k, label, cls = 'num') => <th className={cls} onClick={() => setSortKey(k)}>{label}{arrow(k)}</th>;
    const attrColCount = 5 + ATTR_KEYS.length + 2; // for region row colspan

    return (
      <div className="pool-wrap">
        {showFilters && (
          <div className="pool-toolbar">
            <div className="ptb-group">
              <span className="ptb-label">Find</span>
              <input className="ptb-search" placeholder="Name…" value={search} onChange={e => setSearch(e.target.value)} />
            </div>
            <div className="ptb-group">
              <span className="ptb-label">Region</span>
              <button className={`chip ${region === 'all' ? 'is-active' : ''}`} onClick={() => setRegion('all')}>All</button>
              {REGIONS.map(r => <button key={r} className={`chip ${region === r ? 'is-active' : ''}`} onClick={() => setRegion(r)}>{r}</button>)}
            </div>
            <button className={`chip mine ${mineOnly ? 'is-active' : ''}`} onClick={() => setMineOnly(m => !m)}>◗ Leaning to me</button>
            <span className="ptb-count">Showing <strong>{filtered.length}</strong> of {recruits.length}</span>
          </div>
        )}
        <div className="pool-scroll">
          <table className={`pool ${condensed ? 'condensed' : ''}`}>
            <thead>
              <tr>
                {th('name', 'Name', 'name-col')}
                {th('pos', 'Pos')}
                {th('year', 'Yr')}
                {th('height', 'Ht')}
                {th('weight', 'Wt')}
                {ATTR_KEYS.map((k, i) => <th key={k} className={`num attr-col ${i === 0 ? 'attr-sep' : ''}`} onClick={() => {}}>{k}</th>)}
                <th className="num attr-sep" onClick={() => setSortKey('rt')}>RT{arrow('rt')}</th>
                <th className="lean-col">Leans / Your Standing</th>
              </tr>
            </thead>
            <tbody>
              {groups.map(g => {
                const isCol = collapsed[g.region];
                const mineCount = g.recs.filter(r => r.leansToUser).length;
                return (
                  <React.Fragment key={g.region}>
                    <tr className="region-row">
                      <td colSpan={attrColCount}>
                        <button className={`region-bar ${isCol ? 'region-collapsed' : ''}`} onClick={() => setCollapsed(c => ({ ...c, [g.region]: !c[g.region] }))}>
                          <Chevron />
                          <span className="region-letter">{g.region}</span>
                          <span className="region-name">{REGION_NAMES[g.region]}</span>
                          <span className="region-stat"><b>{g.recs.length}</b> recruits</span>
                          {mineCount > 0 && <span className="region-mine"><span className="d"></span>{mineCount} leaning to you</span>}
                        </button>
                      </td>
                    </tr>
                    {!isCol && g.recs.map(r => <RecRow key={r.id} rec={r} variant={variant} condensed={condensed} />)}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  window.SpinePool = { Pool };
})();
