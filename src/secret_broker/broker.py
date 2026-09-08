"""Broker core — imported by both CLI and MCP so policy is shared."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx

from secret_broker.adapters import build_adapters
from secret_broker.adapters.base import AdapterError, SecretAdapter
from secret_broker.audit import AuditLog
from secret_broker.config import BrokerConfig, load_config
from secret_broker.models import (
    AuditEvent,
    CallResult,
    RunResult,
    SecretMeta,
    StoreStatus,
)
from secret_broker.policy import Policy, PolicyDenied, load_policy, save_policy
from secret_broker.redact import redact_text, scrub_error_message
from secret_broker.refs import SecretRef, parse_ref

InjectStyle = Literal["bearer", "header", "query", "basic"]


class Broker:
    def __init__(
        self,
        config: BrokerConfig | None = None,
        adapters: dict[str, SecretAdapter] | None = None,
        policy: Policy | None = None,
        audit: AuditLog | None = None,
        actor: str = "cli",
    ) -> None:
        self.config = config or load_config()
        self.adapters = adapters if adapters is not None else build_adapters(self.config.stores)
        self.policy = policy or load_policy(
            self.config.policy_path, bootstrap=self.config.policy_bootstrap
        )
        self.audit = audit or AuditLog(self.config.audit_path)
        self.actor = actor

    # --- metadata (never values) ---

    def stores(self) -> list[StoreStatus]:
        return [adapter.health() for adapter in self.adapters.values()]

    def list(self, store: str | None = None) -> list[SecretMeta]:
        metas: list[SecretMeta] = []
        targets = (
            {store: self.adapters[store]}
            if store
            else self.adapters
        )
        if store and store not in self.adapters:
            raise AdapterError(f"unknown store: {store}")
        for adapter in targets.values():
            metas.extend(adapter.list_secrets())
        return metas

    def describe(self, ref_str: str) -> SecretMeta:
        ref = parse_ref(ref_str)
        adapter = self._adapter(ref)
        return adapter.describe(ref)

    # --- operations that resolve secrets in-process only ---

    def call(
        self,
        *,
        url: str,
        ref_str: str,
        method: str = "GET",
        inject: str = "bearer",
        header_name: str | None = None,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout: float = 30.0,
    ) -> CallResult:
        ref = parse_ref(ref_str)
        started = time.perf_counter()
        secrets_used: list[str] = []
        try:
            self.policy.check_host(ref.display(), url)
            self._reject_ssrf(url)
            value = self._resolve(ref)
            secrets_used.append(value)
            req_headers = dict(headers or {})
            req_url = url
            style, _, maybe_name = inject.partition(":")
            style = style.lower()
            name = header_name or (maybe_name if maybe_name else None)

            if style == "bearer":
                req_headers["Authorization"] = f"Bearer {value}"
            elif style == "basic":
                req_headers["Authorization"] = f"Basic {value}"
            elif style == "header":
                if not name:
                    raise ValueError("header inject requires --inject header:Name")
                req_headers[name] = value
            elif style == "query":
                qname = name or "token"
                sep = "&" if urlparse(url).query else "?"
                req_url = f"{url}{sep}{qname}={value}"
            else:
                raise ValueError(f"unsupported inject style: {inject}")

            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                resp = client.request(method.upper(), req_url, headers=req_headers, content=body)
            text, redacted = redact_text(resp.text, secrets_used)
            # Also redact response headers that might echo secrets
            safe_headers = {
                k: redact_text(v, secrets_used)[0]
                for k, v in resp.headers.items()
                if k.lower() not in {"set-cookie", "authorization"}
            }
            duration = int((time.perf_counter() - started) * 1000)
            self.audit.record(
                AuditEvent(
                    actor=self.actor,
                    op="call",
                    ref=ref.display(),
                    destination=url,
                    status="ok",
                    duration_ms=duration,
                    meta={"status_code": resp.status_code, "redacted": redacted},
                )
            )
            return CallResult(
                status_code=resp.status_code,
                headers=safe_headers,
                body=text,
                redacted=redacted,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = int((time.perf_counter() - started) * 1000)
            status = "denied" if isinstance(exc, PolicyDenied) else "error"
            self.audit.record(
                AuditEvent(
                    actor=self.actor,
                    op="call",
                    ref=ref.display() if "ref" in dir() else ref_str,
                    destination=url,
                    status=status,
                    reason=scrub_error_message(exc, secrets_used),
                    duration_ms=duration,
                )
            )
            raise

    def run(
        self,
        command: list[str],
        *,
        env_refs: dict[str, str],
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> RunResult:
        if not command:
            raise ValueError("command required")
        started = time.perf_counter()
        secrets_used: list[str] = []
        refs = {k: parse_ref(v) for k, v in env_refs.items()}
        try:
            for ref in refs.values():
                self.policy.check_bin(ref.display(), command)
            child_env = os.environ.copy()
            for env_name, ref in refs.items():
                value = self._resolve(ref)
                secrets_used.append(value)
                child_env[env_name] = value

            proc = subprocess.run(
                command,
                env=child_env,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            stdout, r1 = redact_text(proc.stdout or "", secrets_used)
            stderr, r2 = redact_text(proc.stderr or "", secrets_used)
            duration = int((time.perf_counter() - started) * 1000)
            self.audit.record(
                AuditEvent(
                    actor=self.actor,
                    op="run",
                    ref=",".join(sorted(r.display() for r in refs.values())),
                    destination=" ".join(command),
                    status="ok" if proc.returncode == 0 else "error",
                    duration_ms=duration,
                    meta={"exit_code": proc.returncode, "redacted": r1 or r2},
                )
            )
            return RunResult(
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                redacted=r1 or r2,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = int((time.perf_counter() - started) * 1000)
            status = "denied" if isinstance(exc, PolicyDenied) else "error"
            self.audit.record(
                AuditEvent(
                    actor=self.actor,
                    op="run",
                    ref=",".join(sorted(r.display() for r in refs.values())) if refs else "",
                    destination=" ".join(command),
                    status=status,
                    reason=scrub_error_message(exc, secrets_used),
                    duration_ms=duration,
                )
            )
            raise

    def policy_show(self) -> dict:
        return self.policy.as_dict()

    def policy_allow_host(self, host: str, ref: str | None = None) -> None:
        self.policy.allow_host(host, ref=ref)
        save_policy(self.config.policy_path, self.policy)

    def policy_allow_bin(self, binary: str, ref: str | None = None) -> None:
        self.policy.allow_bin(binary, ref=ref)
        save_policy(self.config.policy_path, self.policy)

    def audit_tail(self, limit: int = 50) -> list[AuditEvent]:
        return self.audit.read(limit=limit)

    def doctor(self) -> dict:
        """Adapter auth, policy files, and leak-test self-check."""
        checks: list[dict] = []

        # Config
        checks.append(
            {
                "name": "config",
                "ok": True,
                "detail": str(self.config.path) if self.config.path else "defaults (no file)",
            }
        )

        # Policy path
        policy_path = Path(os.path.expanduser(self.config.policy_path))
        checks.append(
            {
                "name": "policy_file",
                "ok": True,
                "detail": f"{policy_path} exists={policy_path.exists()}",
            }
        )

        # Stores
        for status in self.stores():
            checks.append(
                {
                    "name": f"store:{status.name}",
                    "ok": status.health.value in {"ok", "degraded"},
                    "detail": f"{status.type} {status.health}: {status.detail}",
                }
            )

        # Leak self-check using memory adapter
        leak_ok = False
        leak_detail = "memory adapter not configured"
        if "memory" in self.adapters:
            from secret_broker.adapters.memory import MemoryAdapter

            mem = self.adapters["memory"]
            assert isinstance(mem, MemoryAdapter)
            token = "sb-doctor-leak-token-DEADBEEF"
            mem.put("DOCTOR_TOKEN", token)
            # Temporarily allow example.com for this check
            self.policy.allow_host("example.com")
            # Use a local echo via run instead of network
            self.policy.allow_bin("python3")
            result = self.run(
                ["python3", "-c", "import os; print('tok=' + os.environ['T'])"],
                env_refs={"T": "secret://memory/DOCTOR_TOKEN"},
            )
            leak_ok = token not in result.stdout and "[REDACTED]" in result.stdout
            leak_detail = (
                "stdout redacted correctly"
                if leak_ok
                else "LEAK: secret appeared in run stdout before redaction failed"
            )
            if token in result.stdout:
                leak_ok = False
        checks.append({"name": "leak_self_check", "ok": leak_ok, "detail": leak_detail})

        # No get_secret surface
        forbidden = ["get", "cat", "show", "reveal", "export"]
        checks.append(
            {
                "name": "no_reveal_api",
                "ok": not hasattr(self, "get") and not hasattr(self, "reveal"),
                "detail": f"forbidden names reserved: {', '.join(forbidden)}",
            }
        )

        # Optional binaries
        for bin_name in ("op", "vault"):
            checks.append(
                {
                    "name": f"bin:{bin_name}",
                    "ok": True,
                    "detail": "found" if shutil.which(bin_name) else "not on PATH (ok if unused)",
                }
            )

        return {
            "ok": all(
                c["ok"] for c in checks if c["name"] not in {"bin:op", "bin:vault"}
            ),
            "checks": checks,
        }

    def _adapter(self, ref: SecretRef) -> SecretAdapter:
        try:
            return self.adapters[ref.store]
        except KeyError as exc:
            raise AdapterError(f"unknown store: {ref.store}") from exc

    def _resolve(self, ref: SecretRef) -> str:
        return self._adapter(ref).resolve(ref)

    def _reject_ssrf(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise PolicyDenied(f"scheme not allowed: {parsed.scheme}")
        host = (parsed.hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
            raise PolicyDenied("SSRF guard: localhost destinations blocked")
        # Block link-local / metadata IP literals
        if host.startswith("169.254.") or host.startswith("10.") or host.startswith("192.168."):
            raise PolicyDenied("SSRF guard: private IP destinations blocked")
        if host.startswith("172."):
            try:
                second = int(host.split(".")[1])
                if 16 <= second <= 31:
                    raise PolicyDenied("SSRF guard: private IP destinations blocked")
            except (IndexError, ValueError):
                pass
