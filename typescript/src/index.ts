export type Contract = "exact_bytes" | "exact_logical" | "bounded_approx" | "semantic" | "derived" | "tombstone";

export type WorkUnitKind =
  | "byte_object"
  | "file"
  | "directory_snapshot"
  | "block_extent"
  | "backup_snapshot"
  | "container_layer"
  | "structured_file"
  | "table_snapshot"
  | "table_row_group"
  | "stream_segment"
  | "event_batch"
  | "metric_series"
  | "trace_batch"
  | "log_batch"
  | "media_asset"
  | "image_asset"
  | "video_asset"
  | "audio_asset"
  | "document_asset"
  | "vector_index_segment"
  | "embedding_request"
  | "embedding_batch"
  | "prompt_request"
  | "completion_response"
  | "chat_session"
  | "agent_step"
  | "tool_call"
  | "rag_context_pack"
  | "training_dataset"
  | "evaluation_job"
  | "model_checkpoint"
  | "adapter_artifact"
  | "fine_tune_job"
  | "inference_batch"
  | "kv_cache_segment"
  | "synthetic_data_job"
  | "batch_compute_job"
  | "lifecycle_transition"
  | "deletion_candidate"
  | "rehydration_request"
  | "policy_override"
  | "plugin_action";

export interface WorkUnit {
  id?: string;
  traceId: string;
  createdAt: string;
  kind: WorkUnitKind;
  tenant: string;
  namespace: string;
  logicalRef: string;
  requestedContract?: Contract;
  effectiveContract?: Contract;
  metadata: Record<string, unknown>;
  policyContext: Record<string, unknown>;
  payload?: unknown;
  payloadRef?: unknown;
  deadline?: string;
  latencyBudgetMs?: number;
  qualityTarget?: Record<string, unknown>;
}

export interface WorkUnitCreateResult {
  work_unit_id: string;
  trace_id: string;
  state: "received" | string;
}

export interface WorkUnitListQuery {
  tenant?: string;
}

export interface Plan {
  plan_id: string;
  work_unit_id: string;
  trace_id?: string;
  contract: Contract;
  actions: Array<Record<string, unknown>>;
  mode: string;
  policy_bundle_id: string;
  risk: string;
  expected: Record<string, unknown>;
  fallback: string;
}

export interface PlanQuery {
  work_unit_id?: string;
}

export interface ExecutionResult {
  work_unit_id: string;
  manifest_id: string;
  accepted: boolean;
  mode: string;
  output?: unknown;
  details?: Record<string, unknown>;
}

export interface Manifest {
  manifest_id: string;
  work_unit_id: string;
  tenant: string;
  kind: WorkUnitKind;
  contract: Contract;
  logical_ref: string;
  namespace: string;
  trace_id?: string;
  physical?: Record<string, unknown>;
  verification?: Record<string, unknown>;
  telemetry?: Record<string, unknown>;
}

export interface ManifestQuery {
  logical_ref?: string;
  tenant?: string;
  redacted?: boolean;
}

export interface ManifestExportRequest {
  logical_ref?: string;
  tenant?: string;
  redacted?: boolean;
}

export interface ManifestExport {
  manifest_count: number;
  redacted: boolean;
  manifests: Array<Manifest | Record<string, unknown>>;
}

export interface ManifestExploreQuery {
  tenant?: string;
  kind?: WorkUnitKind;
  contract?: Contract;
  state?: string;
  limit?: number;
  redacted?: boolean;
}

export interface ManifestExplorerReport {
  manifest_count: number;
  returned: number;
  filters: Record<string, unknown>;
  by_kind: Record<string, number>;
  by_contract: Record<string, number>;
  by_state: Record<string, number>;
  totals: Record<string, number>;
  rows: Array<Record<string, unknown>>;
}

export interface ManifestRange {
  start: number;
  end: number;
}

export interface ManifestRehydrateOptions {
  range?: ManifestRange;
}

export interface LedgerEvent {
  event_id: string;
  event_type: string;
  tenant: string;
  work_unit_id?: string;
  manifest_id?: string;
  policy_bundle_id?: string;
  trace_id?: string;
  details?: Record<string, unknown>;
}

