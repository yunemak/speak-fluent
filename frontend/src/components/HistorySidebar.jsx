import { useState } from 'react';
import styles from './HistorySidebar.module.css';

export default function HistorySidebar({ sessions, warnings, loading, error, disabled, selectedId, onSelect, onRefresh, onDelete }) {
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState('');

  const remove = async session => {
    if (!window.confirm(`Delete "${session.title}" (${new Date(session.completed_at).toLocaleString()}) and its Markdown file? This cannot be undone.`)) return;
    setDeletingId(session.id);
    setDeleteError('');
    try {
      await onDelete(session.id);
    } catch (failure) {
      setDeleteError(failure.message);
    } finally {
      setDeletingId(null);
    }
  };

  return <aside className={styles.sidebar}>
    <a className={styles.brand} href="/" aria-label="Speak Fluent home">sf<span>●</span></a>
    <h2>Conversations</h2>
    {loading && <p className={styles.note} role="status">Loading history…</p>}
    {!loading && !error && sessions.length === 0 && <p className={styles.empty}>Your completed practice will appear here.</p>}
    {disabled && <p className={styles.note}>Available after this session</p>}
    <nav className={styles.list} aria-label="Saved conversations">
      {sessions.map(session => <div key={session.id} className={styles.row}>
        <button className={styles.select} disabled={disabled || deletingId === session.id}
        aria-current={selectedId === session.id ? 'page' : undefined}
        title={session.title} onClick={() => onSelect(session.id)}>
        <span>{new Date(session.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</span>
        <small>{new Date(session.completed_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</small>
        </button>
        <button className={styles.delete} disabled={disabled || deletingId !== null}
          aria-label={`Delete ${session.title}, ${new Date(session.completed_at).toLocaleString()}`}
          title={deletingId === session.id ? 'Deleting…' : 'Delete conversation'}
          onClick={() => remove(session)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" />
          </svg>
        </button>
      </div>)}
    </nav>
    {deletingId && <p className={styles.note} role="status">Deleting conversation…</p>}
    {deleteError && <p className={styles.warning} role="alert">{deleteError}</p>}
    {error && <p className={styles.warning} role="alert">{error}</p>}
    {warnings.map(warning => <p key={warning.filename} className={styles.warning} role="alert">
      <strong>{warning.filename}</strong><br />{warning.message}
    </p>)}
    <button className={`quiet ${styles.refresh}`} onClick={onRefresh} disabled={loading}>Refresh history</button>
    <div className={styles.local}><span /> Saved on this computer</div>
  </aside>;
}
