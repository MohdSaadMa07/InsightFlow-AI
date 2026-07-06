import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const COPY_FEEDBACK_DURATION = 2000

function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false)
  return (
    <button className="btn btn-gray btn-xs" onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), COPY_FEEDBACK_DURATION) }}>
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

function CodeBlock({ code, lang = 'html' }) {
  return (
    <div className="code-snippet" style={{ marginBottom: 24 }}>
      <pre><code>{code}</code></pre>
      <CopyBtn text={code} />
    </div>
  )
}

function Section({ title, desc, children }) {
  return (
    <div className="card" style={{ padding: 28, marginBottom: 24 }}>
      <h3 style={{ fontSize: 18, color: '#f1f5f9', marginBottom: 8 }}>{title}</h3>
      {desc && <p className="text-muted" style={{ marginBottom: 20, fontSize: 14, lineHeight: 1.6 }}>{desc}</p>}
      {children}
    </div>
  )
}

const SNIPPETS = {
  cdn: `<script src="https://cdn.insightflow.ai/sdk.js" data-api-key="YOUR_API_KEY"></script>`,

  cdnManual: `<script src="https://cdn.insightflow.ai/sdk.js"></script>
<script>
  InsightFlow.init('YOUR_API_KEY');

  InsightFlow.track('signup_completed', {
    plan: 'premium',
    referrer: 'google_ads'
  });

  InsightFlow.identify('user_12345');
</script>`,

  npm: `import InsightFlow from 'insightflow-sdk';

InsightFlow.init('YOUR_API_KEY', {
  userId: 'user_12345'
});`,

  init: `InsightFlow.init('YOUR_API_KEY');

// With options:
InsightFlow.init('YOUR_API_KEY', {
  apiHost: 'https://98.93.48.72.nip.io',  // custom backend
  userId: 'user_12345'                     // known user ID
});`,

  track: `// Track button click
document.getElementById('signup-btn').addEventListener('click', () => {
  InsightFlow.track('signup_clicked', {
    button_location: 'hero',
    plan: 'free'
  });
});

// Track purchase with revenue
InsightFlow.track('purchase_completed', {
  product_id: 'prod_456',
  price: 29.99,
  currency: 'USD',
  category: 'subscription'
});

// Track page section visibility
InsightFlow.track('section_viewed', {
  section: 'pricing',
  scroll_depth_pct: 75
});`,

  identify: `// After user logs in
InsightFlow.identify('user_abc_123');

// The user ID will be attached to all subsequent events.
// This lets you track the same user across sessions and devices.`,

  page: `// Track a virtual pageview (SPA navigation)
InsightFlow.page('dashboard');

// With extra properties
InsightFlow.page('settings', { tab: 'billing' });

// The $pageview event auto-fires on initial load,
// call this manually for client-side route changes.`,

  autoProps: `{
  "$session_id":   "if_k8f3a_x9m2p7q4r",  // auto-generated per session
  "$language":     "en-US",                  // navigator.language
  "$screen_width":  1920,
  "$screen_height": 1080,
  "$platform":     "Win32"                   // navigator.platform
}`,

  events: `// Auto-tracked on page load
InsightFlow.track('$pageview', { url: '...', referrer: '...' });

// Track user engagement
InsightFlow.track('button_click', { button_id: 'pricing_cta' });

// Track e-commerce
InsightFlow.track('order_placed', {
  order_id: 'ORD-789',
  total: 59.98,
  items: ['pro-plan', 'addon-sec'],
  currency: 'USD'
});

// Track feature usage
InsightFlow.track('feature_used', {
  feature: 'export_csv',
  source: 'dashboard_reports'
});

// Track errors
InsightFlow.track('error_occurred', {
  error_type: 'api_timeout',
  endpoint: '/analytics/query',
  status_code: 504
});`,

  fullExample: `// 1. Include the SDK (CDN)
<script src="https://cdn.insightflow.ai/sdk.js"></script>

<script>
  // 2. Initialize with your API key
  InsightFlow.init('YOUR_API_KEY');

  // 3. Identify returning users
  const user = getCurrentUser();
  if (user) InsightFlow.identify(user.id);

  // 4. Track custom events throughout your app
  function onSignup(formData) {
    // ... your signup logic ...
    InsightFlow.track('signup', {
      plan: formData.plan,
      source: formData.referral
    });
  }

  function onPurchase(product) {
    // ... your checkout logic ...
    InsightFlow.track('purchase', {
      product_id: product.id,
      amount: product.price,
      currency: 'USD'
    });
  }

  // 5. Track SPA page views (if applicable)
  router.onRouteChange((route) => {
    InsightFlow.page(route.name);
  });
</script>`,

  dataApi: `// All events are sent to:
POST /api/v1/track/

{
  "api_key":   "YOUR_API_KEY",
  "event":     "signup",
  "properties": {
    "plan":      "premium",
    "source":    "google_ads",
    "$session_id": "if_k8f3a_x9m2p7q4r",
    "$language":   "en-US",
    "$platform":   "Win32"
  },
  "user_id":   "user_abc_123",
  "timestamp": "2026-07-06T15:30:00.000Z"
}`
}

