import React from 'react';
import benchmarkSample from '@site/src/data/benchmark-sample.json';

import styles from './BenchChartPlaceholder.module.css';

type Sample = {
  benchmark: string;
  relative_speedup: number;
};

const rows = benchmarkSample as Sample[];

export default function BenchChartPlaceholder() {
  const max = Math.max(...rows.map((row) => row.relative_speedup), 1);

  return (
    <section className={styles.wrapper}>
      <p className={styles.title}>Illustrative Relative Speedup (dummy data)</p>
      <div className={styles.chart}>
        {rows.map((row) => {
          const width = `${Math.max((row.relative_speedup / max) * 100, 2)}%`;
          return (
            <div key={row.benchmark} className={styles.row}>
              <span className={styles.label}>{row.benchmark}</span>
              <div className={styles.barTrack}>
                <div className={styles.bar} style={{ width }} />
              </div>
              <span className={styles.value}>{row.relative_speedup.toFixed(2)}x</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
