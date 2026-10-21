import styles from './Robot.module.css';

export default function Robot({ speaking }) {
  return <div className={`${styles.balloon} ${speaking ? styles.speaking : ''}`} aria-hidden="true">
    <svg viewBox="0 0 200 180" className={styles.robot}>
      <path d="M100 40V22" stroke="#405d60" strokeWidth="5" strokeLinecap="round" />
      <circle cx="100" cy="18" r="7" fill="#e6ae7e" />
      <rect x="27" y="76" width="15" height="30" rx="7" fill="#78989b" />
      <rect x="158" y="76" width="15" height="30" rx="7" fill="#78989b" />
      <rect x="38" y="39" width="124" height="109" rx="35" fill="#fffdf6" stroke="#405d60" strokeWidth="4" />
      <rect x="51" y="58" width="98" height="65" rx="24" fill="#2d474a" />
      <path d="M71 86q7-12 14 0M115 86q7-12 14 0" fill="none" stroke="#d2e4d6" strokeWidth="5" strokeLinecap="round" />
      <path className={styles.smile} d="M90 100q10 10 20 0" fill="none" stroke="#d2e4d6" strokeWidth="4" strokeLinecap="round" />
      <circle cx="64" cy="103" r="4" fill="#e7b08d" opacity=".8" />
      <circle cx="136" cy="103" r="4" fill="#e7b08d" opacity=".8" />
      <path d="M76 149v12m48-12v12" stroke="#405d60" strokeWidth="7" strokeLinecap="round" />
    </svg>
    <span className={styles.spark}>✦</span>
  </div>;
}
