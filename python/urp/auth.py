from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from contextvars import Token
from dataclasses import dataclass, field
from typing import Dict, Iterable, Mapping, Set
from typing import Iterator

from .errors import URPError, authentication_required, tenant_mismatch


@dataclass(frozen=True)
class Principal:
    actor: str
    tenant: str
    roles: Set[str] = field(default_factory=set)


_CURRENT_PRINCIPAL: ContextVar[Principal | None] = ContextVar("urp_current_principal", default=None)


class LocalAuthorizer:
    """Local RBAC with explicit tenant boundaries.

    Authentication is handled separately by ``APIKeyAuthenticator``. A role
    never grants cross-tenant access unless the principal is bound to tenant
    ``*``.
    """

    def __init__(self, role_permissions: Dict[str, Iterable[str]] | None = None) -> None:
        self.role_permissions = {
            "admin": {"*"},
            "operator": {
                "work_unit:read",
                "work_unit:write",
                "manifest:read",
                "manifest:rehydrate",
                "manifest:sensitive",
                "ledger:query",
                "policy:evaluate",
                "cache:use",
                "object:read",
                "object:write",
                "scheduler:submit",
                "reports:read",
                "observability:read",
                "auth:self",
                "approval:read",
            },
            "viewer": {
                "work_unit:read",
                "manifest:read",
                "ledger:query",
                "reports:read",
                "observability:read",
                "auth:self",
            },
            "developer": {
                "work_unit:read",
                "work_unit:write",
                "manifest:read",
                "manifest:rehydrate",
                "manifest:sensitive",
                "cache:use",
                "object:read",
                "object:write",
                "auth:self",
            },
            "gateway": {"work_unit:write", "manifest:read", "cache:use", "object:read", "object:write", "auth:self"},
        }
        if role_permissions:
            self.role_permissions.update({role: set(perms) for role, perms in role_permissions.items()})

    def allowed(self, principal: Principal, action: str, tenant: str | None = None) -> bool:
        if tenant and principal.tenant not in {tenant, "*"}:
            return False
        for role in principal.roles:
            permissions = self.role_permissions.get(role, set())
            if "*" in permissions or action in permissions:
                return True
        return False

    def require(self, principal: Principal, action: str, tenant: str | None = None) -> None:
        if tenant and principal.tenant not in {tenant, "*"}:
            raise tenant_mismatch(principal.tenant, tenant)
        if not self.allowed(principal, action, tenant):
            raise URPError("authorization_denied", f"{principal.actor} is not allowed to perform {action}", retryable=False)


class APIKeyAuthenticator:
    def __init__(self, records: Mapping[str, Principal] | None = None, *, disabled: bool = False) -> None:
        self.disabled = disabled
        self._records = {
            _token_hash(token): principal
            for token, principal in dict(records or {}).items()
            if token
        }

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "APIKeyAuthenticator":
        current = dict(os.environ if env is None else env)
        mode = current.get("URP_AUTH_MODE", "required").strip().lower()
        if mode == "disabled":
            return cls(disabled=True)
        records: Dict[str, Principal] = {}
        local_key = current.get("URP_LOCAL_API_KEY")
        if local_key:
            records[local_key] = Principal(current.get("URP_LOCAL_ACTOR", "local-admin"), "*", {"admin"})
        raw = current.get("URP_API_KEYS_JSON")
        if raw:
            decoded = json.loads(raw)
            if not isinstance(decoded, dict):
                raise ValueError("URP_API_KEYS_JSON must be an object keyed by API token")
            for token, value in decoded.items():
                if not isinstance(value, dict):
                    raise ValueError("each URP_API_KEYS_JSON value must be an object")
                actor = str(value.get("actor") or "api-client")
                tenant = str(value.get("tenant") or "")
                roles = {str(role) for role in value.get("roles", [])}
                if not tenant or not roles:
                    raise ValueError("configured API keys require tenant and roles")
                records[str(token)] = Principal(actor, tenant, roles)
        return cls(records)

    @property
    def configured(self) -> bool:
        return self.disabled or bool(self._records)

    def authenticate(self, api_key: str | None) -> Principal:
        if self.disabled:
            return Principal("anonymous-local", "*", {"admin"})
        if not api_key:
            raise authentication_required()
        principal = self._records.get(_token_hash(api_key))
        if principal is None:
            raise authentication_required("invalid API key")
        return principal


