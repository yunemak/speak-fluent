import { useEffect, useId, useRef, useState } from 'react';
import styles from './DeleteConversationDialog.module.css';

export default function DeleteConversationDialog({ session, onDelete, onClose }) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);

  const remove = async () => {
    setDeleting(true);
    setError('');
    try {
      await onDelete(session.id);
      onClose();
    } catch (failure) {
      setError(failure.message);
      setDeleting(false);
    }
  };

  return <dialog ref={dialogRef} className={styles.dialog}
    aria-labelledby={titleId} aria-describedby={descriptionId}
    onCancel={event => {
      event.preventDefault();
      if (!deleting) onClose();
    }}>
    <div className={styles.icon} aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6" />
      </svg>
    </div>
    <h2 id={titleId}>Delete conversation?</h2>
    <p id={descriptionId} className={styles.description}>This conversation and its saved Markdown file will be permanently deleted. This cannot be undone.</p>
    <div className={styles.conversation}>
      <strong>{session.title}</strong>
      <time dateTime={session.completed_at}>{new Date(session.completed_at).toLocaleString()}</time>
    </div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {deleting && <p className={styles.description} role="status">Deleting conversation…</p>}
    <div className={styles.actions}>
      <button className="quiet" onClick={onClose} disabled={deleting} autoFocus>Cancel</button>
      <button className={styles.delete} onClick={remove} disabled={deleting}>
        {deleting ? 'Deleting…' : 'Delete conversation'}
      </button>
    </div>
  </dialog>;
}