export default function SDKTutorial() {
  const navigate = useNavigate()

  return (
    <div className="layout">
      <nav className="topnav">
        <h1 style={{ cursor: 'pointer' }} onClick={() => navigate('/projects')}>InsightFlow</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-gray btn-sm" onClick={() => navigate('/projects')}>
            Back to Projects
          </button>
        </div>
      </nav>

      <div style={{ maxWidth: 820, margin: '0 auto', padding: '40px 24px 80px' }}>
        <h2 style={{ fontSize: 32, fontWeight: 700, color: '#f1f5f9', marginBottom: 8 }}>
          Developer Guide
        </h2>
        <p className="hero-subtitle" style={{ fontSize: 16, marginBottom: 40, lineHeight: 1.7 }}>
          Integrate InsightFlow into your web application in minutes. 
          The browser SDK automatically tracks page views and lets you send 
          custom events with a single line of code.
        </p>

        <Section title="1. Installation" desc="Choose your integration method:">
          <h4 style={{ color: '#e2e8f0', marginBottom: 8, fontSize: 14 }}>CDN (Recommended)</h4>
          <p className="text-muted" style={{ fontSize: 13, marginBottom: 8 }}>Add this tag to your HTML. The SDK auto-initializes and sends a <code style={{ color: '#22d3ee' }}>$pageview</code> event on page load.</p>
          <CodeBlock code={SNIPPETS.cdn} />

          <h4 style={{ color: '#e2e8f0', marginBottom: 8, fontSize: 14, marginTop: 24 }}>npm / Bundler</h4>
          <p className="text-muted" style={{ fontSize: 13, marginBottom: 8 }}>Install as a dependency and import in your JavaScript bundle.</p>
          <CodeBlock code={SNIPPETS.npm} lang="bash" />
        </Section>

        <Section title="2. Initialize" desc="Call init() once before tracking any events. This sets your API key and queues any events fired before initialization.">
          <CodeBlock code={SNIPPETS.init} lang="js" />
          <table className="props-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Option</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Type</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Default</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={{ padding: '8px 12px', color: '#e2e8f0' }}><code>apiHost</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>string</td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}><code>https://api.insightflow.ai</code></td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Custom backend URL for self-hosted setups</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 12px', color: '#e2e8f0' }}><code>userId</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>string</td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>auto-generated</td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Pre-set a known user ID</td>
              </tr>
            </tbody>
          </table>
        </Section>

        <Section title="3. Track Events" desc="Send any user action as an event. Events are the building blocks of all your analytics — funnels, churn prediction, revenue forecasting, and anomaly detection all depend on them.">
          <CodeBlock code={SNIPPETS.track} lang="js" />
          <div className="card" style={{ padding: 16, marginTop: 12, background: 'rgba(34, 211, 238, 0.05)', border: '1px solid rgba(34, 211, 238, 0.15)' }}>
            <p style={{ fontSize: 13, color: '#e2e8f0', margin: 0, lineHeight: 1.6 }}>
              <strong style={{ color: '#22d3ee' }}>Pro tip:</strong> Events before <code style={{ color: '#22d3ee' }}>init()</code> are queued and sent once the SDK is ready. You can call <code style={{ color: '#22d3ee' }}>track()</code> safely anywhere in your page lifecycle.
            </p>
          </div>
        </Section>

        <Section title="4. Identify Users" desc="Link events to a known user ID. This lets you track individual users across sessions and devices for personalized analytics.">
          <CodeBlock code={SNIPPETS.identify} lang="js" />
        </Section>

        <Section title="5. Track Page Views" desc="For single-page applications (SPA), call page() on route changes to track navigation. On traditional multi-page sites, the $pageview event fires automatically.">
          <CodeBlock code={SNIPPETS.page} lang="js" />
        </Section>

        <Section title="6. Auto-Enriched Properties" desc="Every event is automatically enriched with these properties — no extra code needed.">
          <CodeBlock code={SNIPPETS.autoProps} lang="json" />
        </Section>

        <Section title="7. Example Events by Use Case" desc="Here are common event patterns you can start tracking immediately:">
          <CodeBlock code={SNIPPETS.events} lang="js" />
        </Section>

        <Section title="8. Full Integration Example" desc="A complete example showing the SDK in action from initialization to tracking:">
          <CodeBlock code={SNIPPETS.fullExample} lang="html" />
        </Section>

        <Section title="9. Data Format" desc="Each event sent to the API follows this schema. The backend validates and stores it in ClickHouse for real-time querying.">
          <CodeBlock code={SNIPPETS.dataApi} lang="json" />
        </Section>

        <Section title="10. SDK Reference" desc="Complete reference of all available SDK methods:">
          <table className="props-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Method</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Arguments</th>
                <th style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={{ padding: '8px 12px', color: '#22d3ee' }}><code>init(apiKey, options?)</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>apiKey: string, options: {`{ apiHost?, userId? }`}</td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Initialize SDK, flush queued events, auto-send $pageview</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={{ padding: '8px 12px', color: '#22d3ee' }}><code>track(event, properties?)</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>event: string, properties: object</td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Send a custom event with optional properties</td>
              </tr>
              <tr style={{ borderBottom: '1px solid #0f172a' }}>
                <td style={{ padding: '8px 12px', color: '#22d3ee' }}><code>identify(userId)</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>userId: string</td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Set the user ID for the current visitor</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 12px', color: '#22d3ee' }}><code>page(name, properties?)</code></td>
                <td style={{ padding: '8px 12px', color: '#cbd5e1' }}>name: string, properties: object</td>
                <td style={{ padding: '8px 12px', color: '#94a3b8' }}>Track a $pageview event (for SPA routing)</td>
              </tr>
            </tbody>
          </table>
          <div className="card" style={{ padding: 16, marginTop: 20, background: 'rgba(34, 211, 238, 0.05)', border: '1px solid rgba(34, 211, 238, 0.15)' }}>
            <p style={{ fontSize: 13, color: '#e2e8f0', margin: 0, lineHeight: 1.6 }}>
              <strong style={{ color: '#22d3ee' }}>Transport:</strong> Uses <code style={{ color: '#22d3ee' }}>navigator.sendBeacon()</code> with 
              <code style={{ color: '#22d3ee' }}> XMLHttpRequest</code> fallback. Zero external dependencies — the SDK is ~2KB gzipped.
            </p>
          </div>
        </Section>
      </div>
    </div>
  )
}