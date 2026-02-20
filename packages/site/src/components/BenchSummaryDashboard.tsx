import React, { useEffect, useMemo, useState } from 'react';

import styles from './BenchSummaryDashboard.module.css';

type SummaryIndexEntry = {
  file: string;
  suite: string;
  run_id: string;
  machine: string;
  generated_at_utc: string;
};

type RuntimeSummary = {
  runtime: string;
  runtime_label: string;
  runtime_version: string;
  startup_mean_seconds: number;
  startup_stdev_seconds: number;
  executed: boolean;
};

type BenchmarkRow = {
  benchmark: string;
  workload_class: string;
  runtime: string;
  runtime_label: string;
  mean_seconds: number;
  stdev_seconds: number;
  sample_count: number;
  warmup_count: number;
  speedup_vs_baseline: number | null;
  p_value: number | null;
  memory_rss_bytes: number | null;
  compile_time_seconds: number | null;
};

type SmokeSummary = {
  suite: string;
  run_id: string;
  generated_at_utc: string;
  machine: string;
  baseline_runtime: string;
  runtimes: RuntimeSummary[];
  skipped_runtimes: string[];
  benchmarks: BenchmarkRow[];
  metadata?: {
    run_config?: {
      ci_mode?: boolean;
      require_cinderx_baseline?: boolean;
    };
  };
  limitations?: string[] | null;
};

type SummaryIndex = {
  updated_at_utc: string;
  entries: SummaryIndexEntry[];
};

type PublishedRunRow = SummaryIndexEntry & {
  baselineRuntime: string;
  policyEnforced: boolean;
  ciMode: boolean;
  cinderxBaselined: boolean;
};

type ViewMode = 'runtime' | 'vs-cinderx';

type CinderxComparisonRow = {
  benchmark: string;
  workloadClass: string;
  cinderxSeconds: number;
  runtimeSeconds: number;
  cinderxSpeedup: number;
  cinderxGainPercent: number;
  runtimePValue: number | null;
  runtimeRssBytes: number | null;
  runtimeCompileSeconds: number | null;
};

const INDEX_URL = '/data/summary/index.json';

function formatSignedPercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function formatNullable(value: number | null, digits: number): string {
  if (value === null || Number.isNaN(value)) {
    return 'n/a';
  }
  return value.toFixed(digits);
}