def principal_from_api_key(
    api_key: str | None,
    tenant: str = "local",
    authenticator: APIKeyAuthenticator | None = None,
) -> Principal:
    principal = (authenticator or APIKeyAuthenticator.from_env()).authenticate(api_key)
    if principal.tenant not in {tenant, "*"}:
        raise tenant_mismatch(principal.tenant, tenant)
    return principal


def bearer_token(authorization: str | None, api_key_header: str | None = None) -> str | None:
    if api_key_header:
        return api_key_header.strip() or None
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise authentication_required("expected Authorization: Bearer <token>")
    return value.strip()


def action_for_request(method: str, path: str) -> str:
    normalized_method = method.upper()
    if path == "/metrics":
        return "admin:manage"
    if path.startswith("/v1/admin/") or path.startswith("/v1/kms/"):
        return "admin:manage"
    if path == "/v1/auth/check":
        return "auth:self"
    if path.startswith("/v1/approvals"):
        return "approval:read" if normalized_method == "GET" else "approval:manage"
    if path.startswith("/v1/plugins"):
        return "plugin:manage" if normalized_method != "GET" else "plugin:read"
    if path.startswith("/v1/policies/bundles"):
        return "policy:manage" if normalized_method != "GET" else "policy:read"
    if path.startswith("/v1/policies"):
        return "policy:evaluate"
    if path.startswith("/v1/ledger"):
        return "ledger:query"
    if path.startswith("/v1/manifests"):
        return "manifest:rehydrate" if path.endswith("/rehydrate") else "manifest:read"
    if path.startswith("/v1/work-units") or path.startswith("/v1/plans"):
        return "work_unit:read" if normalized_method == "GET" else "work_unit:write"
    if path.startswith("/v1/s3/objects/delete"):
        return "object:delete"
    if path.startswith("/v1/s3"):
        return "object:read" if any(token in path for token in ("/get", "/head", "/range", "/list")) else "object:write"
    if path.startswith("/v1/cache") or path.startswith("/v1/chat") or path.startswith("/v1/completions") or path.startswith("/v1/embeddings"):
        return "cache:use"
    if path.startswith("/v1/scheduler"):
        return "scheduler:submit" if normalized_method != "GET" else "reports:read"
    if path.startswith("/v1/reports"):
        return "reports:read"
    if path.startswith("/v1/traces") or path.startswith("/v1/logs") or path.startswith("/v1/routes"):
        return "observability:read"
    if path.startswith("/v1/platforms") or path.startswith("/v1/conformance") or path.startswith("/v1/adapters") or path.startswith("/v1/benchmarks"):
        return "admin:manage"
    if path == "/v1/models":
        return "cache:use"
    return "admin:manage"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@contextmanager
def principal_context(principal: Principal) -> Iterator[Principal]:
    token = _CURRENT_PRINCIPAL.set(principal)
    try:
        yield principal
    finally:
        _CURRENT_PRINCIPAL.reset(token)


def current_principal() -> Principal | None:
    return _CURRENT_PRINCIPAL.get()


def current_tenant() -> str | None:
    principal = current_principal()
    if principal is None or principal.tenant == "*":
        return None
    return principal.tenant


def bind_principal(principal: Principal) -> Token:
    return _CURRENT_PRINCIPAL.set(principal)


def reset_principal(token: Token) -> None:
    _CURRENT_PRINCIPAL.reset(token)
