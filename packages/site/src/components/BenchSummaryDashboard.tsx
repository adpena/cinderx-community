import React, { useEffect, useMemo, useState } from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';

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
  runtime_details?: Record<string, unknown>;
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

type GuardrailCheck = {
  name: string;
  status: string;
  detail: string;
  enforceable?: boolean;
};

type SummaryMetadata = {
  host?: {
    os?: string;
    kernel?: string;
    architecture?: string;
    cpu_model?: string;
    cpu_logical_count?: number;
    ram_total_bytes?: number;
  };
  run_config?: {
    ci_mode?: boolean;
    require_cinderx_baseline?: boolean;
    warmups?: number;
    samples?: number;
    startup_samples?: number;
    pyperformance_mode?: string;
    pyperformance_benchmarks?: string[] | null;
    pyperformance_bootstrap_inline_enabled?: boolean;
    pyperformance_bootstrap_inline_sha256?: string;
    pyperformance_bootstrap_profile?: string | null;
    pyperformance_bootstrap_profile_source?: string | null;
    pyperformance_bootstrap_jit_compile_after_n_calls?: number | null;
    pyperformance_bootstrap_target_runtime_key?: string | null;
  };
  toolchain?: {
    benchmark_repo_sha?: string;
    pyperformance_version?: string;
    pyperformance_command?: string[];
    pyperformance_bootstrap_mode?: string;
    cinderx_upstream?: {
      repo_url?: string;
      commit_sha?: string;
      clone_timestamp_utc?: string;
    };
  };
  guardrails?: {
    checks?: GuardrailCheck[];
    enforceable_failures?: string[];
  };
};

