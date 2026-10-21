import styles from './HistorySidebar.module.css';

export default function HistorySidebar({ sessions, warnings, loading, error, disabled, selectedId, onSelect, onRefresh }) {
  return <aside className={styles.sidebar}>
    <a className={styles.brand} href="/" aria-label="Speak Fluent home">sf<span>●</span></a>
    <h2>Conversations</h2>
    {loading && <p className={styles.note} role="status">Loading history…</p>}
    {!loading && !error && sessions.length === 0 && <p className={styles.empty}>Your completed practice will appear here.</p>}
    {disabled && <p className={styles.note}>Available after this session</p>}
    <nav className={styles.list} aria-label="Saved conversations">
      {sessions.map(session => <button key={session.id} disabled={disabled}
        aria-current={selectedId === session.id ? 'page' : undefined}
        title={session.title} onClick={() => onSelect(session.id)}>
        <span>{new Date(session.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
        <small>{new Date(session.completed_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</small>
      </button>)}
    </nav>
    {error && <p className={styles.warning} role="alert">{error}</p>}
    {warnings.map(warning => <p key={warning.filename} className={styles.warning} role="alert">
      <strong>{warning.filename}</strong><br />{warning.message}
    </p>)}
    <button className={`quiet ${styles.refresh}`} onClick={onRefresh} disabled={loading}>Refresh history</button>
    <div className={styles.local}><span /> Saved on this computer</div>
  </aside>;
}
