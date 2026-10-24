import { useState } from 'react';
import DeleteConversationDialog from './DeleteConversationDialog.jsx';
import styles from './HistorySidebar.module.css';

export default function HistorySidebar({ sessions, warnings, loading, error, disabled, selectedId, onSelect, onRefresh, onDelete }) {
  const [pendingDelete, setPendingDelete] = useState(null);

  return <><aside className={styles.sidebar}>
    <a className={styles.brand} href="/" aria-label="Speak Fluent home">sf<span>●</span></a>
    <h2>Conversations</h2>
    {loading && <p className={styles.note} role="status">Loading history…</p>}
    {!loading && !error && sessions.length === 0 && <p className={styles.empty}>Your completed practice will appear here.</p>}
    {disabled && <p className={styles.note}>Available after this session</p>}
    <nav className={styles.list} aria-label="Saved conversations">
      {sessions.map(session => {
        const completed = new Date(session.completed_at);
        const title = session.title || 'Conversation';
        return <div key={session.id} className={styles.row}>
          <button className={styles.select} disabled={disabled}
          aria-current={selectedId === session.id ? 'page' : undefined}
          title={title} onClick={() => onSelect(session.id)}>
          <span className={styles.title}>{title}</span>
          <small>
            {completed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            {' · '}
            {completed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
          </small>
          </button>
          <button className={styles.delete} disabled={disabled}
            aria-label={`Delete ${title}, ${completed.toLocaleString()}`}
            title="Delete conversation"
            onClick={() => setPendingDelete(session)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" />
            </svg>
          </button>
        </div>;
      })}
    </nav>
    {error && <p className={styles.warning} role="alert">{error}</p>}
    {warnings.map(warning => <p key={warning.filename} className={styles.warning} role="alert">
      <strong>{warning.filename}</strong><br />{warning.message}
    </p>)}
    <button className={`quiet ${styles.refresh}`} onClick={onRefresh} disabled={loading}>Refresh history</button>
    <div className={styles.local}><span /> Saved on this computer</div>
  </aside>
    {pendingDelete && <DeleteConversationDialog session={pendingDelete} onDelete={onDelete}
      onClose={() => setPendingDelete(null)} />}
  </>;
}