export interface LedgerQuery {
  tenant?: string;
  work_unit_id?: string;
  manifest_id?: string;
  event_types?: string[];
  limit?: number;
}

export interface StructuredLogEntry {
  log_id: string;
  created_at: string;
  severity: string;
  event_type: string;
  tenant?: string;
  work_unit_id?: string;
  manifest_id?: string;
  policy_bundle_id?: string;
  trace_id?: string;
  error_code?: string;
  message: string;
  details: Record<string, unknown>;
}

export interface LogQuery extends LedgerQuery {
  trace_id?: string;
  severity?: string;
  error_code?: string;
}

export interface ReportQuery {
  tenant?: string;
}

export interface ConformanceResult {
  name: string;
  passed: boolean;
  checks: Record<string, boolean>;
  details: Record<string, unknown>;
}

export interface ProductionReadinessResult {
  name: string;
  passed: boolean;
  checks: Record<string, boolean>;
  details: Record<string, unknown>;
}

export interface PlatformProfile {
  name: string;
  display_name: string;
  category: string;
  deployment_targets: string[];
  storage_backends: string[];
  compute_backends: string[];
  ai_providers: string[];
  required_capabilities: string[];
  required_artifacts: string[];
  live_credential_env: string[];
  optional_env: string[];
  config_keys: string[];
  notes: string[];
}

export interface PlatformReadinessResult {
  target: string;
  contract_ready: boolean;
  live_ready: boolean;
  passed: boolean;
  checks: Record<string, boolean>;
  details: Record<string, unknown>;
}

export interface PlatformReadinessQuery {
  target?: string;
  require_live?: boolean;
}

export interface PlatformMatrix {
  platform_count: number;
  contract_ready_count: number;
  live_ready_count: number;
  targets: PlatformReadinessResult[];
}

export interface PolicyReloadResult {
  name: string;
  version: string;
  reloaded_at: string;
  record_hash_matches: boolean;
  bundle?: Record<string, unknown>;
}

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatCompletionRequest {
  model?: string;
  messages: ChatMessage[];
  temperature?: number;
  tools?: unknown[];
  urp?: Record<string, unknown>;
}

export interface CompletionRequest {
  model?: string;
  prompt: string | string[];
  temperature?: number;
  urp?: Record<string, unknown>;
}

export interface EmbeddingRequest {
  model?: string;
  input: string | string[];
  urp?: Record<string, unknown>;
}

export interface CacheLookupRequest {
  key: string;
  tenant: string;
  namespace?: string;
  source_fingerprints?: string[];
}

export interface CacheLookupResponse {
  hit: boolean;
  value?: unknown;
  reason?: string;
}

export interface CacheStoreRequest extends CacheLookupRequest {
  value: unknown;
  verification: {
    type: "chat_completion" | "embedding_shape" | "json_shape" | "non_empty_text" | "sha256";
    expected?: string;
    required_keys?: string[];
  };
  ttl_seconds?: number;
}

export interface CacheStoreResponse {
  stored: boolean;
  reason?: string;
  verification?: Record<string, unknown>;
}

export interface URPClientOptions {
  apiKey?: string;
  tenant?: string;
  fetch?: typeof globalThis.fetch;
}

export interface Approval {
  approval_id: string;
  tenant: string;
  actor: string;
  contract: Contract;
  policy_bundle_id: string;
  created_at: string;
  expires_at: string;
  work_unit_id?: string;
  reason: string;
  signature: string;
}

export interface ApprovalRequest {
  tenant: string;
  contract: Contract;
  policy_bundle_id: string;
  reason: string;
  work_unit_id?: string;
  ttl_seconds?: number;
}

export interface S3PutObjectRequest {
  bucket: string;
  key: string;
  tenant?: string;
  namespace?: string;
  body_text?: string;
  body_base64?: string;
  metadata?: Record<string, unknown>;
  tags?: Record<string, unknown>;
}

export interface S3ObjectByManifestRequest {
  manifest_id: string;
  tenant?: string;
}

export interface S3RangeRequest extends S3ObjectByManifestRequest {
  start: number;
  end: number;
}

export interface S3ListObjectsRequest {
  tenant?: string;
  bucket?: string;
  prefix?: string;
  include_tombstoned?: boolean;
}

