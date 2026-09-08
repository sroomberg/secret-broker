"""Typer CLI — equal surface to MCP over the same Broker."""

from __future__ import annotations

import typer

from secret_broker import __version__
from secret_broker.broker import Broker
from secret_broker.cli.format import emit
from secret_broker.config import load_config
from secret_broker.policy import PolicyDenied

app = typer.Typer(
    name="secret-broker",
    help=(
        "Federated secret facade for AI agents. "
        "References in; values never printed. No get/cat/show/reveal."
    ),
    add_completion=True,
    no_args_is_help=True,
)

policy_app = typer.Typer(help="Show and update destination allowlists.")
app.add_typer(policy_app, name="policy")


def _broker(ctx: typer.Context) -> Broker:
    return ctx.obj["broker"]


def _fmt(ctx: typer.Context) -> str:
    return ctx.obj["format"]


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", envvar="SECRET_BROKER_CONFIG", help="Path to config.toml"
    ),
    format: str | None = typer.Option(
        None, "--format", help="table|json (default from config)"
    ),
    actor: str = typer.Option("cli", "--actor", help="Audit actor label"),
) -> None:
    cfg = load_config(config)
    fmt = format or cfg.default_format
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["format"] = fmt
    ctx.obj["broker"] = Broker(config=cfg, actor=actor)


@app.command("version")
def version_cmd() -> None:
    typer.echo(__version__)


@app.command("list")
def list_cmd(
    ctx: typer.Context,
    store: str | None = typer.Option(None, "--store", help="Limit to one store alias"),
) -> None:
    """List secret names/metadata — never values."""
    metas = _broker(ctx).list(store=store)
    payload = [m.model_dump() for m in metas]
    lines = [f"{m.ref:50}  {m.backend:20}  ops={','.join(m.allowed_ops)}" for m in metas]
    if not lines:
        lines = ["(no secrets listed — some adapters require explicit refs)"]
    emit(payload, fmt=_fmt(ctx), human_lines=lines)


@app.command("describe")
def describe_cmd(ctx: typer.Context, ref: str = typer.Argument(..., help="secret://...")) -> None:
    """Describe a ref — never the value."""
    meta = _broker(ctx).describe(ref)
    emit(
        meta.model_dump(),
        fmt=_fmt(ctx),
        human_lines=[
            f"name:    {meta.name}",
            f"ref:     {meta.ref}",
            f"store:   {meta.store}",
            f"backend: {meta.backend}",
            f"ops:     {', '.join(meta.allowed_ops)}",
        ],
    )


@app.command("call")
def call_cmd(
    ctx: typer.Context,
    url: str = typer.Option(..., "--url"),
    ref: str = typer.Option(..., "--ref", help="secret://..."),
    method: str = typer.Option("GET", "--method", "-X"),
    inject: str = typer.Option(
        "bearer",
        "--inject",
        help="bearer | header:Name | query[:name] | basic",
    ),
    header: list[str] | None = typer.Option(
        None, "--header", "-H", help="Extra request header Name: value"
    ),
    body: str | None = typer.Option(None, "--body", "-d"),
) -> None:
    """HTTP inject: resolve secret in-process, print redacted response only."""
    headers: dict[str, str] = {}
    for h in header or []:
        if ":" not in h:
            raise typer.BadParameter(f"header must be Name: value, got {h!r}")
        k, v = h.split(":", 1)
        headers[k.strip()] = v.strip()
    try:
        result = _broker(ctx).call(
            url=url, ref_str=ref, method=method, inject=inject, headers=headers, body=body
        )
    except PolicyDenied as exc:
        typer.secho(f"denied: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    payload = result.model_dump()
    emit(
        payload,
        fmt=_fmt(ctx),
        human_lines=[
            f"HTTP {result.status_code}  redacted={result.redacted}  {result.duration_ms}ms",
            result.body,
        ],
    )


@app.command(
    "run",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def run_cmd(
    ctx: typer.Context,
    ref: list[str] | None = typer.Option(
        None,
        "--ref",
        help="ENV_NAME=secret://... (repeatable)",
    ),
) -> None:
    """Spawn a command with env inject; scrub stdout/stderr. Use: run --ref N=secret://... -- cmd"""
    command = list(ctx.args)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        typer.secho("usage: secret-broker run --ref NAME=secret://... -- <command>", err=True)
        raise typer.Exit(code=2)

    env_refs: dict[str, str] = {}
    for item in ref or []:
        if "=" not in item:
            raise typer.BadParameter("--ref must be NAME=secret://...")
        name, value = item.split("=", 1)
        env_refs[name] = value

    try:
        result = _broker(ctx).run(command, env_refs=env_refs)
    except PolicyDenied as exc:
        typer.secho(f"denied: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    if _fmt(ctx) == "json":
        emit(result.model_dump(), fmt="json")
    else:
        if result.stdout:
            typer.echo(result.stdout, nl=False)
        if result.stderr:
            typer.echo(result.stderr, nl=False, err=True)
    raise typer.Exit(code=result.exit_code)


@policy_app.command("show")
def policy_show(ctx: typer.Context) -> None:
    data = _broker(ctx).policy_show()
    emit(data, fmt=_fmt(ctx))


@policy_app.command("allow-host")
def policy_allow_host(
    ctx: typer.Context,
    host: str = typer.Argument(...),
    ref: str | None = typer.Option(None, "--ref"),
) -> None:
    _broker(ctx).policy_allow_host(host, ref=ref)
    typer.secho(f"allowed host {host}" + (f" for {ref}" if ref else ""), fg=typer.colors.GREEN)


@policy_app.command("allow-bin")
def policy_allow_bin(
    ctx: typer.Context,
    binary: str = typer.Argument(...),
    ref: str | None = typer.Option(None, "--ref"),
) -> None:
    _broker(ctx).policy_allow_bin(binary, ref=ref)
    typer.secho(f"allowed bin {binary}" + (f" for {ref}" if ref else ""), fg=typer.colors.GREEN)


@app.command("audit")
def audit_cmd(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Show recent audit events (no value field)."""
    events = _broker(ctx).audit_tail(limit=limit)
    payload = [e.model_dump(mode="json") for e in events]
    lines = [
        f"{e.timestamp.isoformat()}  {e.op:4}  {e.status:6}  {e.ref}  →  {e.destination}"
        for e in events
    ] or ["(empty audit log)"]
    emit(payload, fmt=_fmt(ctx), human_lines=lines)


@app.command("stores")
def stores_cmd(ctx: typer.Context) -> None:
    """Configured adapters and health."""
    statuses = _broker(ctx).stores()
    payload = [s.model_dump() for s in statuses]
    lines = [f"{s.name:12}  {s.type:22}  {s.health.value:12}  {s.detail}" for s in statuses]
    emit(payload, fmt=_fmt(ctx), human_lines=lines or ["(no stores configured)"])


@app.command("mcp")
def mcp_cmd(ctx: typer.Context) -> None:
    """Run the stdio MCP server (what Cursor launches)."""
    from secret_broker.mcp_server import run_mcp

    run_mcp(broker=_broker(ctx))


@app.command("doctor")
def doctor_cmd(ctx: typer.Context) -> None:
    """Adapter auth, policy files, leak-test self-check."""
    report = _broker(ctx).doctor()
    lines = [
        f"{'PASS' if c['ok'] else 'FAIL':4}  {c['name']}: {c['detail']}" for c in report["checks"]
    ]
    lines.append("")
    lines.append("OK" if report["ok"] else "FAILED")
    emit(report, fmt=_fmt(ctx), human_lines=lines)
    raise typer.Exit(code=0 if report["ok"] else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
