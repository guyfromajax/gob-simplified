(function() {
  // Retired. Browse pages used to keep a season+week copy that ignored browse_rev.
  // Callers still call get/set; get always misses so the request goes through
  // gobStore, which revalidates the ETag and drops the franchise on a new rev.
  function createResourceCache() {
    function key(scopeKey) {
      return String(scopeKey || 'default');
    }

    function get() {
      return null;
    }

    function set(_scopeKey, value) {
      return value;
    }

    return { get, set, key };
  }

  window.ResourceCache = { createResourceCache };
})();
