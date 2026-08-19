# InsightFlow SDK

> **Product analytics for your web app in minutes.** Track user events, pageviews, and identities with a lightweight (< 3 KB), dependency-free JavaScript client for [InsightFlow AI](https://insightflow.ai).

[![npm version](https://img.shields.io/npm/v/insightflow-sdk.svg)](https://www.npmjs.com/package/insightflow-sdk)
[![License](https://img.shields.io/npm/l/insightflow-sdk.svg)](https://github.com/your-org/insightflow-sdk/blob/main/LICENSE)
[![npm downloads](https://img.shields.io/npm/dm/insightflow-sdk.svg)](https://www.npmjs.com/package/insightflow-sdk)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
  - [`init(apiKey, options)`](#initapikey-options)
  - [`track(eventName, properties)`](#trackeventname-properties)
  - [`identify(userId)`](#identifyuserid)
  - [`page(name, properties)`](#pagename-properties)
- [Events & Auto-Captured Properties](#events--auto-captured-properties)
- [How It Works](#how-it-works)
- [Browser Support](#browser-support)
- [Privacy & Consent](#privacy--consent)
- [Development](#development)
- [License](#license)

---

## Features

- **Automatic pageview tracking** — fires a `$pageview` event on `DOMContentLoaded`.
- **Zero configuration identity** — generates and persists a stable anonymous `user_id` and `session_id` out of the box.
- **Reliable delivery** — uses `navigator.sendBeacon` with an `XMLHttpRequest` fallback, so events survive page unload.
- **Event buffering** — calls made before `init()` are queued and flushed automatically once initialized.
- **Universal module** — UMD build that works as a plain `<script>`, with CommonJS, or AMD.
- **No dependencies** — vanilla JavaScript, no runtime libraries required.

---

## Installation

### Via npm

```bash
npm install insightflow-sdk
```

Then import it in your app:

```js
// CommonJS / bundlers (Vite, webpack, Rollup, ...)
const InsightFlow = require('insightflow-sdk');

// ES modules
import InsightFlow from 'insightflow-sdk';
```

### Via CDN (jsDelivr)

```html
<script src="https://cdn.jsdelivr.net/npm/insightflow-sdk"></script>
```

The SDK exposes a global `InsightFlow` object.

---

## Quick Start

```html
<script src="https://cdn.jsdelivr.net/npm/insightflow-sdk"></script>
<script>
  InsightFlow.init('YOUR_API_KEY', {
    apiHost: 'https://34.207.37.93.nip.io',
  });

  // Track a custom event
  InsightFlow.track('signup_completed', { plan: 'pro', referrer: 'landing' });

  // Identify the user
  InsightFlow.identify('user_12345');
</script>
```

That's it. Pageviews are tracked automatically, and every event includes your API key, a stable user ID, session ID, and device context.

---

## Configuration

### `init(apiKey, options)`

| Option     | Type     | Default                    | Description                                            |
|------------|----------|----------------------------|--------------------------------------------------------|
| `apiKey`   | `string` | *required*                 | Your project's API key from the InsightFlow dashboard. |
| `apiHost`  | `string` | `https://api.insightflow.ai` | The base URL events are sent to (e.g. self-hosted instance). |
| `userId`   | `string` | auto-generated             | Override the initial user ID instead of using the anonymous one. |

```js
InsightFlow.init('pk_xxxx', {
  apiHost: 'https://analytics.example.com',
  userId: 'existing_user_id',
});
```

---

## API Reference

### `init(apiKey, options)`

Initializes the SDK with your API key and optional configuration. Must be called once before analytics data is sent.

```js
InsightFlow.init('pk_xxxx');
```

- Logs an error and does nothing if `apiKey` is missing.
- Flushes any events queued before initialization.
- Registers automatic `$pageview` tracking on `DOMContentLoaded`.

### `track(eventName, properties)`

Tracks a custom event with optional properties.

```js
InsightFlow.track('button_clicked', { button: 'checkout', page: '/pricing' });
```

| Argument     | Type     | Description                                   |
|--------------|----------|-----------------------------------------------|
| `eventName`  | `string` | Name of the event (e.g. `checkout_started`).  |
| `properties` | `object` | Optional key/value metadata for the event.    |

- Logs an error if `eventName` is missing.
- If called before `init()`, the event is queued and sent once initialized.

### `identify(userId)`

Associates all future events with a known user ID (e.g. after login). Persists to `localStorage`, replacing the anonymous ID.

```js
InsightFlow.identify('user_abc123');
```

### `page(name, properties)`

Tracks a named pageview. Uses `location.pathname` as the page name when none is given.

```js
InsightFlow.page('Pricing');
InsightFlow.page('Dashboard', { role: 'admin' });
```

---

## Events & Auto-Captured Properties

Every event payload sent to `POST {apiHost}/api/v1/track/` includes:

| Field        | Description                                        |
|--------------|----------------------------------------------------|
| `api_key`    | Your project API key.                              |
| `event`      | Event name (`$pageview` for pageviews).            |
| `properties` | Event properties merged with device context.       |
| `user_id`    | Stable user ID (from `localStorage`).              |
| `timestamp`  | ISO-8601 timestamp of the event.                   |

When a browser is available, the following **auto-captured properties** are merged into every event's properties:

| Property           | Source                |
|--------------------|-----------------------|
| `$session_id`      | session-scoped ID      |
| `$language`        | `navigator.language`   |
| `$screen_width`    | `screen.width`         |
| `$screen_height`   | `screen.height`        |
| `$platform`        | `navigator.platform`   |

Pageview events additionally include `url` and `referrer`.

> **Note:** Event names and properties prefixed with `$` are reserved for InsightFlow's internal use.

---

## How It Works

1. `init()` stores your API key and flushes any buffered events.
2. Each `track()` call builds a JSON payload enriched with user/session/device context.
3. Events are delivered with `navigator.sendBeacon` (falling back to a `fetch`-less `XMLHttpRequest`) to `POST {apiHost}/api/v1/track/`.
4. InsightFlow's backend ingests events through Kafka into ClickHouse, powering your dashboards and ML insights.

Because `sendBeacon` is used, events are guaranteed to be sent even when the user closes the tab immediately after an action.

---

## Browser Support

Works in all modern browsers, including evergreen Chrome, Firefox, Safari, and Edge. Uses `localStorage`, `sessionStorage`, `navigator.sendBeacon`, and `XMLHttpRequest` — each with graceful fallbacks when unavailable.

---

## Privacy & Consent

The SDK is privacy-friendly by design:

- Generates **anonymous** user IDs by default — no PII is collected unless you pass it.
- Uses first-party `localStorage`/`sessionStorage`; no third-party cookies.
- If your app requires consent (e.g. GDPR), simply call `init()` and `track()` only after the user opts in.

```js
function onConsentGranted() {
  InsightFlow.init('pk_xxxx');
}
```

---

## Development

```bash
# Install dev dependencies
npm install

# Publish a new version (requires npm login)
npm version patch
npm publish
```

The published package is a single UMD bundle (`insightflow.js`) with zero build step.

---

## License

[MIT](LICENSE) © InsightFlow AI