function formatRssMiB(value: number | null): string {
  if (value === null || Number.isNaN(value) || value <= 0) {
    return 'n/a';
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function chooseComparisonRuntime(runtimes: RuntimeSummary[]): string {
  const executed = runtimes.filter((item) => item.executed);
  const withCpython = executed.find((item) => item.runtime === 'cpython');
  if (withCpython) {
    return withCpython.runtime;
  }
  const firstNonCinderx = executed.find((item) => item.runtime !== 'cpython-cinderx');
  return firstNonCinderx?.runtime ?? '';
}

export default function BenchSummaryDashboard() {
  const [index, setIndex] = useState<SummaryIndex | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [summary, setSummary] = useState<SmokeSummary | null>(null);
  const [publishedRuns, setPublishedRuns] = useState<PublishedRunRow[]>([]);
  const [selectedRuntime, setSelectedRuntime] = useState<string>('');
  const [comparisonRuntime, setComparisonRuntime] = useState<string>('');
  const [selectedWorkload, setSelectedWorkload] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('vs-cinderx');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let active = true;
    fetch(INDEX_URL)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load ${INDEX_URL}`);
        }
        return response.json() as Promise<SummaryIndex>;
      })
      .then((payload) => {
        if (!active) {
          return;
        }
        setIndex(payload);
        const latest = payload.entries?.[0]?.file ?? '';
        setSelectedFile(latest);
      })
      .catch(() => {
        if (active) {
          setError(
            'No benchmark summaries are published yet. Run `cxc bench run --suite smoke` first.'
          );
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!index) {
      setPublishedRuns([]);
      return;
    }

    let active = true;
    const maxRows = 12;
    const entries = index.entries.slice(0, maxRows);

    Promise.all(
      entries.map(async (entry) => {
        try {
          const response = await fetch(`/data/summary/${entry.file}`);
          if (!response.ok) {
            throw new Error('summary load failed');
          }
          const payload = (await response.json()) as SmokeSummary;
          const baselineRuntime =
            typeof payload.baseline_runtime === 'string' ? payload.baseline_runtime : 'unknown';
          const policyEnforced = Boolean(payload.metadata?.run_config?.require_cinderx_baseline);
          const ciMode = Boolean(payload.metadata?.run_config?.ci_mode);
          return {
            ...entry,
            baselineRuntime,
            policyEnforced,
            ciMode,
            cinderxBaselined: baselineRuntime === 'cpython-cinderx'
          } satisfies PublishedRunRow;
        } catch {
          return {
            ...entry,
            baselineRuntime: 'unavailable',
            policyEnforced: false,
            ciMode: false,
            cinderxBaselined: false
          } satisfies PublishedRunRow;
        }
      })
    ).then((rows) => {
      if (active) {
        setPublishedRuns(rows);
      }
    });

    return () => {
      active = false;
    };
  }, [index]);

  useEffect(() => {
    if (!selectedFile) {
      setSummary(null);
      return;
    }

    let active = true;
    fetch(`/data/summary/${selectedFile}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load /data/summary/${selectedFile}`);
        }
        return response.json() as Promise<SmokeSummary>;
      })
      .then((payload) => {
        if (!active) {
          return;
        }
        setSummary(payload);

        const executed = payload.runtimes.filter((item) => item.executed);
        const baselineRuntime =
          executed.find((item) => item.runtime === payload.baseline_runtime)?.runtime ??
          executed[0]?.runtime ??
          '';

        setSelectedRuntime(baselineRuntime);
        const defaultComparisonRuntime = chooseComparisonRuntime(payload.runtimes);
        setComparisonRuntime(defaultComparisonRuntime);
        setSelectedWorkload('all');

        const hasCinderxComparison =
          payload.baseline_runtime === 'cpython-cinderx' &&
          payload.runtimes.some((item) => item.executed && item.runtime !== 'cpython-cinderx') &&
          defaultComparisonRuntime !== '';
        setViewMode(hasCinderxComparison ? 'vs-cinderx' : 'runtime');
        setError('');
      })
      .catch(() => {
        if (active) {
          setError('Failed to load selected benchmark summary JSON.');
        }
      });

    return () => {
      active = false;
    };
  }, [selectedFile]);

  const executedRuntimes = useMemo(() => {
    if (!summary) {
      return [];
    }
    return summary.runtimes.filter((item) => item.executed);
  }, [summary]);

  const cinderxBaseline = useMemo(() => {
    return summary?.baseline_runtime === 'cpython-cinderx';
  }, [summary]);

  const ciShapeRun = useMemo(() => {
    return Boolean(summary?.metadata?.run_config?.ci_mode);
  }, [summary]);

  const cinderxPolicyEnforced = useMemo(() => {
    return Boolean(summary?.metadata?.run_config?.require_cinderx_baseline);
  }, [summary]);

  const workloadOptions = useMemo(() => {
    if (!summary) {
      return [];
    }
    return Array.from(new Set(summary.benchmarks.map((row) => row.workload_class))).sort();
  }, [summary]);

  const filteredRows = useMemo(() => {
    if (!summary || !selectedRuntime) {
      return [];
    }
    return summary.benchmarks
      .filter((row) => row.runtime === selectedRuntime)
      .filter((row) => selectedWorkload === 'all' || row.workload_class === selectedWorkload)
      .sort((a, b) => (b.speedup_vs_baseline ?? 0) - (a.speedup_vs_baseline ?? 0));
  }, [selectedRuntime, selectedWorkload, summary]);

  const maxSpeedup = useMemo(() => {
    const values = filteredRows
      .map((row) => row.speedup_vs_baseline ?? 0)
      .filter((value) => value > 0);
    return values.length > 0 ? Math.max(...values) : 1;
  }, [filteredRows]);

  const comparisonRuntimeOptions = useMemo(() => {
    return executedRuntimes.filter((runtime) => runtime.runtime !== 'cpython-cinderx');
  }, [executedRuntimes]);

  const canCompareVsCinderx = useMemo(() => {
    return cinderxBaseline && comparisonRuntimeOptions.length > 0;
  }, [cinderxBaseline, comparisonRuntimeOptions.length]);

  const cinderxComparisonRows = useMemo(() => {
    if (!summary || !canCompareVsCinderx || !comparisonRuntime) {
      return [];
    }

    const cinderxRows = summary.benchmarks.filter((row) => row.runtime === 'cpython-cinderx');
    const compareByBenchmark = new Map(
      summary.benchmarks
        .filter((row) => row.runtime === comparisonRuntime)
        .map((row) => [row.benchmark, row] as const)
    );

    return cinderxRows
      .filter((row) => selectedWorkload === 'all' || row.workload_class === selectedWorkload)
      .map((cinderxRow) => {
        const compareRow = compareByBenchmark.get(cinderxRow.benchmark);
        if (!compareRow) {
          return null;
        }

        const cinderxSeconds = cinderxRow.mean_seconds;
        const runtimeSeconds = compareRow.mean_seconds;
        const cinderxSpeedup = cinderxSeconds > 0 ? runtimeSeconds / cinderxSeconds : 0;
        const cinderxGainPercent =
          runtimeSeconds > 0 ? ((runtimeSeconds - cinderxSeconds) / runtimeSeconds) * 100 : 0;

        const row: CinderxComparisonRow = {
          benchmark: cinderxRow.benchmark,
          workloadClass: cinderxRow.workload_class,
          cinderxSeconds,
          runtimeSeconds,
          cinderxSpeedup,
          cinderxGainPercent,
          runtimePValue: compareRow.p_value,
          runtimeRssBytes: compareRow.memory_rss_bytes,
          runtimeCompileSeconds: compareRow.compile_time_seconds
        };
        return row;
      })
      .filter((row): row is CinderxComparisonRow => row !== null)
      .sort((a, b) => b.cinderxSpeedup - a.cinderxSpeedup);
  }, [canCompareVsCinderx, comparisonRuntime, selectedWorkload, summary]);

  const cinderxComparisonMax = useMemo(() => {
    const values = cinderxComparisonRows
      .map((row) => row.cinderxSpeedup)
      .filter((value) => value > 0);
    return values.length > 0 ? Math.max(...values) : 1;
  }, [cinderxComparisonRows]);

  if (error && !summary) {
    return <p className={styles.notice}>{error}</p>;
  }

  if (!index || !summary) {
    return <p className={styles.notice}>Loading benchmark summaries...</p>;
  }

  const selectedComparisonRuntimeLabel =
    comparisonRuntimeOptions.find((item) => item.runtime === comparisonRuntime)?.runtime_label ??
    comparisonRuntime;

  return (
    <section className={styles.wrapper}>
      {cinderxBaseline && cinderxPolicyEnforced ? (
        <p className={styles.claimStrong}>
          Canonical CinderX-first summary: headline comparisons are anchored to the CinderX
          baseline.
        </p>
      ) : (
        <p className={styles.claimWarning}>
          Diagnostics-only summary (non-claim): this result is not fully CinderX-baselined and
          policy-enforced for headline comparisons.
        </p>
      )}

      <div className={styles.presets}>
        <button
          type="button"
          className={`${styles.presetButton} ${viewMode === 'vs-cinderx' ? styles.presetActive : ''}`}
          onClick={() => {
            setViewMode('vs-cinderx');
          }}
          disabled={!canCompareVsCinderx}
          title={
            canCompareVsCinderx
              ? 'Compare runtimes directly against CinderX baseline'
              : 'CinderX baseline plus at least one additional runtime is required'
          }
        >
          CinderX Headline View
        </button>
        <button
          type="button"
          className={`${styles.presetButton} ${viewMode === 'runtime' ? styles.presetActive : ''}`}
          onClick={() => setViewMode('runtime')}
        >
          Secondary Runtime View
        </button>
      </div>

      <div className={styles.controls}>
        <label>
          Result Set
          <select value={selectedFile} onChange={(event) => setSelectedFile(event.target.value)}>
            {index.entries.map((entry) => (
              <option key={entry.file} value={entry.file}>
                {entry.generated_at_utc} | {entry.machine} | {entry.run_id}
              </option>
            ))}
          </select>
        </label>

        {viewMode === 'runtime' ? (
          <label>
            Runtime
            <select
              value={selectedRuntime}
              onChange={(event) => {
                setSelectedRuntime(event.target.value);
                setViewMode('runtime');
              }}
            >
              {executedRuntimes.map((runtime) => (
                <option key={runtime.runtime} value={runtime.runtime}>
                  {runtime.runtime_label}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label>
          Workload Class
          <select
            value={selectedWorkload}
            onChange={(event) => setSelectedWorkload(event.target.value)}
          >
            <option value="all">All</option>
            {workloadOptions.map((workload) => (
              <option key={workload} value={workload}>
                {workload}
              </option>
            ))}
          </select>
        </label>
      </div>

      {viewMode === 'vs-cinderx' && canCompareVsCinderx ? (
        <div className={styles.controls}>
          <label>
            Comparison Runtime
            <select
              value={comparisonRuntime}
              onChange={(event) => setComparisonRuntime(event.target.value)}
            >
              {comparisonRuntimeOptions.map((runtime) => (
                <option key={`compare-${runtime.runtime}`} value={runtime.runtime}>
                  {runtime.runtime_label}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      <div className={styles.meta}>
        <p>
          <strong>Suite:</strong> {summary.suite}
        </p>
        <p>
          <strong>Run ID:</strong> {summary.run_id}
        </p>
        <p>
          <strong>Generated:</strong> {summary.generated_at_utc}
        </p>
        <p>
          <strong>Machine:</strong> {summary.machine}
        </p>
        <p>
          <strong>Baseline:</strong> {summary.baseline_runtime}
        </p>
      </div>

      <h3>Published runs</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Generated (UTC)</th>
            <th>Suite</th>
            <th>Run ID</th>
            <th>Machine</th>
            <th>Baseline</th>
            <th>Policy</th>
            <th>Mode</th>
          </tr>
        </thead>
        <tbody>
          {publishedRuns.map((run) => (
            <tr key={`published-run-${run.file}`}>
              <td>{run.generated_at_utc}</td>
              <td>{run.suite}</td>
              <td>{run.run_id}</td>
              <td>{run.machine}</td>
              <td>
                <span className={run.cinderxBaselined ? styles.flagGood : styles.flagWarn}>
                  {run.baselineRuntime}
                </span>
              </td>
              <td>{run.policyEnforced ? 'enforced' : 'not-enforced'}</td>
              <td>{run.ciMode ? 'ci-shape' : 'full'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {!cinderxBaseline ? (
        <p className={styles.warning}>
          This summary is not CinderX-baselined. Run with `--cpython-cinderx` to produce direct
          CinderX comparisons.
        </p>
      ) : null}
      {ciShapeRun ? (
        <p className={styles.notice}>
          CI-shape mode is enabled for this run. Treat this as reproducibility diagnostics, not a
          headline performance claim.
        </p>
      ) : null}

      {viewMode === 'runtime' && cinderxBaseline ? (
        <>
          <h3>Secondary runtime chart (non-headline)</h3>
          <div className={styles.chart}>
            {filteredRows.map((row) => {
              const ratio = row.speedup_vs_baseline ?? 0;
              const width = `${Math.max((ratio / maxSpeedup) * 100, 3)}%`;
              return (
                <div key={`${row.runtime}-${row.benchmark}`} className={styles.chartRow}>
                  <div className={styles.chartLabel}>{row.benchmark}</div>
                  <div className={styles.chartTrack}>
                    <div className={styles.chartBar} style={{ width }} />
                  </div>
                  <div className={styles.chartValue}>{ratio ? `${ratio.toFixed(2)}x` : 'n/a'}</div>
                </div>
              );
            })}
          </div>

          <h3>Secondary runtime statistics</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Benchmark</th>
                <th>Workload</th>
                <th>Mean (s)</th>
                <th>Stdev (s)</th>
                <th>Speedup vs selected baseline</th>
                <th>p-value</th>
                <th>RSS (max)</th>
                <th>Compile time (s)</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={`runtime-row-${row.runtime}-${row.benchmark}`}>
                  <td>{row.benchmark}</td>
                  <td>{row.workload_class}</td>
                  <td>{row.mean_seconds.toFixed(6)}</td>
                  <td>{row.stdev_seconds.toFixed(6)}</td>
                  <td>
                    {row.speedup_vs_baseline ? `${row.speedup_vs_baseline.toFixed(2)}x` : 'n/a'}
                  </td>
                  <td>{formatNullable(row.p_value, 4)}</td>
                  <td>{formatRssMiB(row.memory_rss_bytes)}</td>
                  <td>{formatNullable(row.compile_time_seconds, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : viewMode === 'runtime' ? (
        <p className={styles.notice}>
          Runtime comparison charts are hidden for non-CinderX-baselined summaries. Run with a real
          `--cpython-cinderx` runtime to publish CinderX-first comparisons.
        </p>
      ) : (
        <>
          <h3>CinderX vs {selectedComparisonRuntimeLabel} chart</h3>
          {canCompareVsCinderx ? (
            <>
              <div className={styles.chart}>
                {cinderxComparisonRows.map((row) => {
                  const width = `${Math.max((row.cinderxSpeedup / cinderxComparisonMax) * 100, 3)}%`;
                  return (
                    <div key={`cinderx-compare-${row.benchmark}`} className={styles.chartRow}>
                      <div className={styles.chartLabel}>{row.benchmark}</div>
                      <div className={styles.chartTrack}>
                        <div className={styles.compareBar} style={{ width }} />
                      </div>
                      <div className={styles.chartValue}>{row.cinderxSpeedup.toFixed(2)}x</div>
                    </div>
                  );
                })}
              </div>

              <h3>CinderX delta table</h3>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Benchmark</th>
                    <th>Workload</th>
                    <th>CinderX mean (s)</th>
                    <th>{selectedComparisonRuntimeLabel} mean (s)</th>
                    <th>CinderX speedup</th>
                    <th>CinderX gain</th>
                    <th>{selectedComparisonRuntimeLabel} p-value</th>
                    <th>{selectedComparisonRuntimeLabel} RSS (max)</th>
                    <th>{selectedComparisonRuntimeLabel} compile (s)</th>
                  </tr>
                </thead>
                <tbody>
                  {cinderxComparisonRows.map((row) => (
                    <tr key={`cinderx-row-${row.benchmark}`}>
                      <td>{row.benchmark}</td>
                      <td>{row.workloadClass}</td>
                      <td>{row.cinderxSeconds.toFixed(6)}</td>
                      <td>{row.runtimeSeconds.toFixed(6)}</td>
                      <td>{row.cinderxSpeedup.toFixed(2)}x</td>
                      <td
                        className={
                          row.cinderxGainPercent >= 0 ? styles.deltaBetter : styles.deltaWorse
                        }
                      >
                        {formatSignedPercent(row.cinderxGainPercent)}
                      </td>
                      <td>{formatNullable(row.runtimePValue, 4)}</td>
                      <td>{formatRssMiB(row.runtimeRssBytes)}</td>
                      <td>{formatNullable(row.runtimeCompileSeconds, 4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className={styles.notice}>
              CinderX comparison requires a summary where `cpython-cinderx` and at least one
              additional runtime are executed.
            </p>
          )}
        </>
      )}

      <h3>Runtime Startup (mean seconds)</h3>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Runtime</th>
            <th>Version</th>
            <th>Startup mean (s)</th>
            <th>Startup stdev (s)</th>
          </tr>
        </thead>
        <tbody>
          {executedRuntimes.map((runtime) => (
            <tr key={runtime.runtime}>
              <td>{runtime.runtime_label}</td>
              <td>{runtime.runtime_version}</td>
              <td>{runtime.startup_mean_seconds.toFixed(6)}</td>
              <td>{runtime.startup_stdev_seconds.toFixed(6)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {summary.skipped_runtimes.length > 0 ? (
        <p className={styles.warning}>
          Skipped runtimes/tools: {summary.skipped_runtimes.join('; ')}
        </p>
      ) : null}
      {error ? <p className={styles.warning}>{error}</p> : null}
    </section>
  );
}
