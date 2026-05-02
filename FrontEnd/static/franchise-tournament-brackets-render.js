/**
 * Shared franchise tournament bracket DOM (FCC Tournament tab + brackets.html).
 * Depends: bracket.js (renderBracketShared), getTeamAssetPath from common.js (optional).
 */
(function (global) {
  'use strict';

  function normalizeRegionBracket(rt) {
    if (!rt) return null;
    const finalList = rt.final || [];
    return {
      bracket: {
        round1: rt.round1 || [],
        round2: [],
        final: finalList,
      },
      seeds: {},
    };
  }

  function createBracketSection(sectionTitle, bracketPayload, layout, toneClass, teamIdToNameMap, userTeamId, teamIdMetaMap) {
    if (!bracketPayload || !bracketPayload.bracket) return null;

    const section = document.createElement('section');
    section.className = `fcc-tournament-section ${toneClass || ''}`.trim();

    const heading = document.createElement('h4');
    heading.className = 'fcc-tournament-section-title';
    heading.textContent = sectionTitle;
    section.appendChild(heading);

    const bracketRoot = document.createElement('div');
    bracketRoot.className = 'bracket';
    section.appendChild(bracketRoot);

    if (typeof renderBracketShared === 'function') {
      renderBracketShared(bracketRoot, bracketPayload.bracket || {}, teamIdToNameMap, {
        seeds: bracketPayload.seeds || {},
        layout: layout || 'full',
        getLogo: function (name) {
          return typeof getTeamAssetPath === 'function'
            ? getTeamAssetPath(name, 'banner_primary')
            : '/images/teams/general/general_banner_primary.jpg';
        },
        isUserTeam: function (id) {
          return userTeamId != null && String(id) === String(userTeamId);
        },
        getTooltip: function (id, name) {
          const meta = teamIdMetaMap[String(id)] || {};
          const teamName = meta.team || name || '';
          const mascot = meta.mascot || '';
          if (!teamName) return '';
          return mascot ? `${teamName} ${mascot}` : teamName;
        },
      });
    } else {
      bracketRoot.innerHTML = '<p>Bracket renderer not loaded.</p>';
    }

    return section;
  }

  /** Mirrors FCC `hasBracketHistory`: user-relevant tournaments or derived eos payload. */
  function hasFccBracketHistory(topData) {
    if (!topData) return false;
    if (topData.eos_tournament) return true;
    if (topData.national_tournament) return true;
    const uc = topData.user_conference != null ? String(topData.user_conference) : '';
    const ur = String(topData.user_region || '').toUpperCase();
    if (uc && (topData.conference_tournaments || {})[uc]) return true;
    if (ur && (topData.region_tournaments || {})[ur]) return true;
    return false;
  }

  function buildFccSections(topData, userTeamId, teamIdToNameMap, teamIdMetaMap) {
    const week = Number(topData?.week || 0);
    const userConference = topData?.user_conference != null ? String(topData.user_conference) : '';
    const userRegion = String(topData?.user_region || '').toUpperCase();
    const conferenceTournament = userConference ? (topData?.conference_tournaments || {})[userConference] : null;
    const regionTournamentRaw = userRegion ? (topData?.region_tournaments || {})[userRegion] : null;
    const regionTournament = regionTournamentRaw ? normalizeRegionBracket(regionTournamentRaw) : null;
    const nationalTournament = topData?.national_tournament || null;
    const eosTournament = topData?.eos_tournament;

    if (!hasFccBracketHistory(topData)) {
      return [];
    }

    let tournamentTitle = 'End-of-Season Tournament';
    if (week >= 27 && week <= 29) {
      tournamentTitle = 'Conference Tournament';
    } else if (week >= 30 && week <= 31) {
      tournamentTitle = 'Region Tournament';
    } else if (week >= 32 && week <= 36) {
      tournamentTitle = 'National Tournament';
    }

    const sections = [];
    if (week >= 27 && week <= 29 && conferenceTournament) {
      sections.push(
        createBracketSection(
          'Conference Tournament',
          conferenceTournament,
          'full',
          'fcc-tournament-tone-conference',
          teamIdToNameMap,
          userTeamId,
          teamIdMetaMap
        )
      );
    } else if (week >= 30 && week <= 31) {
      if (regionTournament) {
        sections.push(
          createBracketSection(
            'Region Tournament',
            regionTournament,
            'compact4',
            'fcc-tournament-tone-region',
            teamIdToNameMap,
            userTeamId,
            teamIdMetaMap
          )
        );
      }
      if (conferenceTournament) {
        sections.push(
          createBracketSection(
            'Conference Tournament',
            conferenceTournament,
            'full',
            'fcc-tournament-tone-conference',
            teamIdToNameMap,
            userTeamId,
            teamIdMetaMap
          )
        );
      }
    } else if (week >= 32 && week <= 36) {
      if (nationalTournament) {
        sections.push(
          createBracketSection(
            'National Tournament',
            nationalTournament,
            'full',
            'fcc-tournament-tone-national',
            teamIdToNameMap,
            userTeamId,
            teamIdMetaMap
          )
        );
      }
      if (regionTournament) {
        sections.push(
          createBracketSection(
            'Region Tournament',
            regionTournament,
            'compact4',
            'fcc-tournament-tone-region',
            teamIdToNameMap,
            userTeamId,
            teamIdMetaMap
          )
        );
      }
      if (conferenceTournament) {
        sections.push(
          createBracketSection(
            'Conference Tournament',
            conferenceTournament,
            'full',
            'fcc-tournament-tone-conference',
            teamIdToNameMap,
            userTeamId,
            teamIdMetaMap
          )
        );
      }
    } else if (eosTournament) {
      sections.push(
        createBracketSection(
          tournamentTitle,
          eosTournament,
          week >= 30 && week <= 31 ? 'compact4' : 'full',
          'fcc-tournament-tone-conference',
          teamIdToNameMap,
          userTeamId,
          teamIdMetaMap
        )
      );
    }

    return sections.filter(Boolean);
  }

  function buildAllSections(topData, userTeamId, teamIdToNameMap, teamIdMetaMap) {
    const sections = [];
    const nat = topData?.national_tournament;
    if (nat && nat.bracket) {
      sections.push(
        createBracketSection(
          'National Tournament',
          nat,
          'full',
          'fcc-tournament-tone-national',
          teamIdToNameMap,
          userTeamId,
          teamIdMetaMap
        )
      );
    }
    const regionMap = topData?.region_tournaments || {};
    Object.keys(regionMap)
      .sort()
      .forEach(function (regionKey) {
        const normalized = normalizeRegionBracket(regionMap[regionKey]);
        if (normalized && normalized.bracket) {
          sections.push(
            createBracketSection(
              `Region ${regionKey} Tournament`,
              normalized,
              'compact4',
              'fcc-tournament-tone-region',
              teamIdToNameMap,
              userTeamId,
              teamIdMetaMap
            )
          );
        }
      });
    const confMap = topData?.conference_tournaments || {};
    Object.keys(confMap)
      .sort(function (a, b) {
        return Number(a) - Number(b);
      })
      .forEach(function (ck) {
        const ct = confMap[ck];
        if (ct && ct.bracket) {
          sections.push(
            createBracketSection(
              `Conference ${ck} Tournament`,
              ct,
              'full',
              'fcc-tournament-tone-conference',
              teamIdToNameMap,
              userTeamId,
              teamIdMetaMap
            )
          );
        }
      });
    return sections.filter(Boolean);
  }

  function appendSectionsToContainer(container, renderedSections) {
    renderedSections.forEach(function (section, index) {
      if (index > 0) {
        const divider = document.createElement('hr');
        divider.className = 'fcc-tournament-divider';
        container.appendChild(divider);
      }
      container.appendChild(section);
    });
  }

  /**
   * @param {HTMLElement} container
   * @param {object} topData - /franchise/command-center/data payload
   * @param {{ userTeamId: string|null, teamIdToNameMap: object, teamIdMetaMap: object, mode: 'fcc'|'all', titleEl?: HTMLElement|null }} opts
   */
  function appendFranchiseBracketSections(container, topData, opts) {
    if (!container || !topData) return false;
    const userTeamId = opts.userTeamId;
    const teamIdToNameMap = opts.teamIdToNameMap || {};
    const teamIdMetaMap = opts.teamIdMetaMap || {};
    const mode = opts.mode || 'fcc';
    const titleEl = opts.titleEl || null;

    const week = Number(topData.week || 0);
    let tournamentTitle = 'End-of-Season Tournament';
    if (week >= 27 && week <= 29) tournamentTitle = 'Conference Tournament';
    else if (week >= 30 && week <= 31) tournamentTitle = 'Region Tournament';
    else if (week >= 32 && week <= 36) tournamentTitle = 'National Tournament';
    if (titleEl) titleEl.textContent = tournamentTitle;

    container.innerHTML = '';

    let sections = [];
    if (mode === 'all') {
      sections = buildAllSections(topData, userTeamId, teamIdToNameMap, teamIdMetaMap);
    } else {
      if (!hasFccBracketHistory(topData)) {
        if (titleEl) titleEl.textContent = 'End-of-Season Tournament';
        container.innerHTML = '<p class="fcc-tournament-empty-msg">Tournament bracket not available.</p>';
        return false;
      }
      sections = buildFccSections(topData, userTeamId, teamIdToNameMap, teamIdMetaMap);
    }

    if (!sections.length) {
      if (titleEl) titleEl.textContent = 'End-of-Season Tournament';
      container.innerHTML = '<p class="fcc-tournament-empty-msg">Tournament bracket not available.</p>';
      return false;
    }

    appendSectionsToContainer(container, sections);
    return true;
  }

  global.FranchiseTournamentBrackets = {
    appendFranchiseBracketSections: appendFranchiseBracketSections,
  };
})(typeof window !== 'undefined' ? window : this);
