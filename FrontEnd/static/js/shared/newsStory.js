/**
 * Story body for the news drill-in. Same rich_lines and lines the news page rendered.
 * The view supplies the back bar and the headline. Names in a headline stay plain text.
 */

var PLAYER_TABLE_ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
var RETIRED_HEADING = 'Recruiting Leans Announced';

function esc(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatTableHeight(inches) {
  var raw = Number(inches);
  if (!raw || isNaN(raw)) return '--';
  return Math.floor(raw / 12) + "'" + (raw % 12) + '"';
}

function formatTableYear(year) {
  if (window.GOB_PlayerYear && typeof window.GOB_PlayerYear.formatDisplay === 'function') {
    return window.GOB_PlayerYear.formatDisplay(year);
  }
  return year || '--';
}

function renderPlayerTable(players) {
  if (!players || !players.length) return '';
  var tiles = window.GOB_AttrTiles;
  // The twelve attributes read as six pairs (Styleguide › Tables): `gstart` opens a
  // pair, `gend` closes it, and `wt` carries the wider gutter before the first pair.
  var head = '<th class="team">Name</th><th>Pos</th><th>Yr</th><th>Ht</th><th class="wt">Wt</th>';
  PLAYER_TABLE_ATTRS.forEach(function (key, index) {
    var tip = tiles && tiles.ATTR_FULL_NAMES ? (tiles.ATTR_FULL_NAMES[key] || key) : key;
    head += '<th class="' + (index % 2 ? 'gend' : 'gstart') + '" data-tooltip="' + esc(tip) + '"><span class="ak">' + esc(key) + '</span></th>';
  });
  head += '<th>RT</th>';
  var rows = players.map(function (player) {
    var attrs = player.attributes || {};
    var cells = [
      '<td class="team">' + esc(player.name || '--') + '</td>',
      '<td>' + esc(player.pos || '--') + '</td>',
      '<td>' + esc(formatTableYear(player.year)) + '</td>',
      '<td>' + esc(formatTableHeight(player.height)) + '</td>',
      '<td class="wt">' + esc(player.weight == null ? '--' : String(player.weight)) + '</td>'
    ];
    PLAYER_TABLE_ATTRS.forEach(function (key, index) {
      var value = tiles && typeof tiles.tileValue === 'function' ? tiles.tileValue(attrs, key) : null;
      var tile = tiles && typeof tiles.tileHtml === 'function' ? tiles.tileHtml(key, value, false) : esc(value == null ? '--' : value);
      cells.push('<td class="' + (index % 2 ? 'gend' : 'gstart') + '">' + tile + '</td>');
    });
    var rt = player.rt;
    var rtText = rt == null
      ? '--'
      : (typeof formatRtDisplay === 'function' ? formatRtDisplay(rt) : String(rt));
    var rtClass = typeof getRtBucketClass === 'function' ? getRtBucketClass(rt) : '';
    cells.push('<td class="' + esc(rtClass) + '">' + esc(rtText) + '</td>');
    return '<tr>' + cells.join('') + '</tr>';
  });
  return '<div class="gob-xs gob-pairs"><table class="gob-tbl"><thead><tr>' + head + '</tr></thead><tbody>'
    + rows.join('') + '</tbody></table></div>';
}

function userTeamId() {
  var views = window.GOBViews;
  return views && typeof views.userTeamId === 'function' ? String(views.userTeamId() || '') : '';
}

// A team in the shared team style (logo mark and name), linking to its page.
function teamHtml(teamId, name) {
  var tables = window.GOBTables;
  if (!tables || typeof tables.markHtml !== 'function') return esc(name);
  if (teamId && typeof tables.rosterHref === 'function' && typeof tables.teamLink === 'function') {
    return tables.teamLink(tables.rosterHref('', teamId, name, 'news-view'), name, name, '');
  }
  return '<span class="gob-team">' + tables.markHtml(name, '') + '<span>' + esc(name) + '</span></span>';
}

// Rank movement since last week, stored with the story: "▲3", "▼2", "NEW", or nothing
// when unchanged. Neutral both ways, the Office's rank-movement treatment.
function moveHtml(row) {
  if (row.new === true) return '<span class="gob-news-mv is-new">NEW</span>';
  var n = Number(row.move);
  if (row.move == null || !isFinite(n) || n === 0) return '<span class="gob-news-mv"></span>';
  return '<span class="gob-news-mv' + (n < 0 ? ' dn' : '') + '">' + (n < 0 ? '▼' : '▲') + Math.abs(n) + '</span>';
}

function hasMovement(rows) {
  return (rows || []).some(function (row) { return row && (row.new === true || row.move != null); });
}

function rankingRowHtml(row, opts, foot) {
  var mine = opts.userId && String(row.team_id || '') === opts.userId;
  var cls = (mine ? 'me is-user' : '') + (foot ? (mine ? ' ' : '') + 'is-foot' : '');
  var name = row.team || row.team_id || '--';
  return '<tr' + (cls ? ' class="' + cls + '"' : '') + '>'
    + '<td class="rk"><span class="gob-news-rkn">' + esc(row.rank == null ? '--' : String(row.rank)) + '</span>'
    + (opts.moves ? moveHtml(row) : '') + '</td>'
    + '<td class="team">' + (row.team_id ? teamHtml(String(row.team_id), name) : esc(name)) + '</td>'
    + '<td>' + esc(row.score == null ? '--' : String(row.score)) + '</td></tr>';
}

function renderRankingTableSingle(columns, rows, opts, footRow) {
  if ((!rows || !rows.length) && !footRow) return '';
  var cols = (columns && columns.length) ? columns : ['Rank', 'Team', 'Score'];
  var head = cols.map(function (label, idx) {
    return '<th' + (idx === 0 ? ' class="rk"' : (idx === 1 ? ' class="team"' : '')) + '>' + esc(label) + '</th>';
  }).join('');
  var body = (rows || []).map(function (row) { return rankingRowHtml(row, opts, false); }).join('');
  if (footRow) body += rankingRowHtml(footRow, opts, true);
  return '<table class="gob-tbl gob-news-rank-tbl' + (opts.moves ? ' has-moves' : '') + '"><thead><tr>' + head
    + '</tr></thead><tbody>' + body + '</tbody></table>';
}

/**
 * `ranking_table`. Team rows are team links and the user's team is the navy "yours"
 * row. `user_row` (the user's team when it is outside the table) sits at the foot, with
 * its real rank. A table with any stored movement shows the marks beside the rank; a
 * story stored without movement shows none.
 */
function renderRankingTable(item) {
  var rows = item.rows || [];
  var foot = item.user_row && typeof item.user_row === 'object' ? item.user_row : null;
  var opts = { userId: userTeamId(), moves: hasMovement(foot ? rows.concat([foot]) : rows) };
  var split = Array.isArray(item.column_split) ? item.column_split : null;
  var leftCount = split && split.length >= 1 ? Number(split[0]) : 0;
  if (!leftCount || leftCount >= rows.length) return renderRankingTableSingle(item.columns, rows, opts, foot);
  return '<div class="gob-news-split">'
    + renderRankingTableSingle(item.columns, rows.slice(0, leftCount), opts, null)
    + renderRankingTableSingle(item.columns, rows.slice(leftCount), opts, foot)
    + '</div>';
}

/**
 * `team_recruits`: one team and the recruits who leaned to it (Recruiting Report ›
 * Conference Lean Announcements). The team is the sub-heading: logo mark and name in the
 * shared team style, linking to the team page. Its recruits are a list under it, one per
 * row, name then RT in the canonical ramp. No story links a recruit, so names are text.
 */
function renderTeamRecruits(item) {
  var team = teamHtml(item.team_id, item.team_name || '');
  var rows = (item.recruits || []).map(function (recruit) {
    var rt = recruit ? recruit.rt : null;
    var known = typeof rt === 'number' && isFinite(rt);
    var rtText = !known ? '--' : (typeof formatRtDisplay === 'function' ? formatRtDisplay(rt) : String(rt));
    var rtClass = known && typeof getRtBucketClass === 'function' ? getRtBucketClass(rt) : '';
    return '<li><span class="gob-news-recruit">' + esc((recruit && recruit.name) || '--') + '</span>'
      + '<span class="gob-news-rt' + (rtClass ? ' ' + esc(rtClass) : '') + '">' + esc(rtText) + '</span></li>';
  }).join('');
  return '<section class="gob-news-team"><h4 class="gob-news-sub gob-news-team-h">' + team + '</h4>'
    + (rows ? '<ul class="gob-news-recruits">' + rows + '</ul>' : '') + '</section>';
}

// A section heading and, with `level: 2`, a sub-section heading: the app's heading
// styles (Styleguide › Type: heading-col and heading-card), not bold body text.
function headingHtml(item) {
  if (Number(item.level) === 2) return '<h4 class="gob-news-sub">' + esc(item.text) + '</h4>';
  return '<h3 class="gob-news-heading">' + esc(item.text) + '</h3>';
}

function isRankHeading(lines, index) {
  var item = lines[index];
  var next = lines[index + 1];
  return !!(item && item.type === 'heading' && item.text !== RETIRED_HEADING
    && next && next.type === 'ranking_table');
}

// A heading, the quiet caption that says what Score is, and its table.
function rankSectionHtml(heading, table) {
  return '<section class="gob-news-rank">' + headingHtml(heading)
    + (table.caption ? '<p class="gob-news-caption">' + esc(table.caption) + '</p>' : '')
    + renderRankingTable(table) + '</section>';
}

function renderLine(item) {
  var type = item.type || 'text';
  if (type === 'gap') return '<div class="gob-news-gap"></div>';
  if (type === 'heading') {
    // A Recruiting Report stored before the lean section became team blocks carries
    // this outer heading over its two sub-headings. It is redundant: not drawn.
    if (item.text === RETIRED_HEADING) return '';
    return headingHtml(item);
  }
  if (type === 'link') {
    return '<p class="gob-news-line"><a class="gob-news-link" href="' + esc(item.href) + '">' + esc(item.label) + '</a></p>';
  }
  if (type === 'team_roster') {
    return '<p class="gob-news-line"><a class="gob-news-link" href="' + esc(item.href) + '">' + esc(item.label) + '</a></p>'
      + '<p class="gob-news-line">' + esc(item.players_line) + '</p>';
  }
  if (type === 'team_recruits') return renderTeamRecruits(item);
  if (type === 'player_table') return renderPlayerTable(item.players || []);
  if (type === 'ranking_table') return renderRankingTable(item);
  if (type === 'game_result') {
    var line = esc(item.text);
    if (item.box_score_href) {
      line += ' <a class="lnk" href="' + esc(item.box_score_href) + '">Box Score</a>';
    }
    return '<p class="gob-news-line">' + line + '</p>';
  }
  return '<p class="gob-news-line">' + esc(item.text || '') + '</p>';
}

/**
 * The story's lines, in order. Ranking tables that follow one another (National, then
 * the Region) are one `.gob-news-ranks` group: stacked, and side by side from 1600px.
 */
export function renderRichLines(richLines) {
  if (!richLines || !richLines.length) return '';
  var html = '';
  var index = 0;
  while (index < richLines.length) {
    if (!isRankHeading(richLines, index)) {
      html += renderLine(richLines[index]);
      index += 1;
      continue;
    }
    var sections = '';
    var count = 0;
    while (isRankHeading(richLines, index)) {
      sections += rankSectionHtml(richLines[index], richLines[index + 1]);
      count += 1;
      index += 2;
      // The gap between two ranking sections belongs to the group's own spacing.
      if (richLines[index] && richLines[index].type === 'gap' && isRankHeading(richLines, index + 1)) index += 1;
    }
    html += '<div class="gob-news-ranks' + (count > 1 ? ' is-pair' : '') + '">' + sections + '</div>';
  }
  return html;
}

/** True when the story has ranking tables: the page gives it the wide measure. */
export function storyIsWide(story) {
  return !!(story && (story.rich_lines || []).some(function (line) {
    return line && line.type === 'ranking_table';
  }));
}

export function renderStoryBody(story) {
  if (!story) return '';
  if (story.rich_lines && story.rich_lines.length) return renderRichLines(story.rich_lines);
  return (story.lines || []).map(function (line) {
    if (!String(line == null ? '' : line).trim()) return '<div class="gob-news-gap"></div>';
    return '<p class="gob-news-line">' + esc(line) + '</p>';
  }).join('');
}
