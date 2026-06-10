/**
 * Shared franchise tournament bracket DOM (FCC Tournament tab + brackets.html).
 * Depends: fcc-tournament-style-a.js (Style A renderer).
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
      seeds: rt.seeds || {},
    };
  }

  function createBracketSection(
    sectionTitle,
    bracketPayload,
    layout,
    teamIdToNameMap,
    userTeamId,
    teamIdMetaMap,
    topData,
    fccMode,
    tierHint
  ) {
    if (!bracketPayload || !bracketPayload.bracket) return null;

    const resolvedTier = tierHint || (typeof FccTournamentStyleA !== 'undefined' && FccTournamentStyleA.inferTier
      ? FccTournamentStyleA.inferTier(sectionTitle)
      : 'conference');

    const section = document.createElement('section');
    section.className = 'fcc-tournament-section fcc-tb-tier';
    section.setAttribute('data-tb-tier', resolvedTier);

    const heading = document.createElement('h4');
    heading.className = 'fcc-tournament-section-title fcc-tb-tier-title';
    heading.textContent = sectionTitle;
    section.appendChild(heading);

    const bracketRoot = document.createElement('div');
    bracketRoot.className = 'fcc-tb-tier-body';
    section.appendChild(bracketRoot);

    if (typeof FccTournamentStyleA !== 'undefined' && FccTournamentStyleA.renderInto) {
      FccTournamentStyleA.renderInto(bracketRoot, {
        sectionTitle: sectionTitle,
        layout: layout || 'full',
        bracket: bracketPayload.bracket || {},
        seeds: bracketPayload.seeds || {},
        teamIdToNameMap: teamIdToNameMap,
        userTeamId: userTeamId,
        teamIdMetaMap: teamIdMetaMap,
        topData: topData || {},
        allBrackets: fccMode === 'all',
        tierHint: tierHint || null,
      });
    } else {
      bracketRoot.innerHTML = '<p class="fcc-tournament-empty-msg">Tournament bracket UI not loaded.</p>';
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

    const tierOrder = { national: 0, region: 1, conference: 2 };
    const entries = [];

    if (nationalTournament && nationalTournament.bracket) {
      entries.push({
        tier: 'national',
        title: 'National Tournament',
        payload: nationalTournament,
        layout: 'full',
      });
    }
    if (regionTournament && regionTournament.bracket) {
      entries.push({
        tier: 'region',
        title: 'Region Tournament',
        payload: regionTournament,
        layout: 'compact4',
      });
    }
    if (conferenceTournament && conferenceTournament.bracket) {
      entries.push({
        tier: 'conference',
        title: 'Conference Tournament',
        payload: conferenceTournament,
        layout: 'full',
      });
    }

    if (!entries.length && eosTournament) {
      let tournamentTitle = 'End-of-Season Tournament';
      if (week >= 27 && week <= 29) tournamentTitle = 'Conference Tournament';
      else if (week >= 30 && week <= 31) tournamentTitle = 'Region Tournament';
      else if (week >= 32 && week <= 36) tournamentTitle = 'National Tournament';
      const eosTier = week >= 32 ? 'national' : week >= 30 ? 'region' : 'conference';
      entries.push({
        tier: eosTier,
        title: tournamentTitle,
        payload: eosTournament,
        layout: week >= 30 && week <= 31 ? 'compact4' : 'full',
      });
    }

    entries.sort(function (a, b) {
      return (tierOrder[a.tier] != null ? tierOrder[a.tier] : 9) - (tierOrder[b.tier] != null ? tierOrder[b.tier] : 9);
    });

    return entries
      .map(function (entry) {
        return createBracketSection(
          entry.title,
          entry.payload,
          entry.layout,
          teamIdToNameMap,
          userTeamId,
          teamIdMetaMap,
          topData,
          'fcc',
          entry.tier
        );
      })
      .filter(Boolean);
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
          teamIdToNameMap,
          userTeamId,
          teamIdMetaMap,
          topData,
          'all',
          'national'
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
              teamIdToNameMap,
              userTeamId,
              teamIdMetaMap,
              topData,
              'all',
              'region'
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
              teamIdToNameMap,
              userTeamId,
              teamIdMetaMap,
              topData,
              'all',
              'conference'
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
