import { useState } from 'react';
import Transcript from './Transcript.jsx';
import styles from './HistoryView.module.css';

export default function HistoryView({ entry, loading, error, onRetry, onStart, onBack, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const remove = async () => {
    setDeleting(true);
    setDeleteError('');
    try {
      await onDelete();
    } catch (failure) {
      setDeleteError(failure.message);
      setDeleting(false);
    }
  };

  return <section className={styles.view} aria-label="Saved conversation">
    <div className={styles.actions}>
      <button className="quiet" onClick={onBack}>Back to practice</button>
      <button className={styles.start} onClick={onStart}>Start a conversation</button>
    </div>
    {loading && <p role="status">Opening your conversation…</p>}
    {error && <div className={styles.warning} role="alert"><p>{error}</p><button className="quiet" onClick={onRetry}>Retry opening</button></div>}
    {entry && <>
      <h1>{entry.title}</h1>
      {entry.completed_at && <p className={styles.date}>
        {new Date(entry.completed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        {' · '}
        {new Date(entry.completed_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
      </p>}
      <p className={styles.note}>Your transcript and feedback, saved locally.</p>
      <Transcript turns={entry.turns || []} report={entry.report_text} headerRight="Saved transcript" />
      <div className={styles.danger}>
        {confirming ? <>
          <p>Delete this conversation and its Markdown file? This cannot be undone.</p>
          <div className={styles.dangerActions}>
            <button className="quiet" onClick={() => setConfirming(false)} disabled={deleting}>Keep it</button>
            <button className={styles.delete} onClick={remove} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete permanently'}
            </button>
          </div>
        </> : <button className={styles.deleteLink} onClick={() => setConfirming(true)}>Delete this conversation</button>}
        {deleteError && <p className={styles.deleteError} role="alert">{deleteError}</p>}
      </div>
    </>}
  </section>;
}
