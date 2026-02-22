"""CLI entrypoint for cinderx_community."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cinderx_community.bench.runner import (
    PYPERFORMANCE_BOOTSTRAP_PROFILES,
    PYPERFORMANCE_SUITE,
    SMOKE_SUITE,
    build_plan,
    export_metadata_dossiers,
    list_suites,
    preflight_pyperformance_suite,
    run_pyperformance_suite,
    run_smoke_suite,
    verify_publishable_summaries,
)
from cinderx_community.bench.runner import (
    to_json as bench_to_json,
)
from cinderx_community.research.extract import (
    extract_metadata,
    render_docs_from_introspection,
    to_json,
)
from cinderx_community.upstream import (
    UpstreamError,
    ensure_latest_clone,
    pin_upstream,
    read_history,
    upstream_status,
)

app = typer.Typer(help="CinderX Community CLI")
upstream_app = typer.Typer(help="Sync and inspect upstream repositories")
bench_app = typer.Typer(help="Benchmark planning and execution")
research_app = typer.Typer(help="Introspection extraction and generated docs")

app.add_typer(upstream_app, name="upstream")
app.add_typer(bench_app, name="bench")
app.add_typer(research_app, name="research")


@upstream_app.command("clone")
def upstream_clone(
    repo: Annotated[str, typer.Option(help="Configured upstream repo key")] = "cinderx",
    dest: Annotated[Path, typer.Option(help="Destination directory")] = Path(
        ".cache/upstream/cinderx"
    ),
) -> None:
    """Clone or update the repo and pin to the latest remote HEAD commit."""
    try:
        status = ensure_latest_clone(repo=repo, destination=dest)
    except UpstreamError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"repo: {status.repo}")
    typer.echo(f"destination: {status.destination}")
    if status.pinned_commit:
        typer.echo(f"pinned_commit: {status.pinned_commit}")
    if status.pinned_timestamp_utc:
        typer.echo(f"pinned_timestamp_utc: {status.pinned_timestamp_utc}")
    if status.pinned_tags:
        typer.echo(f"pinned_tags: {', '.join(status.pinned_tags)}")
    if status.latest_remote_commit:
        typer.echo(f"latest_remote_commit: {status.latest_remote_commit}")


@upstream_app.command("pin")
def upstream_pin(
    repo: Annotated[str, typer.Option(help="Configured upstream repo key")] = "cinderx",
    dest: Annotated[Path, typer.Option(help="Destination directory")] = Path(
        ".cache/upstream/cinderx"
    ),
    commit: Annotated[
        str | None,
        typer.Option(help="Commit SHA to pin. Defaults to local HEAD in --dest"),
    ] = None,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Optional pin tag. Repeat --tag to add multiple tags."),
    ] = None,
) -> None:
    """Pin upstream provenance metadata in python/cinderx_community/pins.toml."""
    try:
        status = pin_upstream(repo=repo, destination=dest, commit=commit, tags=tag)
    except UpstreamError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"repo: {status.repo}")
    typer.echo(f"destination: {status.destination}")
    typer.echo(f"pinned_commit: {status.pinned_commit or 'none'}")
    typer.echo(f"pinned_timestamp_utc: {status.pinned_timestamp_utc or 'none'}")
    typer.echo(f"pinned_tags: {', '.join(status.pinned_tags) if status.pinned_tags else 'none'}")
    typer.echo(f"latest_remote_commit: {status.latest_remote_commit or 'unknown'}")


@upstream_app.command("status")
def upstream_repo_status(
    repo: Annotated[str, typer.Option(help="Configured upstream repo key")] = "cinderx",
    dest: Annotated[Path, typer.Option(help="Destination directory")] = Path(
        ".cache/upstream/cinderx"
    ),
) -> None:
    """Print pinned/local/latest commit status for the upstream repo."""
    try:
        status = upstream_status(repo=repo, destination=dest)
    except UpstreamError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if status.pinned_commit is None and status.local_commit is None:
        typer.echo("uninitialized")
        raise typer.Exit(code=0)

    typer.echo(f"repo: {status.repo}")
    typer.echo(f"destination: {status.destination}")
    typer.echo(f"pinned_commit: {status.pinned_commit or 'none'}")
    typer.echo(f"pinned_timestamp_utc: {status.pinned_timestamp_utc or 'none'}")
    typer.echo(f"pinned_tags: {', '.join(status.pinned_tags) if status.pinned_tags else 'none'}")
    typer.echo(f"local_commit: {status.local_commit or 'none'}")
    typer.echo(f"latest_remote_commit: {status.latest_remote_commit or 'unknown'}")

    if status.latest_remote_commit and status.pinned_commit:
        if status.latest_remote_commit == status.pinned_commit:
            typer.echo("state: up-to-date")
        else:
            typer.echo("state: behind-latest (run `cxc upstream clone` to refresh)")


@upstream_app.command("history")
def upstream_history(
    repo: Annotated[str, typer.Option(help="Configured upstream repo key")] = "cinderx",
    limit: Annotated[int, typer.Option(min=1, max=500, help="Maximum records to print")] = 20,
) -> None:
    """Print recorded upstream commit snapshots."""
    rows = read_history(repo=repo, limit=limit)
    if not rows:
        typer.echo("no-history")
        raise typer.Exit(code=0)

    typer.echo(json.dumps(rows, indent=2, sort_keys=True))


@bench_app.command("list")
def bench_list() -> None:
    """List planned benchmark suites."""
    for suite in list_suites():
        if suite in {SMOKE_SUITE, PYPERFORMANCE_SUITE}:
            typer.echo(f"{suite} (runnable)")
        else:
            typer.echo(f"{suite} (planned)")


@bench_app.command("run")
def bench_run(
    suite: Annotated[str, typer.Option(help="Benchmark suite key")] = SMOKE_SUITE,
    python: Annotated[
        Path,
        typer.Option(exists=True, file_okay=True, dir_okay=False, help="Python executable"),
    ] = ...,
    out: Annotated[Path, typer.Option(help="Raw run output root")] = Path("data/runs"),
    summary_out: Annotated[Path, typer.Option(help="Normalized summary output root")] = Path(
        "data/summary"
    ),
    static_summary_out: Annotated[
        Path | None,
        typer.Option(help="Optional static-site summary mirror root"),
    ] = Path("packages/site/static/data/summary"),
    machine: Annotated[
        str | None,
        typer.Option(help="Machine name for result paths/metadata. Defaults to hostname."),
    ] = None,
    ci_mode: Annotated[
        bool,
        typer.Option(help="Quick smoke mode for CI sanity checks; not for performance claims."),
    ] = False,
    enforce_guardrails: Annotated[
        bool,
        typer.Option(help="Fail if enforceable reproducibility guardrails are violated."),
    ] = False,
    require_cinderx_baseline: Annotated[
        bool,
        typer.Option(
            help=(
                "Enforce CinderX as the primary comparison baseline for publishable runs. "
                "Requires --cpython-cinderx so CPython-only fallback summaries are non-publishable."
            ),
        ),
    ] = False,
    cpython_cinderx: Annotated[
        Path | None,
        typer.Option(
            "--cpython-cinderx",
            file_okay=True,
            dir_okay=False,
            help="Optional Python executable with CinderX enabled.",
        ),
    ] = None,
    pypy: Annotated[
        Path | None,
        typer.Option(file_okay=True, dir_okay=False, help="Optional PyPy executable."),
    ] = None,
    pyperformance_bootstrap_inline: Annotated[
        str | None,
        typer.Option(
            help=(
                "Optional inline Python executed via a temporary sitecustomize shim for "
                "pyperformance runs (experimental). Useful for custom CinderX feature trials."
            ),
        ),
    ] = None,
    pyperformance_bootstrap_profile: Annotated[
        str | None,
        typer.Option(
            help=(
                "Named pyperformance bootstrap profile. Supported values: "
                + ", ".join(PYPERFORMANCE_BOOTSTRAP_PROFILES)
                + ". When omitted and --cpython-cinderx is provided, "
                "cinderx-jit-all is auto-applied to the cpython-cinderx lane "
                "(eager JIT with no strict-loader dependency)."
            ),
        ),
    ] = None,
    pyperformance_bootstrap_jit_compile_after_n_calls: Annotated[
        int | None,
        typer.Option(
            min=1,
            help=(
                "JIT compile-after-n-calls threshold for "
                "--pyperformance-bootstrap-profile=cinderx-jit-compile-after-n-calls."
            ),
        ),
    ] = None,
    pyperformance_runtime_timeout_seconds: Annotated[
        int | None,
        typer.Option(
            min=1,
            help=(
                "Command timeout in seconds for each pyperformance runtime invocation. "
                "Defaults to 1200 in --ci-mode and 14400 otherwise."
            ),
        ),
    ] = None,
) -> None:
    """Run benchmark suites or print execution plans for not-yet-automated suites."""
    runnable_suites = {SMOKE_SUITE, PYPERFORMANCE_SUITE}
    if suite not in runnable_suites:
        try:
            plan = build_plan(suite=suite, python_executable=python)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        typer.echo(bench_to_json(plan))
        raise typer.Exit(code=0)

    try:
        if suite == SMOKE_SUITE:
            run_result = run_smoke_suite(
                python=python,
                out_root=out,
                summary_root=summary_out,
                machine=machine,
                ci_mode=ci_mode,
                enforce_guardrails=enforce_guardrails,
                require_cinderx_baseline=require_cinderx_baseline,
                cpython_cinderx=cpython_cinderx,
                pypy=pypy,
                static_summary_root=static_summary_out,
            )
        else:
            run_result = run_pyperformance_suite(
                python=python,
                out_root=out,
                summary_root=summary_out,
                machine=machine,
                ci_mode=ci_mode,
                enforce_guardrails=enforce_guardrails,
                require_cinderx_baseline=require_cinderx_baseline,
                cpython_cinderx=cpython_cinderx,
                pypy=pypy,
                static_summary_root=static_summary_out,
                pyperformance_bootstrap_inline=pyperformance_bootstrap_inline,
                pyperformance_bootstrap_profile=pyperformance_bootstrap_profile,
                pyperformance_bootstrap_jit_compile_after_n_calls=(
                    pyperformance_bootstrap_jit_compile_after_n_calls
                ),
                pyperformance_runtime_timeout_seconds=pyperformance_runtime_timeout_seconds,
            )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(bench_to_json(run_result))


@bench_app.command("preflight-pyperformance")
def bench_preflight_pyperformance(
    python: Annotated[
        Path,
        typer.Option(exists=True, file_okay=True, dir_okay=False, help="Python executable"),
    ] = ...,
    cpython_cinderx: Annotated[
        Path | None,
        typer.Option(
            "--cpython-cinderx",
            file_okay=True,
            dir_okay=False,
            help="Optional Python executable with CinderX enabled.",
        ),
    ] = None,
    require_cinderx_baseline: Annotated[
        bool,
        typer.Option(
            help="Require CinderX baseline runtime availability for preflight checks.",
        ),
    ] = False,
    pyperformance_bootstrap_inline: Annotated[
        str | None,
        typer.Option(
            help=(
                "Optional inline Python executed via a temporary sitecustomize shim for "
                "pyperformance preflight."
            ),
        ),
    ] = None,
    pyperformance_bootstrap_profile: Annotated[
        str | None,
        typer.Option(
            help=(
                "Named pyperformance bootstrap profile for preflight. Supported values: "
                + ", ".join(PYPERFORMANCE_BOOTSTRAP_PROFILES)
            ),
        ),
    ] = None,
    pyperformance_bootstrap_jit_compile_after_n_calls: Annotated[
        int | None,
        typer.Option(
            min=1,
            help=(
                "JIT compile-after-n-calls threshold for "
                "--pyperformance-bootstrap-profile=cinderx-jit-compile-after-n-calls."
            ),
        ),
    ] = None,
    timeout_seconds: Annotated[
        int,
        typer.Option(min=1, help="Command timeout for each pyperformance preflight check."),
    ] = 45,
) -> None:
    """Run a fast pyperformance launcher/bootstrap preflight before full benchmark execution."""
    try:
        result = preflight_pyperformance_suite(
            python=python,
            cpython_cinderx=cpython_cinderx,
            require_cinderx_baseline=require_cinderx_baseline,
            pyperformance_bootstrap_inline=pyperformance_bootstrap_inline,
            pyperformance_bootstrap_profile=pyperformance_bootstrap_profile,
            pyperformance_bootstrap_jit_compile_after_n_calls=(
                pyperformance_bootstrap_jit_compile_after_n_calls
            ),
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(bench_to_json(result))


@bench_app.command("verify-publish")
def bench_verify_publish(
    summary_root: Annotated[Path, typer.Option(help="Normalized summary root")] = Path(
        "data/summary"
    ),
    static_summary_root: Annotated[
        Path | None,
        typer.Option(help="Optional static-site summary mirror root to validate"),
    ] = Path("packages/site/static/data/summary"),
    require_suite: Annotated[
        list[str] | None,
        typer.Option(
            "--require-suite",
            help=(
                "Suite to require for publish validation (repeatable). "
                "Defaults to smoke + pyperformance."
            ),
        ),
    ] = None,
) -> None:
    """Fail if required latest summaries are not truly CinderX-baselined."""
    suites = list(require_suite) if require_suite else None
    try:
        verification = verify_publishable_summaries(
            summary_root=summary_root,
            static_summary_root=static_summary_root,
            suites=suites,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(bench_to_json(verification))


@bench_app.command("export-dossier")
def bench_export_dossier(
    summary_root: Annotated[Path, typer.Option(help="Normalized summary root")] = Path(
        "data/summary"
    ),
    output_root: Annotated[
        Path | None,
        typer.Option(help="Optional dossier output directory (defaults to <summary_root>/reports)"),
    ] = None,
    require_suite: Annotated[
        list[str] | None,
        typer.Option(
            "--require-suite",
            help=(
                "Suite to include in dossier export (repeatable). "
                "Defaults to smoke + pyperformance."
            ),
        ),
    ] = None,
) -> None:
    """Export metadata dossier JSON from latest benchmark summaries."""
    suites = list(require_suite) if require_suite else None
    try:
        result = export_metadata_dossiers(
            summary_root=summary_root,
            suites=suites,
            output_root=output_root,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(bench_to_json(result))


@research_app.command("extract")
def research_extract(
    repo: Annotated[str, typer.Option(help="Repository key used in output paths")] = "cinderx",
    repo_path: Annotated[Path, typer.Option(help="Path to cloned upstream repo")] = Path(
        ".cache/upstream/cinderx"
    ),
    out: Annotated[Path, typer.Option(help="Output root for introspection JSON")] = Path(
        "data/introspection"
    ),
    render_docs: Annotated[
        bool,
        typer.Option(
            help="Render generated docs under --docs-out after extraction completes.",
        ),
    ] = False,
    docs_out: Annotated[Path, typer.Option(help="Generated docs destination root")] = Path(
        "packages/site/docs/generated"
    ),
) -> None:
    """Extract source inventories and write JSON under data/introspection/<repo>/<sha>."""
    try:
        metadata = extract_metadata(repo=repo, repo_path=repo_path, out_root=out)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(to_json(metadata))
    if render_docs:
        docs = render_docs_from_introspection(
            repo=repo,
            data_root=out,
            docs_root=docs_out,
            commit_sha=metadata.commit_sha,
        )
        typer.echo(to_json(docs))


@research_app.command("render-docs")
def research_render_docs(
    repo: Annotated[
        str,
        typer.Option(help="Repository key used under data/introspection"),
    ] = "cinderx",
    data_root: Annotated[
        Path,
        typer.Option(help="Introspection root path"),
    ] = Path("data/introspection"),
    docs_out: Annotated[Path, typer.Option(help="Generated docs destination root")] = Path(
        "packages/site/docs/generated"
    ),
    commit_sha: Annotated[
        str | None,
        typer.Option(help="Specific commit SHA to render. Defaults to latest snapshot."),
    ] = None,
) -> None:
    """Render MDX pages from previously extracted introspection JSON."""
    try:
        docs = render_docs_from_introspection(
            repo=repo,
            data_root=data_root,
            docs_root=docs_out,
            commit_sha=commit_sha,
        )
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(to_json(docs))


if __name__ == "__main__":
    app()
