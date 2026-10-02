/**
 * Story body for the news drill-in. Same rich_lines and lines the news page rendered.
 * The view supplies the back bar and the headline. Names in a headline stay plain text.
 */

var PLAYER_TABLE_ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];

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

function renderRankingTableSingle(columns, rows) {
  if (!rows || !rows.length) return '';
  var cols = (columns && columns.length) ? columns : ['Rank', 'Team', 'Score'];
  var head = cols.map(function (label, idx) {
    return '<th' + (idx === 1 ? ' class="team"' : '') + '>' + esc(label) + '</th>';
  }).join('');
  var body = rows.map(function (row) {
    return '<tr><td>' + esc(row.rank == null ? '--' : String(row.rank)) + '</td>'
      + '<td class="team">' + esc(row.team || row.team_id || '--') + '</td>'
      + '<td>' + esc(row.score == null ? '--' : String(row.score)) + '</td></tr>';
  }).join('');
  return '<table class="gob-tbl"><thead><tr>' + head + '</tr></thead><tbody>'
    + body + '</tbody></table>';
}

function renderRankingTable(columns, rows, columnSplit) {
  if (!rows || !rows.length) return '';
  var split = Array.isArray(columnSplit) ? columnSplit : null;
  var leftCount = split && split.length >= 1 ? Number(split[0]) : 0;
  if (!leftCount || leftCount >= rows.length) return renderRankingTableSingle(columns, rows);
  return '<div class="gob-news-split">'
    + renderRankingTableSingle(columns, rows.slice(0, leftCount))
    + renderRankingTableSingle(columns, rows.slice(leftCount))
    + '</div>';
}

export function renderRichLines(richLines) {
  if (!richLines || !richLines.length) return '';
  return richLines.map(function (item) {
    var type = item.type || 'text';
    if (type === 'gap') return '<div class="gob-news-gap"></div>';
    if (type === 'heading') {
      return '<p class="gob-news-line gob-news-heading"><strong>' + esc(item.text) + '</strong></p>';
    }
    if (type === 'link') {
      return '<p class="gob-news-line"><a class="gob-news-link" href="' + esc(item.href) + '">' + esc(item.label) + '</a></p>';
    }
    if (type === 'team_roster') {
      return '<p class="gob-news-line"><a class="gob-news-link" href="' + esc(item.href) + '">' + esc(item.label) + '</a></p>'
        + '<p class="gob-news-line">' + esc(item.players_line) + '</p>';
    }
    if (type === 'player_table') return renderPlayerTable(item.players || []);
    if (type === 'ranking_table') return renderRankingTable(item.columns || [], item.rows || [], item.column_split);
    if (type === 'game_result') {
      var line = esc(item.text);
      if (item.box_score_href) {
        line += ' <a class="lnk" href="' + esc(item.box_score_href) + '">Box Score</a>';
      }
      return '<p class="gob-news-line">' + line + '</p>';
    }
    return '<p class="gob-news-line">' + esc(item.text || '') + '</p>';
  }).join('');
}

export function renderStoryBody(story) {
  if (!story) return '';
  if (story.rich_lines && story.rich_lines.length) return renderRichLines(story.rich_lines);
  return (story.lines || []).map(function (line) {
    if (!String(line == null ? '' : line).trim()) return '<div class="gob-news-gap"></div>';
    return '<p class="gob-news-line">' + esc(line) + '</p>';
  }).join('');
}
