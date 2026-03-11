(function() {
  function safeParse(raw) {
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.warn('Failed to parse cached resource payload', err);
      return null;
    }
  }

  function createResourceCache(page, franchiseId, season, week) {
    const memory = new Map();

    function key(scopeKey) {
      return ['resource', page, franchiseId || '', season || '', week || '', scopeKey || 'default'].join(':');
    }

    function get(scopeKey) {
      const cacheKey = key(scopeKey);
      if (memory.has(cacheKey)) return memory.get(cacheKey);
      const parsed = safeParse(sessionStorage.getItem(cacheKey));
      if (parsed != null) memory.set(cacheKey, parsed);
      return parsed;
    }

    function set(scopeKey, value) {
      const cacheKey = key(scopeKey);
      memory.set(cacheKey, value);
      try {
        sessionStorage.setItem(cacheKey, JSON.stringify(value));
      } catch (err) {
        console.warn('Failed to cache resource payload', err);
      }
      return value;
    }

    return { get, set, key };
  }

  window.ResourceCache = { createResourceCache };
})();
