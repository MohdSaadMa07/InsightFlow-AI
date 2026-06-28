export default function Placeholder({ title }) {
  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>{title}</h2>
      <div className="card empty-state" style={{ padding: '80px 20px', marginTop: 16 }}>
        <div style={{ fontSize: 40, marginBottom: 16 }}>🚧</div>
        <div style={{ fontSize: 18, color: '#EAEAFA', marginBottom: 8 }}>Coming Soon</div>
        <div>The {title} module is currently under development.</div>
      </div>
    </div>
  )
}
