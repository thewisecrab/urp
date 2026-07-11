from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping
from urllib import error as urlerror
from urllib import parse, request


@dataclass(frozen=True)
class LiveAdapterProfile:
    name: str
    target: str
    kind: str
    operations: list[str]
    required_env: list[str]
    optional_env: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self, env: Mapping[str, str] | None = None) -> Dict[str, Any]:
        current = dict(os.environ if env is None else env)
        missing = [name for name in self.required_env if not current.get(name)]
        return {
            "name": self.name,
            "target": self.target,
            "kind": self.kind,
            "operations": self.operations,
            "required_env": self.required_env,
            "optional_env": self.optional_env,
            "ready": not missing,
            "missing_env": missing,
            "notes": self.notes,
        }


def built_in_live_adapter_profiles() -> Dict[str, LiveAdapterProfile]:
    return {
        "aws_s3": LiveAdapterProfile(
            name="aws_s3",
            target="aws",
            kind="object_store",
            operations=["put_object", "get_object", "head_object", "range_read"],
            required_env=["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "URP_AWS_BUCKET"],
            optional_env=["AWS_SESSION_TOKEN", "AWS_S3_ENDPOINT", "URP_AWS_PREFIX"],
            notes=["Uses AWS Signature Version 4 over HTTPS and is opt-in only."],
        ),
        "postgres_manifest": LiveAdapterProfile(
            name="postgres_manifest",
            target="kubernetes",
            kind="manifest_store",
            operations=["put_manifest", "get_manifest", "list_manifests"],
            required_env=["URP_POSTGRES_DSN"],
            optional_env=["URP_POSTGRES_SCHEMA", "URP_POSTGRES_SSLMODE"],
            notes=["Production manifest backends should use migrations and transactions."],
        ),
        "azure_blob": LiveAdapterProfile(
            name="azure_blob",
            target="azure",
            kind="object_store",
            operations=["put_object", "get_object", "head_object", "range_read"],
            required_env=["AZURE_STORAGE_ACCOUNT", "AZURE_STORAGE_KEY", "URP_AZURE_CONTAINER"],
            optional_env=["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"],
            notes=["Credential-gated adapter contract for Azure Blob Storage."],
        ),
        "gcp_storage": LiveAdapterProfile(
            name="gcp_storage",
            target="gcp",
            kind="object_store",
            operations=["put_object", "get_object", "head_object", "range_read"],
            required_env=["GOOGLE_CLOUD_PROJECT", "URP_GCP_BUCKET"],
            optional_env=["GOOGLE_APPLICATION_CREDENTIALS", "URP_GCP_KMS_KEY", "URP_GCP_PREFIX"],
            notes=["Credential-gated adapter contract for Cloud Storage."],
        ),
        "openai_compatible": LiveAdapterProfile(
            name="openai_compatible",
            target="openai_compatible",
            kind="ai_provider",
            operations=["chat_completions"],
            required_env=["OPENAI_API_KEY"],
            optional_env=["OPENAI_BASE_URL", "URP_OPENAI_MODEL", "URP_AI_MODEL_FRONTIER"],
            notes=["Implemented by OpenAICompatibleProvider in urp.ai_gateway."],
        ),
    }


def live_adapter_readiness(target: str = "all", env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    profiles = built_in_live_adapter_profiles()
    rows = [profile.to_dict(env) for profile in profiles.values() if target == "all" or profile.target == target]
    return {
        "target": target,
        "adapter_count": len(rows),
        "ready_count": sum(1 for row in rows if row["ready"]),
        "adapters": rows,
    }


@dataclass(frozen=True)
class AWSS3Config:
    region: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    endpoint: str = ""
    session_token: str = ""
    prefix: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AWSS3Config":
        current = dict(os.environ if env is None else env)
        missing = [name for name in ["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "URP_AWS_BUCKET"] if not current.get(name)]
        if missing:
            raise ValueError(f"missing AWS S3 adapter environment: {', '.join(missing)}")
        return cls(
            region=current["AWS_REGION"],
            access_key_id=current["AWS_ACCESS_KEY_ID"],
            secret_access_key=current["AWS_SECRET_ACCESS_KEY"],
            bucket=current["URP_AWS_BUCKET"],
            endpoint=current.get("AWS_S3_ENDPOINT", ""),
            session_token=current.get("AWS_SESSION_TOKEN", ""),
            prefix=current.get("URP_AWS_PREFIX", ""),
        )


class AWSS3ObjectAdapter:
    def __init__(self, config: AWSS3Config) -> None:
        self.config = config

    def put_object(self, key: str, body: bytes, metadata: Mapping[str, str] | None = None) -> Dict[str, Any]:
        headers = {f"x-amz-meta-{k.lower()}": str(v) for k, v in dict(metadata or {}).items()}
        response = self._request("PUT", key, body=body, headers=headers)
        return {"bucket": self.config.bucket, "key": self._key(key), "status": response["status"], "etag": response["headers"].get("etag", "")}

    def get_object(self, key: str, byte_range: tuple[int, int] | None = None) -> bytes:
        headers = {}
        if byte_range is not None:
            headers["range"] = f"bytes={byte_range[0]}-{byte_range[1] - 1}"
        return self._request("GET", key, headers=headers)["body"]

    def head_object(self, key: str) -> Dict[str, Any]:
        response = self._request("HEAD", key)
        return {"bucket": self.config.bucket, "key": self._key(key), "status": response["status"], "headers": response["headers"]}

    def _request(self, method: str, key: str, body: bytes = b"", headers: Mapping[str, str] | None = None) -> Dict[str, Any]:
        url = self._url(key)
        signed_headers = self._signed_headers(method, url, body, dict(headers or {}))
        req = request.Request(url, data=body if method != "HEAD" else None, method=method, headers=signed_headers)
        try:
            with request.urlopen(req, timeout=30) as response:  # noqa: S310 - opt-in user configured endpoint
                return {"status": response.status, "headers": {k.lower(): v for k, v in response.headers.items()}, "body": response.read()}
        except urlerror.HTTPError as exc:
            detail = exc.read()
            raise RuntimeError(f"AWS S3 adapter returned HTTP {exc.code}: {detail.decode('utf-8', errors='replace')}") from exc

    def _url(self, key: str) -> str:
        escaped_key = "/".join(parse.quote(part, safe="") for part in self._key(key).split("/"))
        if self.config.endpoint:
            return f"{self.config.endpoint.rstrip('/')}/{self.config.bucket}/{escaped_key}"
        return f"https://{self.config.bucket}.s3.{self.config.region}.amazonaws.com/{escaped_key}"

    def _key(self, key: str) -> str:
        clean_key = key.lstrip("/")
        prefix = self.config.prefix.strip("/")
        return f"{prefix}/{clean_key}" if prefix else clean_key

    def _signed_headers(self, method: str, url: str, body: bytes, headers: Dict[str, str]) -> Dict[str, str]:
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        parsed = parse.urlparse(url)
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_headers = {
            "host": parsed.netloc,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            **{k.lower(): v.strip() for k, v in headers.items()},
        }
        if self.config.session_token:
            canonical_headers["x-amz-security-token"] = self.config.session_token
        signed_names = sorted(canonical_headers)
        canonical_request = "\n".join(
            [
                method,
                parsed.path or "/",
                parsed.query,
                "".join(f"{name}:{canonical_headers[name]}\n" for name in signed_names),
                ";".join(signed_names),
                payload_hash,
            ]
        )
        scope = f"{date_stamp}/{self.config.region}/s3/aws4_request"
        string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()])
        signature = hmac.new(self._signing_key(date_stamp), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            **canonical_headers,
            "authorization": (
                "AWS4-HMAC-SHA256 "
                f"Credential={self.config.access_key_id}/{scope}, "
                f"SignedHeaders={';'.join(signed_names)}, "
                f"Signature={signature}"
            ),
        }

    def _signing_key(self, date_stamp: str) -> bytes:
        key_date = hmac.new(("AWS4" + self.config.secret_access_key).encode("utf-8"), date_stamp.encode("utf-8"), hashlib.sha256).digest()
        key_region = hmac.new(key_date, self.config.region.encode("utf-8"), hashlib.sha256).digest()
        key_service = hmac.new(key_region, b"s3", hashlib.sha256).digest()
        return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


@dataclass(frozen=True)
class AzureBlobConfig:
    account: str
    credential: str
    container: str
    endpoint: str = ""
    prefix: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AzureBlobConfig":
        current = dict(os.environ if env is None else env)
        required = ["AZURE_STORAGE_ACCOUNT", "AZURE_STORAGE_KEY", "URP_AZURE_CONTAINER"]
        missing = [name for name in required if not current.get(name)]
        if missing:
            raise ValueError(f"missing Azure Blob adapter environment: {', '.join(missing)}")
        return cls(
            account=current["AZURE_STORAGE_ACCOUNT"],
            credential=current["AZURE_STORAGE_KEY"],
            container=current["URP_AZURE_CONTAINER"],
            endpoint=current.get("AZURE_STORAGE_BLOB_ENDPOINT", ""),
            prefix=current.get("URP_AZURE_PREFIX", ""),
        )


class AzureBlobObjectAdapter:
    def __init__(self, config: AzureBlobConfig, container_client: Any | None = None) -> None:
        self.config = config
        if container_client is None:
            try:
                from azure.storage.blob import BlobServiceClient  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional cloud dependency
                raise RuntimeError("install urp[cloud] to use Azure Blob Storage") from exc
            endpoint = config.endpoint or f"https://{config.account}.blob.core.windows.net"
            container_client = BlobServiceClient(account_url=endpoint, credential=config.credential).get_container_client(config.container)
        self.container_client = container_client

    def put_object(self, key: str, body: bytes, metadata: Mapping[str, str] | None = None) -> Dict[str, Any]:
        blob_name = self._key(key)
        client = self.container_client.get_blob_client(blob_name)
        response = client.upload_blob(body, overwrite=True, metadata={str(k): str(v) for k, v in dict(metadata or {}).items()})
        etag = getattr(response, "etag", None) or (response.get("etag") if isinstance(response, dict) else "")
        return {"container": self.config.container, "key": blob_name, "etag": str(etag or "")}

    def get_object(self, key: str, byte_range: tuple[int, int] | None = None) -> bytes:
        client = self.container_client.get_blob_client(self._key(key))
        if byte_range is None:
            return bytes(client.download_blob().readall())
        start, end = byte_range
        if start < 0 or end < start:
            raise ValueError("invalid byte range")
        return bytes(client.download_blob(offset=start, length=end - start).readall())

    def head_object(self, key: str) -> Dict[str, Any]:
        properties = self.container_client.get_blob_client(self._key(key)).get_blob_properties()
        return {
            "container": self.config.container,
            "key": self._key(key),
            "size": int(getattr(properties, "size", 0)),
            "etag": str(getattr(properties, "etag", "")),
            "metadata": dict(getattr(properties, "metadata", {}) or {}),
        }

    def _key(self, key: str) -> str:
        clean = key.lstrip("/")
        prefix = self.config.prefix.strip("/")
        return f"{prefix}/{clean}" if prefix else clean


@dataclass(frozen=True)
class GCPStorageConfig:
    project: str
    bucket: str
    prefix: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GCPStorageConfig":
        current = dict(os.environ if env is None else env)
        required = ["GOOGLE_CLOUD_PROJECT", "URP_GCP_BUCKET"]
        missing = [name for name in required if not current.get(name)]
        if missing:
            raise ValueError(f"missing GCP Storage adapter environment: {', '.join(missing)}")
        return cls(current["GOOGLE_CLOUD_PROJECT"], current["URP_GCP_BUCKET"], current.get("URP_GCP_PREFIX", ""))


class GCPStorageObjectAdapter:
    def __init__(self, config: GCPStorageConfig, bucket_client: Any | None = None) -> None:
        self.config = config
        if bucket_client is None:
            try:
                from google.cloud import storage  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional cloud dependency
                raise RuntimeError("install urp[cloud] to use Google Cloud Storage") from exc
            bucket_client = storage.Client(project=config.project).bucket(config.bucket)
        self.bucket_client = bucket_client

    def put_object(self, key: str, body: bytes, metadata: Mapping[str, str] | None = None) -> Dict[str, Any]:
        blob = self.bucket_client.blob(self._key(key))
        blob.metadata = {str(k): str(v) for k, v in dict(metadata or {}).items()}
        blob.upload_from_string(body)
        return {"bucket": self.config.bucket, "key": blob.name, "etag": str(getattr(blob, "etag", "") or "")}

    def get_object(self, key: str, byte_range: tuple[int, int] | None = None) -> bytes:
        blob = self.bucket_client.blob(self._key(key))
        if byte_range is None:
            return bytes(blob.download_as_bytes())
        start, end = byte_range
        if start < 0 or end < start:
            raise ValueError("invalid byte range")
        if end == start:
            return b""
        return bytes(blob.download_as_bytes(start=start, end=end - 1))

    def head_object(self, key: str) -> Dict[str, Any]:
        blob = self.bucket_client.get_blob(self._key(key))
        if blob is None:
            raise KeyError(key)
        return {
            "bucket": self.config.bucket,
            "key": blob.name,
            "size": int(getattr(blob, "size", 0) or 0),
            "etag": str(getattr(blob, "etag", "") or ""),
            "metadata": dict(getattr(blob, "metadata", {}) or {}),
        }

    def _key(self, key: str) -> str:
        clean = key.lstrip("/")
        prefix = self.config.prefix.strip("/")
        return f"{prefix}/{clean}" if prefix else clean
