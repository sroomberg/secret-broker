"""Typer CLI — equal surface to MCP over the same Broker."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from secret_broker import __version__
from secret_broker.broker import Broker
from secret_broker.cli.format import emit
from secret_broker.config import load_config
from secret_broker.harness.base import Scope
from secret_broker.harness.registry import get_plugin, list_plugins
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

harness_app = typer.Typer(help="Install MCP (+hooks) into agent harnesses.")
app.add_typer(harness_app, name="harness")


def _broker(ctx: typer.Context) -> Broker:
    return ctx.obj["broker"]


def _fmt(ctx: typer.Context) -> str:
    return ctx.obj["format"]


def _broker_command() -> list[str]:
    exe = shutil.which("secret-broker")
    if exe:
        return [exe, "mcp"]
    return ["python3", "-m", "secret_broker", "mcp"]


def _resolve_home(home: str | None) -> Path:
    return Path(home) if home else Path.home()


def _resolve_root(root: str | None) -> Path:
    return Path(root) if root else Path.cwd()


@app.callback()
def main_callback(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None, "--config", envvar="SECRET_BROKER_CONFIG", help="Path to config.toml"
    ),
    format: str | None = typer.Option(None, "--format", help="table|json (default from config)"),
    actor: str = typer.Option("cli", "--actor", help="Audit actor label"),
) -> None:
    cfg = load_config(config)
    fmt = format or cfg.default_format
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["format"] = fmt
    ctx.obj["broker"] = Broker(config=cfg, actor=actor)
    ctx.obj["config_opt"] = config


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
def doctor_cmd(
    ctx: typer.Context,
    home: str | None = typer.Option(None, "--home"),
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Adapter auth, policy files, leak-test, and harness install status."""
    report = _broker(ctx).doctor()
    home_p = _resolve_home(home)
    root_p = _resolve_root(root)
    for plugin in list_plugins():
        st = plugin.status(scope=Scope.USER, root=root_p, home=home_p)
        report["checks"].append(
            {
                "name": f"harness:{plugin.id}:user",
                "ok": True,
                "detail": (f"installed={st.installed} mcp={st.mcp} hooks={st.hooks} ({st.detail})"),
            }
        )
    lines = [
        f"{'PASS' if c['ok'] else 'FAIL':4}  {c['name']}: {c['detail']}" for c in report["checks"]
    ]
    lines.append("")
    lines.append("OK" if report["ok"] else "FAILED")
    emit(report, fmt=_fmt(ctx), human_lines=lines)
    raise typer.Exit(code=0 if report["ok"] else 1)


@harness_app.command("list")
def harness_list(ctx: typer.Context) -> None:
    """List supported agent harness plugins."""
    plugins = list_plugins()
    payload = [
        {
            "id": p.id,
            "name": p.name,
            "supports_mcp": p.supports_mcp,
            "supports_hooks": p.supports_hooks,
        }
        for p in plugins
    ]
    lines = [
        f"{p.id:14}  {p.name:14}  mcp={p.supports_mcp}  hooks={p.supports_hooks}" for p in plugins
    ]
    emit(payload, fmt=_fmt(ctx), human_lines=lines)


@harness_app.command("status")
def harness_status(
    ctx: typer.Context,
    harness: str = typer.Argument(...),
    scope: Scope = typer.Option(Scope.USER, "--scope"),
    home: str | None = typer.Option(None, "--home"),
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Show whether secret-broker is installed for a harness."""
    try:
        plugin = get_plugin(harness)
    except KeyError as exc:
        typer.secho(f"unknown harness: {harness}", err=True)
        raise typer.Exit(code=2) from exc
    st = plugin.status(scope=scope, root=_resolve_root(root), home=_resolve_home(home))
    emit(
        st.model_dump(),
        fmt=_fmt(ctx),
        human_lines=[
            f"{st.harness}: installed={st.installed} mcp={st.mcp} hooks={st.hooks}",
            f"paths: {', '.join(st.paths)}",
            st.detail,
        ],
    )


@harness_app.command("install")
def harness_install(
    ctx: typer.Context,
    harness: str | None = typer.Argument(None),
    all_harnesses: bool = typer.Option(False, "--all", help="Install into every known harness"),
    scope: Scope = typer.Option(Scope.USER, "--scope"),
    hooks: bool = typer.Option(False, "--hooks", help="Also install PreToolUse block hooks"),
    home: str | None = typer.Option(None, "--home"),
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Install MCP server (and optional hooks) into a harness."""
    if all_harnesses:
        targets = list_plugins()
    elif harness:
        try:
            targets = [get_plugin(harness)]
        except KeyError as exc:
            typer.secho(f"unknown harness: {harness}", err=True)
            raise typer.Exit(code=2) from exc
    else:
        typer.secho("provide HARNESS or --all", err=True)
        raise typer.Exit(code=2)

    config_path = ctx.obj.get("config_opt")
    home_p = _resolve_home(home)
    root_p = _resolve_root(root)
    cmd = _broker_command()
    results = []
    for plugin in targets:
        result = plugin.install(
            scope=scope,
            root=root_p,
            home=home_p,
            broker_command=cmd,
            config_path=config_path,
            with_hooks=hooks,
        )
        results.append(result.model_dump())
        typer.secho(
            f"{plugin.id}: mcp={result.mcp_installed} hooks={result.hooks_installed} "
            f"→ {', '.join(result.paths_touched)}",
            fg=typer.colors.GREEN,
        )
    if _fmt(ctx) == "json":
        emit(results, fmt="json")


@harness_app.command("uninstall")
def harness_uninstall(
    ctx: typer.Context,
    harness: str = typer.Argument(...),
    scope: Scope = typer.Option(Scope.USER, "--scope"),
    home: str | None = typer.Option(None, "--home"),
    root: str | None = typer.Option(None, "--root"),
) -> None:
    """Remove secret-broker MCP/hooks from a harness."""
    try:
        plugin = get_plugin(harness)
    except KeyError as exc:
        typer.secho(f"unknown harness: {harness}", err=True)
        raise typer.Exit(code=2) from exc
    result = plugin.uninstall(scope=scope, root=_resolve_root(root), home=_resolve_home(home))
    emit(
        result.model_dump(),
        fmt=_fmt(ctx),
        human_lines=[f"{result.harness}: {result.detail}"],
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