export interface S3DeleteObjectRequest extends S3ObjectByManifestRequest {
  actor?: string;
  allow_delete?: boolean;
}

export interface S3MultipartCreateRequest {
  bucket: string;
  key: string;
  tenant?: string;
  namespace?: string;
  metadata?: Record<string, unknown>;
  tags?: Record<string, unknown>;
}

export interface S3MultipartPartRequest {
  upload_id: string;
  part_number: number;
  tenant?: string;
  body_text?: string;
  body_base64?: string;
}

export class WorkUnitBuilder {
  private value: Partial<WorkUnit>;

  constructor(kind: WorkUnitKind, tenant: string, logicalRef: string) {
    this.value = {
      kind,
      tenant,
      logicalRef,
      namespace: "default",
      metadata: {},
      policyContext: {},
      traceId: newId("tr"),
      createdAt: new Date().toISOString(),
    };
  }

  static byteObject(tenant: string, logicalRef: string, payload?: Uint8Array | string): WorkUnitBuilder {
    return new WorkUnitBuilder("byte_object", tenant, logicalRef).payload(payload);
  }

  static promptRequest(tenant: string, logicalRef = "openai://chat/completions", payload?: unknown): WorkUnitBuilder {
    return new WorkUnitBuilder("prompt_request", tenant, logicalRef).contract("semantic").payload(payload);
  }

  namespace(namespace: string): WorkUnitBuilder {
    this.value.namespace = namespace;
    return this;
  }

  contract(contract: Contract): WorkUnitBuilder {
    this.value.requestedContract = contract;
    return this;
  }

  metadata(key: string, value: unknown): WorkUnitBuilder {
    this.value.metadata = { ...(this.value.metadata ?? {}), [key]: value };
    return this;
  }

  policyContext(key: string, value: unknown): WorkUnitBuilder {
    this.value.policyContext = { ...(this.value.policyContext ?? {}), [key]: value };
    return this;
  }

  payload(payload: unknown): WorkUnitBuilder {
    this.value.payload = payload;
    return this;
  }

  payloadRef(payloadRef: unknown): WorkUnitBuilder {
    this.value.payloadRef = payloadRef;
    return this;
  }

  deadline(deadline: string): WorkUnitBuilder {
    this.value.deadline = deadline;
    return this;
  }

  latencyBudgetMs(value: number): WorkUnitBuilder {
    if (!Number.isInteger(value) || value < 0) throw new Error("latency budget must be a non-negative integer");
    this.value.latencyBudgetMs = value;
    return this;
  }

  qualityTarget(value: Record<string, unknown>): WorkUnitBuilder {
    this.value.qualityTarget = { ...value };
    return this;
  }

  traceId(traceId: string): WorkUnitBuilder {
    this.value.traceId = traceId;
    return this;
  }

  build(): WorkUnit {
    if (!this.value.kind) throw new Error("work unit kind is required");
    if (!this.value.tenant) throw new Error("work unit tenant is required");
    if (!this.value.logicalRef) throw new Error("work unit logicalRef is required");
    return {
      kind: this.value.kind,
      tenant: this.value.tenant,
      logicalRef: this.value.logicalRef,
      namespace: this.value.namespace ?? "default",
      metadata: this.value.metadata ?? {},
      policyContext: this.value.policyContext ?? {},
      traceId: this.value.traceId ?? newId("tr"),
      createdAt: this.value.createdAt ?? new Date().toISOString(),
      ...(this.value.requestedContract ? { requestedContract: this.value.requestedContract } : {}),
      ...(this.value.payload !== undefined ? { payload: this.value.payload } : {}),
      ...(this.value.id ? { id: this.value.id } : {}),
      ...(this.value.payloadRef !== undefined ? { payloadRef: this.value.payloadRef } : {}),
      ...(this.value.effectiveContract ? { effectiveContract: this.value.effectiveContract } : {}),
      ...(this.value.deadline ? { deadline: this.value.deadline } : {}),
      ...(this.value.latencyBudgetMs !== undefined ? { latencyBudgetMs: this.value.latencyBudgetMs } : {}),
      ...(this.value.qualityTarget ? { qualityTarget: this.value.qualityTarget } : {}),
    };
  }
}

