(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.InsightFlow = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  var state = {
    apiKey: null,
    apiHost: 'https://api.insightflow.ai',
    queue: [],
    initialized: false,
    userId: null,
  };

  function generateId() {
    return 'if_' + Date.now().toString(36) + '_' + Math.random().toString(36).substr(2, 9);
  }

  function getUserId() {
    if (state.userId) return state.userId;
    try {
      var stored = localStorage.getItem('if_user_id');
      if (stored) {
        state.userId = stored;
        return stored;
      }
    } catch (e) {}
    var id = generateId();
    state.userId = id;
    try { localStorage.setItem('if_user_id', id); } catch (e) {}
    return id;
  }

  function send(eventName, properties) {
    var payload = JSON.stringify({
      api_key: state.apiKey,
      event: eventName,
      properties: properties || {},
      user_id: getUserId(),
      timestamp: new Date().toISOString(),
    });

    var url = state.apiHost + '/api/v1/track/';

    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      navigator.sendBeacon(url, payload);
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', url, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(payload);
    }
  }

  function flush() {
    while (state.queue.length) {
      var item = state.queue.shift();
      send(item.event, item.properties);
    }
  }

  return {
    init: function (apiKey, options) {
      if (!apiKey) {
        console.error('[InsightFlow] API key is required');
        return;
      }
      state.apiKey = apiKey;
      if (options) {
        if (options.apiHost) state.apiHost = options.apiHost;
        if (options.userId) state.userId = options.userId;
      }
      state.initialized = true;
      flush();

      if (typeof document !== 'undefined') {
        document.addEventListener('DOMContentLoaded', function () {
          send('$pageview', { url: location.href, referrer: document.referrer });
        });
      }
    },

    track: function (eventName, properties) {
      if (!eventName) {
        console.error('[InsightFlow] Event name is required');
        return;
      }
      if (!state.initialized) {
        state.queue.push({ event: eventName, properties: properties || {} });
        return;
      }
      send(eventName, properties || {});
    },

    identify: function (userId) {
      state.userId = userId;
      try { localStorage.setItem('if_user_id', userId); } catch (e) {}
    },

    page: function (name, properties) {
      this.track('$pageview', Object.assign({ page: name || location.pathname }, properties || {}));
    },
  };
}));