type BenchmarkSummary = {
  suite: string;
  run_id: string;
  generated_at_utc: string;
  machine: string;
  baseline_runtime: string;
  runtimes: RuntimeSummary[];
  skipped_runtimes: string[];
  benchmarks: BenchmarkRow[];
  metadata?: SummaryMetadata;
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
  benchmarkCount: number;
  executedRuntimes: number;
  pyperformanceMode: string;
  bootstrapEnabled: boolean;
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

const BENCHMARK_DISPLAY_LIMIT = 40;

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

function formatRamGiB(value?: number): string {
  if (value === undefined || Number.isNaN(value) || value <= 0) {
    return 'unknown';
  }
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GiB`;
}

function shortenSha(value?: string): string {
  if (!value) {
    return 'unknown';
  }
  return value.length > 12 ? value.slice(0, 12) : value;
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

function runtimeLabel(summary: BenchmarkSummary | null, runtimeKey: string): string {
  if (!summary) {
    return runtimeKey;
  }
  return summary.runtimes.find((item) => item.runtime === runtimeKey)?.runtime_label ?? runtimeKey;
}

function asBadgeMode(ciMode: boolean, pyperformanceMode?: string): string {
  if (ciMode) {
    return 'ci-shape';
  }
  if (pyperformanceMode) {
    return pyperformanceMode;
  }
  return 'full';
}

export default function BenchSummaryDashboard() {
  const indexUrl = useBaseUrl('/data/summary/index.json');
  const summaryBaseUrl = useBaseUrl('/data/summary/');

  const [index, setIndex] = useState<SummaryIndex | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [publishedRuns, setPublishedRuns] = useState<PublishedRunRow[]>([]);
  const [selectedRuntime, setSelectedRuntime] = useState<string>('');
  const [comparisonRuntime, setComparisonRuntime] = useState<string>('');
  const [selectedWorkload, setSelectedWorkload] = useState<string>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('vs-cinderx');
  const [benchmarkFilter, setBenchmarkFilter] = useState<string>('');
  const [showAllRows, setShowAllRows] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    let active = true;
    fetch(indexUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load ${indexUrl}`);
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
            'No benchmark summaries are currently available. Publish a pyperformance summary first.'
          );
        }
      });

    return () => {
      active = false;
    };
  }, [indexUrl]);

  useEffect(() => {
    if (!index) {
      setPublishedRuns([]);
      return;
    }

    let active = true;
    const entries = index.entries.slice(0, 20);

    Promise.all(
      entries.map(async (entry) => {
        try {
          const response = await fetch(`${summaryBaseUrl}${entry.file}`);
          if (!response.ok) {
            throw new Error('summary load failed');
          }
          const payload = (await response.json()) as BenchmarkSummary;
          const baselineRuntime =
            typeof payload.baseline_runtime === 'string' ? payload.baseline_runtime : 'unknown';
          const runConfig = payload.metadata?.run_config;
          const policyEnforced = Boolean(runConfig?.require_cinderx_baseline);
          const ciMode = Boolean(runConfig?.ci_mode);
          return {
            ...entry,
            baselineRuntime,
            policyEnforced,
            ciMode,
            cinderxBaselined: baselineRuntime === 'cpython-cinderx',
            benchmarkCount: payload.benchmarks.length,
            executedRuntimes: payload.runtimes.filter((item) => item.executed).length,
            pyperformanceMode: runConfig?.pyperformance_mode ?? 'default',
            bootstrapEnabled: Boolean(runConfig?.pyperformance_bootstrap_inline_enabled)
          } satisfies PublishedRunRow;
        } catch {
          return {
            ...entry,
            baselineRuntime: 'unavailable',
            policyEnforced: false,
            ciMode: false,
            cinderxBaselined: false,
            benchmarkCount: 0,
            executedRuntimes: 0,
            pyperformanceMode: 'unknown',
            bootstrapEnabled: false
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
  }, [index, summaryBaseUrl]);

  useEffect(() => {
    if (!selectedFile) {
      setSummary(null);
      return;
    }

    let active = true;
    fetch(`${summaryBaseUrl}${selectedFile}`)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load ${summaryBaseUrl}${selectedFile}`);
        }
        return response.json() as Promise<BenchmarkSummary>;
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
        setBenchmarkFilter('');
        setShowAllRows(false);
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
  }, [selectedFile, summaryBaseUrl]);

  const executedRuntimes = useMemo(() => {
    if (!summary) {
      return [];
    }
    return summary.runtimes.filter((item) => item.executed);
  }, [summary]);

  const cinderxBaseline = useMemo(() => {
    return summary?.baseline_runtime === 'cpython-cinderx';
  }, [summary]);

  const runConfig = summary?.metadata?.run_config;
  const host = summary?.metadata?.host;
  const toolchain = summary?.metadata?.toolchain;
  const guardrails = summary?.metadata?.guardrails;
  const ciShapeRun = Boolean(runConfig?.ci_mode);
  const cinderxPolicyEnforced = Boolean(runConfig?.require_cinderx_baseline);
  const bootstrapEnabled = Boolean(runConfig?.pyperformance_bootstrap_inline_enabled);
  const bootstrapProfile = runConfig?.pyperformance_bootstrap_profile ?? null;
  const bootstrapProfileSource =
    runConfig?.pyperformance_bootstrap_profile_source ??
    (bootstrapEnabled ? 'unknown' : 'disabled');
  const bootstrapLabel = bootstrapEnabled
    ? bootstrapProfile
      ? `profile: ${bootstrapProfile}`
      : 'custom-inline'
    : 'disabled';
  const bootstrapBadgeClass = !bootstrapEnabled
    ? styles.badgeNeutral
    : bootstrapProfileSource === 'auto-default'
      ? styles.badgeGood
      : styles.badgeWarn;

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
    const normalizedFilter = benchmarkFilter.trim().toLowerCase();
    return summary.benchmarks
      .filter((row) => row.runtime === selectedRuntime)
      .filter((row) => selectedWorkload === 'all' || row.workload_class === selectedWorkload)
      .filter((row) => {
        if (!normalizedFilter) {
          return true;
        }
        return row.benchmark.toLowerCase().includes(normalizedFilter);
      })
      .sort((a, b) => (b.speedup_vs_baseline ?? 0) - (a.speedup_vs_baseline ?? 0));
  }, [benchmarkFilter, selectedRuntime, selectedWorkload, summary]);

  const displayedRuntimeRows = useMemo(() => {
    if (showAllRows) {
      return filteredRows;
    }
    return filteredRows.slice(0, BENCHMARK_DISPLAY_LIMIT);
  }, [filteredRows, showAllRows]);

  const maxSpeedup = useMemo(() => {
    const values = displayedRuntimeRows
      .map((row) => row.speedup_vs_baseline ?? 0)
      .filter((value) => value > 0);
    return values.length > 0 ? Math.max(...values) : 1;
  }, [displayedRuntimeRows]);

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

    const normalizedFilter = benchmarkFilter.trim().toLowerCase();
    const cinderxRows = summary.benchmarks.filter((row) => row.runtime === 'cpython-cinderx');
    const compareByBenchmark = new Map(
      summary.benchmarks
        .filter((row) => row.runtime === comparisonRuntime)
        .map((row) => [row.benchmark, row] as const)
    );

    return cinderxRows
      .filter((row) => selectedWorkload === 'all' || row.workload_class === selectedWorkload)
      .filter((row) => {
        if (!normalizedFilter) {
          return true;
        }
        return row.benchmark.toLowerCase().includes(normalizedFilter);
      })
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
  }, [benchmarkFilter, canCompareVsCinderx, comparisonRuntime, selectedWorkload, summary]);

  const displayedCinderxRows = useMemo(() => {
    if (showAllRows) {
      return cinderxComparisonRows;
    }
    return cinderxComparisonRows.slice(0, BENCHMARK_DISPLAY_LIMIT);
  }, [cinderxComparisonRows, showAllRows]);

  const cinderxComparisonMax = useMemo(() => {
    const values = displayedCinderxRows
      .map((row) => row.cinderxSpeedup)
      .filter((value) => value > 0);
    return values.length > 0 ? Math.max(...values) : 1;
  }, [displayedCinderxRows]);

  const selectedComparisonRuntimeLabel =
    comparisonRuntimeOptions.find((item) => item.runtime === comparisonRuntime)?.runtime_label ??
    comparisonRuntime;

  if (error && !summary) {
    return <p className={styles.notice}>{error}</p>;
  }

  if (!index || !summary) {
    return <p className={styles.notice}>Loading benchmark summaries...</p>;
  }

  const visibleCount =
    viewMode === 'vs-cinderx' ? displayedCinderxRows.length : displayedRuntimeRows.length;
  const totalCount = viewMode === 'vs-cinderx' ? cinderxComparisonRows.length : filteredRows.length;

  return (
    <section className={styles.wrapper}>
      {cinderxBaseline && cinderxPolicyEnforced ? (
        <p className={styles.claimStrong}>
          Publishable benchmark run. Headline comparisons are anchored to CinderX baseline and
          policy-enforced metadata.
        </p>
      ) : (
        <p className={styles.claimWarning}>
          Diagnostics-only run. Do not treat this result as a headline benchmark claim.
        </p>
      )}

      <div className={styles.overviewGrid}>
        <article className={styles.overviewCard}>
          <h3>Run at a glance</h3>
          <ul>
            <li>Suite: {summary.suite}</li>
            <li>Run ID: {summary.run_id}</li>
            <li>Generated UTC: {summary.generated_at_utc}</li>
            <li>Machine tag: {summary.machine}</li>
            <li>Benchmarks: {summary.benchmarks.length}</li>
            <li>Executed runtimes: {executedRuntimes.length}</li>
            <li>
              Baseline: <strong>{runtimeLabel(summary, summary.baseline_runtime)}</strong>
            </li>
          </ul>
        </article>

        <article className={styles.overviewCard}>
          <h3>Run mode</h3>
          <div className={styles.badgeRow}>
            <span className={ciShapeRun ? styles.badgeWarn : styles.badgeGood}>
              {asBadgeMode(ciShapeRun, runConfig?.pyperformance_mode)}
            </span>
            <span className={cinderxPolicyEnforced ? styles.badgeGood : styles.badgeWarn}>
              {cinderxPolicyEnforced ? 'policy-enforced' : 'not policy-enforced'}
            </span>
            <span className={bootstrapBadgeClass}>bootstrap: {bootstrapLabel}</span>
          </div>
          <ul>
            <li>Workload classes: {workloadOptions.length}</li>
            <li>Startup samples: {runConfig?.startup_samples ?? 'n/a'}</li>
            <li>Samples per benchmark: {runConfig?.samples ?? 'n/a'}</li>
            <li>Warmups per benchmark: {runConfig?.warmups ?? 'n/a'}</li>
            <li>
              Bootstrap JIT threshold:{' '}
              {runConfig?.pyperformance_bootstrap_jit_compile_after_n_calls ?? 'n/a'}
            </li>
            <li>Bootstrap profile source: {bootstrapProfileSource}</li>
            <li>
              Bootstrap target runtime:{' '}
              {runConfig?.pyperformance_bootstrap_target_runtime_key ?? 'n/a'}
            </li>
            <li>Skipped runtimes: {summary.skipped_runtimes.length}</li>
          </ul>
        </article>
      </div>

      <div className={styles.panelGrid}>
        <article className={styles.panel}>
          <h3>Machine profile</h3>
          <dl className={styles.kv}>
            <dt>OS</dt>
            <dd>{host?.os ?? 'unknown'}</dd>
            <dt>Kernel</dt>
            <dd>{host?.kernel ?? 'unknown'}</dd>
            <dt>Architecture</dt>
            <dd>{host?.architecture ?? 'unknown'}</dd>
            <dt>CPU model</dt>
            <dd>{host?.cpu_model ?? 'unknown'}</dd>
            <dt>CPU logical count</dt>
            <dd>{host?.cpu_logical_count ?? 'unknown'}</dd>
            <dt>RAM</dt>
            <dd>{formatRamGiB(host?.ram_total_bytes)}</dd>
          </dl>
        </article>

        <article className={styles.panel}>
          <h3>Toolchain and provenance</h3>
          <dl className={styles.kv}>
            <dt>Benchmark repo SHA</dt>
            <dd>{shortenSha(toolchain?.benchmark_repo_sha)}</dd>
            <dt>CinderX upstream SHA</dt>
            <dd>{shortenSha(toolchain?.cinderx_upstream?.commit_sha)}</dd>
            <dt>CinderX clone timestamp</dt>
            <dd>{toolchain?.cinderx_upstream?.clone_timestamp_utc ?? 'unknown'}</dd>
            <dt>pyperformance version</dt>
            <dd>{toolchain?.pyperformance_version ?? 'unknown'}</dd>
            <dt>pyperformance launcher</dt>
            <dd>
              {Array.isArray(toolchain?.pyperformance_command)
                ? toolchain.pyperformance_command.join(' ')
                : 'unknown'}
            </dd>
            <dt>Bootstrap mode</dt>
            <dd>{toolchain?.pyperformance_bootstrap_mode ?? 'disabled'}</dd>
            <dt>Bootstrap profile</dt>
            <dd>{runConfig?.pyperformance_bootstrap_profile ?? 'n/a'}</dd>
            <dt>Bootstrap profile source</dt>
            <dd>{bootstrapProfileSource}</dd>
            <dt>Bootstrap hash</dt>
            <dd>{runConfig?.pyperformance_bootstrap_inline_sha256 ?? 'n/a'}</dd>
          </dl>
        </article>

        <article className={styles.panel}>
          <h3>Guardrails status</h3>
          {guardrails?.checks && guardrails.checks.length > 0 ? (
            <ul className={styles.guardrailList}>
              {guardrails.checks.map((check) => (
                <li key={check.name}>
                  <span className={styles.guardrailName}>{check.name}</span>
                  <span className={styles.guardrailStatus}>{check.status}</span>
                  <span className={styles.guardrailDetail}>{check.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.noticeInline}>No guardrail checks captured in metadata.</p>
          )}
          {guardrails?.enforceable_failures && guardrails.enforceable_failures.length > 0 ? (
            <p className={styles.warningInline}>
              Enforceable failures: {guardrails.enforceable_failures.join('; ')}
            </p>
          ) : null}
        </article>
      </div>

      <div className={styles.historyBlock}>
        <h3 className={styles.sectionHeading}>Published run history</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Generated (UTC)</th>
              <th>Run ID</th>
              <th>Machine</th>
              <th>Suite</th>
              <th>Benchmarks</th>
              <th>Runtimes</th>
              <th>Baseline</th>
              <th>Mode</th>
              <th>Policy</th>
            </tr>
          </thead>
          <tbody>
            {publishedRuns.map((run) => (
              <tr key={`published-run-${run.file}`}>
                <td>{run.generated_at_utc}</td>
                <td>{run.run_id}</td>
                <td>{run.machine}</td>
                <td>{run.suite}</td>
                <td>{run.benchmarkCount}</td>
                <td>{run.executedRuntimes}</td>
                <td>
                  <span className={run.cinderxBaselined ? styles.flagGood : styles.flagWarn}>
                    {run.baselineRuntime}
                  </span>
                </td>
                <td>{asBadgeMode(run.ciMode, run.pyperformanceMode)}</td>
                <td>{run.policyEnforced ? 'enforced' : 'not-enforced'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.controlsBlock}>
        <div className={styles.presets}>
          <button
            type="button"
            className={`${styles.presetButton} ${viewMode === 'vs-cinderx' ? styles.presetActive : ''}`}
            onClick={() => {
              setViewMode('vs-cinderx');
              setShowAllRows(false);
            }}
            disabled={!canCompareVsCinderx}
            title={
              canCompareVsCinderx
                ? 'Compare runtimes directly against CinderX baseline'
                : 'CinderX baseline plus at least one additional runtime is required'
            }
          >
            CinderX headline view
          </button>
          <button
            type="button"
            className={`${styles.presetButton} ${viewMode === 'runtime' ? styles.presetActive : ''}`}
            onClick={() => {
              setViewMode('runtime');
              setShowAllRows(false);
            }}
          >
            Secondary runtime view
          </button>
        </div>

        <div className={styles.controls}>
          <label>
            Result set
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

          {viewMode === 'vs-cinderx' && canCompareVsCinderx ? (
            <label>
              Comparison runtime
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
          ) : null}

          <label>
            Workload class
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

          <label>
            Benchmark filter
            <input
              type="text"
              value={benchmarkFilter}
              placeholder="substring match (e.g. json, regex, startup)"
              onChange={(event) => setBenchmarkFilter(event.target.value)}
            />
          </label>
        </div>

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

        <div className={styles.rowMeta}>
          <p>
            Showing {visibleCount} of {totalCount} benchmark rows
            {benchmarkFilter ? ' after filter' : ''}.
          </p>
          {totalCount > BENCHMARK_DISPLAY_LIMIT ? (
            <button
              type="button"
              className={styles.inlineButton}
              onClick={() => setShowAllRows((value) => !value)}
            >
              {showAllRows ? 'Show top rows only' : `Show all ${totalCount} rows`}
            </button>
          ) : null}
        </div>
      </div>

      {viewMode === 'runtime' && cinderxBaseline ? (
        <>
          <h3 className={styles.sectionHeading}>
            Secondary runtime chart ({runtimeLabel(summary, selectedRuntime)} vs{' '}
            {runtimeLabel(summary, summary.baseline_runtime)})
          </h3>
          <div className={styles.chart}>
            {displayedRuntimeRows.map((row) => {
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

          <h3 className={styles.sectionHeading}>Secondary runtime statistics</h3>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Benchmark</th>
                <th>Workload</th>
                <th>Mean (s)</th>
                <th>Stdev (s)</th>
                <th>Speedup vs baseline</th>
                <th>p-value</th>
                <th>RSS (max)</th>
                <th>Compile time (s)</th>
              </tr>
            </thead>
            <tbody>
              {displayedRuntimeRows.map((row) => (
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
          <h3 className={styles.sectionHeading}>CinderX vs {selectedComparisonRuntimeLabel}</h3>
          {canCompareVsCinderx ? (
            <>
              <div className={styles.chart}>
                {displayedCinderxRows.map((row) => {
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

              <h3 className={styles.sectionHeading}>CinderX delta table</h3>
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
                  {displayedCinderxRows.map((row) => (
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

      <h3 className={styles.sectionHeading}>Runtime startup (mean seconds)</h3>
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
      {summary.limitations && summary.limitations.length > 0 ? (
        <p className={styles.warning}>Run limitations: {summary.limitations.join('; ')}</p>
      ) : null}
      {error ? <p className={styles.warning}>{error}</p> : null}
    </section>
  );
}