export class URPClient {
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(private baseUrl: string, private readonly options: URPClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async createWorkUnit(workUnit: WorkUnit): Promise<WorkUnitCreateResult> {
    const res = await this.request(`${this.baseUrl}/v1/work-units`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(toApiWorkUnit(workUnit)),
    });
    if (!res.ok) throw new Error(`URP create work unit failed: ${res.status}`);
    return res.json();
  }

  async listWorkUnits(query: WorkUnitListQuery = {}): Promise<WorkUnit[]> {
    const url = new URL(`${this.baseUrl}/v1/work-units`);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP list work units failed: ${res.status}`);
    const rows = (await res.json()) as Array<Record<string, unknown>>;
    return rows.map(fromApiWorkUnit);
  }

  async getWorkUnit(workUnitId: string): Promise<WorkUnit> {
    const res = await this.request(`${this.baseUrl}/v1/work-units/${workUnitId}`);
    if (!res.ok) throw new Error(`URP get work unit failed: ${res.status}`);
    return fromApiWorkUnit(await res.json());
  }

  async planWorkUnit(workUnitId: string): Promise<Plan> {
    const res = await this.request(`${this.baseUrl}/v1/work-units/${workUnitId}/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    });
    if (!res.ok) throw new Error(`URP plan work unit failed: ${res.status}`);
    return res.json();
  }

  async executeWorkUnit(workUnitId: string, mode = "enforce"): Promise<ExecutionResult> {
    const res = await this.request(`${this.baseUrl}/v1/work-units/${workUnitId}/execute`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mode }),
    });
    if (!res.ok) throw new Error(`URP execute work unit failed: ${res.status}`);
    return res.json();
  }

  async plan(workUnit: WorkUnit): Promise<Plan> {
    const res = await this.request(`${this.baseUrl}/v1/work-units/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(toApiWorkUnit(workUnit)),
    });
    if (!res.ok) throw new Error(`URP plan failed: ${res.status}`);
    return res.json();
  }

  async createPlan(workUnit: WorkUnit, mode = "observe"): Promise<Plan> {
    const res = await this.request(`${this.baseUrl}/v1/plans`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...toApiWorkUnit(workUnit), mode }),
    });
    if (!res.ok) throw new Error(`URP create plan failed: ${res.status}`);
    return res.json();
  }

  async listPlans(query: PlanQuery = {}): Promise<Plan[]> {
    const url = new URL(`${this.baseUrl}/v1/plans`);
    if (query.work_unit_id) url.searchParams.set("work_unit_id", query.work_unit_id);
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP plan list failed: ${res.status}`);
    return res.json();
  }

  async getPlan(planId: string): Promise<Plan> {
    const res = await this.request(`${this.baseUrl}/v1/plans/${planId}`);
    if (!res.ok) throw new Error(`URP plan get failed: ${res.status}`);
    return res.json();
  }

  async execute(workUnit: WorkUnit, mode = "enforce"): Promise<ExecutionResult> {
    const res = await this.request(`${this.baseUrl}/v1/work-units/execute`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...toApiWorkUnit(workUnit), mode }),
    });
    if (!res.ok) throw new Error(`URP execute failed: ${res.status}`);
    return res.json();
  }

  async manifest(manifestId: string): Promise<Manifest> {
    const res = await this.request(`${this.baseUrl}/v1/manifests/${manifestId}`);
    if (!res.ok) throw new Error(`URP manifest failed: ${res.status}`);
    return res.json();
  }

  async listManifests(query: ManifestQuery = {}): Promise<Array<Manifest | Record<string, unknown>>> {
    const url = new URL(`${this.baseUrl}/v1/manifests`);
    if (query.logical_ref) url.searchParams.set("logical_ref", query.logical_ref);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    if (query.redacted !== undefined) url.searchParams.set("redacted", String(query.redacted));
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP manifest list failed: ${res.status}`);
    return res.json();
  }

  async exportManifests(request: ManifestExportRequest = {}): Promise<ManifestExport> {
    const res = await this.request(`${this.baseUrl}/v1/manifests/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP manifest export failed: ${res.status}`);
    return res.json();
  }

  async exploreManifests(query: ManifestExploreQuery = {}): Promise<ManifestExplorerReport> {
    const url = new URL(`${this.baseUrl}/v1/manifests/explore`);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    if (query.kind) url.searchParams.set("kind", query.kind);
    if (query.contract) url.searchParams.set("contract", query.contract);
    if (query.state) url.searchParams.set("state", query.state);
    if (query.limit !== undefined) url.searchParams.set("limit", String(query.limit));
    if (query.redacted !== undefined) url.searchParams.set("redacted", String(query.redacted));
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP manifest explore failed: ${res.status}`);
    return res.json();
  }

  async rehydrateManifest(manifestId: string, options: ManifestRehydrateOptions = {}): Promise<ArrayBuffer> {
    const res = await this.request(`${this.baseUrl}/v1/manifests/${manifestId}/rehydrate`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(options),
    });
    if (!res.ok) throw new Error(`URP manifest rehydrate failed: ${res.status}`);
    return res.arrayBuffer();
  }

  async ledgerQuery(query: LedgerQuery): Promise<LedgerEvent[]> {
    const res = await this.request(`${this.baseUrl}/v1/ledger/query`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(query),
    });
    if (!res.ok) throw new Error(`URP ledger query failed: ${res.status}`);
    return res.json();
  }

  async logsQuery(query: LogQuery): Promise<StructuredLogEntry[]> {
    const res = await this.request(`${this.baseUrl}/v1/logs/query`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(query),
    });
    if (!res.ok) throw new Error(`URP logs query failed: ${res.status}`);
    return res.json();
  }

  ledgerStreamUrl(query: LedgerQuery = {}): string {
    const url = new URL(`${this.baseUrl}/v1/ledger/stream`);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    if (query.work_unit_id) url.searchParams.set("work_unit_id", query.work_unit_id);
    if (query.manifest_id) url.searchParams.set("manifest_id", query.manifest_id);
    if (query.event_types?.length) url.searchParams.set("event_types", query.event_types.join(","));
    if (query.limit !== undefined) url.searchParams.set("limit", String(query.limit));
    return url.toString();
  }

  async savingsReport(query: ReportQuery = {}): Promise<Record<string, unknown>> {
    const url = new URL(`${this.baseUrl}/v1/reports/savings`);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP savings report failed: ${res.status}`);
    return res.json();
  }

  async dashboardReport(query: ReportQuery = {}): Promise<Record<string, unknown>> {
    const url = new URL(`${this.baseUrl}/v1/reports/dashboard`);
    if (query.tenant) url.searchParams.set("tenant", query.tenant);
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP dashboard report failed: ${res.status}`);
    return res.json();
  }

  async aiConformance(): Promise<ConformanceResult> {
    const res = await this.request(`${this.baseUrl}/v1/conformance/ai`);
    if (!res.ok) throw new Error(`URP AI conformance failed: ${res.status}`);
    return res.json();
  }

  async productionReadiness(): Promise<ProductionReadinessResult> {
    const res = await this.request(`${this.baseUrl}/v1/admin/readiness`);
    if (!res.ok) throw new Error(`URP production readiness failed: ${res.status}`);
    return res.json();
  }

  async platformProfiles(): Promise<PlatformProfile[]> {
    const res = await this.request(`${this.baseUrl}/v1/platforms`);
    if (!res.ok) throw new Error(`URP platform profiles failed: ${res.status}`);
    return res.json();
  }

  async platformReadiness(query: PlatformReadinessQuery = {}): Promise<PlatformReadinessResult | PlatformReadinessResult[]> {
    const url = new URL(`${this.baseUrl}/v1/platforms/readiness`);
    if (query.target) url.searchParams.set("target", query.target);
    if (query.require_live !== undefined) url.searchParams.set("require_live", String(query.require_live));
    const res = await this.request(url);
    if (!res.ok) throw new Error(`URP platform readiness failed: ${res.status}`);
    return res.json();
  }

  async platformMatrix(): Promise<PlatformMatrix> {
    const res = await this.request(`${this.baseUrl}/v1/platforms/matrix`);
    if (!res.ok) throw new Error(`URP platform matrix failed: ${res.status}`);
    return res.json();
  }

  async reloadPolicyBundle(name = "default-safe", actor = "sdk"): Promise<PolicyReloadResult> {
    const res = await this.request(`${this.baseUrl}/v1/policies/bundles/${encodeURIComponent(name)}/reload`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ actor }),
    });
    if (!res.ok) throw new Error(`URP policy reload failed: ${res.status}`);
    return res.json();
  }

  async exactCacheLookup(request: CacheLookupRequest): Promise<CacheLookupResponse> {
    const res = await this.request(`${this.baseUrl}/v1/cache/exact/lookup`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP exact cache lookup failed: ${res.status}`);
    return res.json();
  }

  async storeCacheEntry(request: CacheStoreRequest): Promise<CacheStoreResponse> {
    const res = await this.request(`${this.baseUrl}/v1/cache/store`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP cache store failed: ${res.status}`);
    return res.json();
  }

  async s3PutObject(request: S3PutObjectRequest): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/objects", request, "URP S3 put object failed");
  }

  async s3HeadObject(request: S3ObjectByManifestRequest): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/objects/head", request, "URP S3 head object failed");
  }

  async s3GetObject(request: S3ObjectByManifestRequest): Promise<ArrayBuffer> {
    return this.postBytes("/v1/s3/objects/get", request, "URP S3 get object failed");
  }

  async s3RangeRead(request: S3RangeRequest): Promise<ArrayBuffer> {
    return this.postBytes("/v1/s3/objects/range", request, "URP S3 range read failed");
  }

  async s3ListObjects(request: S3ListObjectsRequest = {}): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/objects/list", request, "URP S3 list objects failed");
  }

  async s3DeleteObject(request: S3DeleteObjectRequest): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/objects/delete", request, "URP S3 delete object failed");
  }

  async s3CreateMultipartUpload(request: S3MultipartCreateRequest): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/multipart/create", request, "URP S3 multipart create failed");
  }

  async s3UploadMultipartPart(request: S3MultipartPartRequest): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/multipart/part", request, "URP S3 multipart part failed");
  }

  async s3CompleteMultipartUpload(uploadId: string, tenant?: string): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/multipart/complete", { upload_id: uploadId, tenant }, "URP S3 multipart complete failed");
  }

  async s3AbortMultipartUpload(uploadId: string, tenant?: string): Promise<Record<string, unknown>> {
    return this.postJson("/v1/s3/multipart/abort", { upload_id: uploadId, tenant }, "URP S3 multipart abort failed");
  }

  async chatCompletions(request: ChatCompletionRequest): Promise<Record<string, unknown>> {
    const res = await this.request(`${this.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP chat completion failed: ${res.status}`);
    return res.json();
  }

  async completions(request: CompletionRequest): Promise<Record<string, unknown>> {
    const res = await this.request(`${this.baseUrl}/v1/completions`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP completion failed: ${res.status}`);
    return res.json();
  }

  async embeddings(request: EmbeddingRequest): Promise<Record<string, unknown>> {
    const res = await this.request(`${this.baseUrl}/v1/embeddings`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw new Error(`URP embeddings failed: ${res.status}`);
    return res.json();
  }

  async models(): Promise<Record<string, unknown>> {
    const res = await this.request(`${this.baseUrl}/v1/models`);
    if (!res.ok) throw new Error(`URP models failed: ${res.status}`);
    return res.json();
  }

  async issueApproval(request: ApprovalRequest): Promise<Approval> {
    const res = await this.request(`${this.baseUrl}/v1/approvals`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!res.ok) throw await responseError("URP approval issue failed", res);
    return res.json();
  }

  async listApprovals(tenant?: string): Promise<Approval[]> {
    const url = new URL(`${this.baseUrl}/v1/approvals`);
    if (tenant) url.searchParams.set("tenant", tenant);
    const res = await this.request(url);
    if (!res.ok) throw await responseError("URP approval list failed", res);
    return res.json();
  }

  private async postJson(path: string, payload: unknown, message: string): Promise<Record<string, unknown>> {
    const res = await this.request(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`${message}: ${res.status}`);
    return res.json();
  }

  private async postBytes(path: string, payload: unknown, message: string): Promise<ArrayBuffer> {
    const res = await this.request(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw await responseError(message, res);
    return res.arrayBuffer();
  }

  private request(input: string | URL | Request, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    if (this.options.apiKey && !headers.has("authorization")) {
      headers.set("authorization", `Bearer ${this.options.apiKey}`);
    }
    if (this.options.tenant && !headers.has("x-urp-tenant")) {
      headers.set("x-urp-tenant", this.options.tenant);
    }
    return this.fetchImpl(input, { ...init, headers });
  }
}

export function toApiWorkUnit(workUnit: WorkUnit): Record<string, unknown> {
  return {
    id: workUnit.id,
    kind: workUnit.kind,
    tenant: workUnit.tenant,
    namespace: workUnit.namespace ?? "default",
    logical_ref: workUnit.logicalRef,
    payload: encodeJsonValue(workUnit.payload),
    payload_ref: encodeJsonValue(workUnit.payloadRef),
    requested_contract: workUnit.requestedContract,
    effective_contract: workUnit.effectiveContract,
    metadata: workUnit.metadata ?? {},
    policy_context: workUnit.policyContext ?? {},
    trace_id: workUnit.traceId,
    created_at: workUnit.createdAt,
    deadline: workUnit.deadline,
    latency_budget_ms: workUnit.latencyBudgetMs,
    quality_target: workUnit.qualityTarget ?? {},
  };
}

export function fromApiWorkUnit(data: Record<string, unknown>): WorkUnit {
  return {
    kind: data.kind as WorkUnitKind,
    tenant: data.tenant as string,
    namespace: (data.namespace as string | undefined) ?? "default",
    logicalRef: data.logical_ref as string,
    payload: decodeJsonValue(data.payload),
    ...(data.payload_ref !== undefined ? { payloadRef: decodeJsonValue(data.payload_ref) } : {}),
    metadata: (data.metadata as Record<string, unknown> | undefined) ?? {},
    policyContext: (data.policy_context as Record<string, unknown> | undefined) ?? {},
    traceId: (data.trace_id as string | undefined) ?? newId("tr"),
    createdAt: (data.created_at as string | undefined) ?? new Date().toISOString(),
    ...(typeof data.id === "string" ? { id: data.id } : {}),
    ...(typeof data.requested_contract === "string" ? { requestedContract: data.requested_contract as Contract } : {}),
    ...(typeof data.effective_contract === "string" ? { effectiveContract: data.effective_contract as Contract } : {}),
    ...(typeof data.deadline === "string" ? { deadline: data.deadline } : {}),
    ...(typeof data.latency_budget_ms === "number" ? { latencyBudgetMs: data.latency_budget_ms } : {}),
    ...(data.quality_target && typeof data.quality_target === "object" ? { qualityTarget: data.quality_target as Record<string, unknown> } : {}),
  };
}

function newId(prefix: string): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && "randomUUID" in cryptoApi) {
    return `${prefix}_${cryptoApi.randomUUID().replace(/-/g, "")}`;
  }
  return `${prefix}_${Math.random().toString(16).slice(2)}${Date.now().toString(16)}`;
}

function encodeJsonValue(value: unknown): unknown {
  if (value instanceof Uint8Array) {
    return { _urp_encoding: "base64", data: bytesToBase64(value) };
  }
  if (Array.isArray(value)) return value.map(encodeJsonValue);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, encodeJsonValue(item)]));
  }
  return value;
}

function decodeJsonValue(value: unknown): unknown {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    if (record._urp_encoding === "base64" && typeof record.data === "string" && Object.keys(record).length === 2) {
      return base64ToBytes(record.data);
    }
    return Object.fromEntries(Object.entries(record).map(([key, item]) => [key, decodeJsonValue(item)]));
  }
  if (Array.isArray(value)) return value.map(decodeJsonValue);
  return value;
}

function bytesToBase64(value: Uint8Array): string {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return globalThis.btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  const binary = globalThis.atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function responseError(prefix: string, response: Response): Promise<Error> {
  const body = (await response.text()).slice(0, 64 * 1024);
  return new Error(`${prefix}: ${response.status}${body ? ` ${body}` : ""}`);
}
