package urp

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type Contract string

const (
	ExactBytes    Contract = "exact_bytes"
	ExactLogical  Contract = "exact_logical"
	BoundedApprox Contract = "bounded_approx"
	Semantic      Contract = "semantic"
	Derived       Contract = "derived"
	Tombstone     Contract = "tombstone"
)

type WorkUnit struct {
	ID                string         `json:"id,omitempty"`
	TraceID           string         `json:"trace_id,omitempty"`
	CreatedAt         string         `json:"created_at,omitempty"`
	Kind              string         `json:"kind"`
	Tenant            string         `json:"tenant"`
	Namespace         string         `json:"namespace,omitempty"`
	LogicalRef        string         `json:"logical_ref"`
	RequestedContract Contract       `json:"requested_contract,omitempty"`
	EffectiveContract Contract       `json:"effective_contract,omitempty"`
	Metadata          map[string]any `json:"metadata,omitempty"`
	PolicyContext     map[string]any `json:"policy_context,omitempty"`
	Payload           any            `json:"payload,omitempty"`
	PayloadRef        any            `json:"payload_ref,omitempty"`
	Deadline          string         `json:"deadline,omitempty"`
	LatencyBudgetMS   *int           `json:"latency_budget_ms,omitempty"`
	QualityTarget     map[string]any `json:"quality_target,omitempty"`
}

func (w WorkUnit) MarshalJSON() ([]byte, error) {
	type workUnitAlias WorkUnit
	encoded, err := json.Marshal(workUnitAlias(w))
	if err != nil {
		return nil, err
	}
	var value map[string]any
	if err := json.Unmarshal(encoded, &value); err != nil {
		return nil, err
	}
	if w.Payload != nil {
		value["payload"] = encodeJSONValue(w.Payload)
	}
	if w.PayloadRef != nil {
		value["payload_ref"] = encodeJSONValue(w.PayloadRef)
	}
	return json.Marshal(value)
}

func (w *WorkUnit) UnmarshalJSON(data []byte) error {
	type workUnitAlias WorkUnit
	var value map[string]any
	if err := json.Unmarshal(data, &value); err != nil {
		return err
	}
	payload, err := decodeJSONValue(value["payload"])
	if err != nil {
		return fmt.Errorf("decode work unit payload: %w", err)
	}
	payloadRef, err := decodeJSONValue(value["payload_ref"])
	if err != nil {
		return fmt.Errorf("decode work unit payload_ref: %w", err)
	}
	delete(value, "payload")
	delete(value, "payload_ref")
	normalized, err := json.Marshal(value)
	if err != nil {
		return err
	}
	var alias workUnitAlias
	if err := json.Unmarshal(normalized, &alias); err != nil {
		return err
	}
	*w = WorkUnit(alias)
	w.Payload = payload
	w.PayloadRef = payloadRef
	return nil
}

type WorkUnitBuilder struct {
	wu WorkUnit
}

type WorkUnitCreateResult struct {
	WorkUnitID string `json:"work_unit_id"`
	TraceID    string `json:"trace_id"`
	State      string `json:"state"`
}

type WorkUnitListQuery struct {
	Tenant string
}

type PlanQuery struct {
	WorkUnitID string
}

func NewWorkUnitBuilder(kind, tenant, logicalRef string) *WorkUnitBuilder {
	return &WorkUnitBuilder{wu: WorkUnit{
		Kind:          kind,
		Tenant:        tenant,
		LogicalRef:    logicalRef,
		Namespace:     "default",
		TraceID:       newID("tr"),
		CreatedAt:     time.Now().UTC().Format(time.RFC3339Nano),
		Metadata:      map[string]any{},
		PolicyContext: map[string]any{},
	}}
}

func ByteObjectWorkUnit(tenant, logicalRef string, payload any) *WorkUnitBuilder {
	return NewWorkUnitBuilder("byte_object", tenant, logicalRef).Payload(payload)
}

func PromptRequestWorkUnit(tenant, logicalRef string, payload any) *WorkUnitBuilder {
	if logicalRef == "" {
		logicalRef = "openai://chat/completions"
	}
	return NewWorkUnitBuilder("prompt_request", tenant, logicalRef).Contract(Semantic).Payload(payload)
}

func (b *WorkUnitBuilder) Namespace(namespace string) *WorkUnitBuilder {
	b.wu.Namespace = namespace
	return b
}

func (b *WorkUnitBuilder) Contract(contract Contract) *WorkUnitBuilder {
	b.wu.RequestedContract = contract
	return b
}

func (b *WorkUnitBuilder) Metadata(key string, value any) *WorkUnitBuilder {
	if b.wu.Metadata == nil {
		b.wu.Metadata = map[string]any{}
	}
	b.wu.Metadata[key] = value
	return b
}

func (b *WorkUnitBuilder) PolicyContext(key string, value any) *WorkUnitBuilder {
	if b.wu.PolicyContext == nil {
		b.wu.PolicyContext = map[string]any{}
	}
	b.wu.PolicyContext[key] = value
	return b
}

func (b *WorkUnitBuilder) Payload(payload any) *WorkUnitBuilder {
	b.wu.Payload = payload
	return b
}

func (b *WorkUnitBuilder) PayloadRef(payloadRef any) *WorkUnitBuilder {
	b.wu.PayloadRef = payloadRef
	return b
}

func (b *WorkUnitBuilder) Deadline(deadline string) *WorkUnitBuilder {
	b.wu.Deadline = deadline
	return b
}

func (b *WorkUnitBuilder) LatencyBudget(milliseconds int) *WorkUnitBuilder {
	b.wu.LatencyBudgetMS = &milliseconds
	return b
}

func (b *WorkUnitBuilder) QualityTarget(target map[string]any) *WorkUnitBuilder {
	b.wu.QualityTarget = target
	return b
}

func (b *WorkUnitBuilder) TraceID(traceID string) *WorkUnitBuilder {
	b.wu.TraceID = traceID
	return b
}

func (b *WorkUnitBuilder) Build() (WorkUnit, error) {
	if strings.TrimSpace(b.wu.Kind) == "" {
		return WorkUnit{}, fmt.Errorf("work unit kind is required")
	}
	if strings.TrimSpace(b.wu.Tenant) == "" {
		return WorkUnit{}, fmt.Errorf("work unit tenant is required")
	}
	if strings.TrimSpace(b.wu.LogicalRef) == "" {
		return WorkUnit{}, fmt.Errorf("work unit logical_ref is required")
	}
	if b.wu.Namespace == "" {
		b.wu.Namespace = "default"
	}
	if b.wu.TraceID == "" {
		b.wu.TraceID = newID("tr")
	}
	if b.wu.CreatedAt == "" {
		b.wu.CreatedAt = time.Now().UTC().Format(time.RFC3339Nano)
	}
	if b.wu.LatencyBudgetMS != nil && *b.wu.LatencyBudgetMS < 0 {
		return WorkUnit{}, fmt.Errorf("work unit latency budget must be non-negative")
	}
	return b.wu, nil
}

type ExecutionResult struct {
	WorkUnitID string         `json:"work_unit_id"`
	ManifestID string         `json:"manifest_id"`
	Accepted   bool           `json:"accepted"`
	Mode       string         `json:"mode"`
	Output     any            `json:"output,omitempty"`
	Details    map[string]any `json:"details,omitempty"`
}

type Manifest struct {
	ManifestID   string         `json:"manifest_id"`
	WorkUnitID   string         `json:"work_unit_id"`
	Tenant       string         `json:"tenant"`
	Kind         string         `json:"kind"`
	Contract     Contract       `json:"contract"`
	LogicalRef   string         `json:"logical_ref"`
	Namespace    string         `json:"namespace"`
	TraceID      string         `json:"trace_id,omitempty"`
	Physical     map[string]any `json:"physical,omitempty"`
	Verification map[string]any `json:"verification,omitempty"`
	Telemetry    map[string]any `json:"telemetry,omitempty"`
}

type ManifestQuery struct {
	LogicalRef string
	Tenant     string
	Redacted   bool
}

type ManifestExportRequest struct {
	LogicalRef string `json:"logical_ref,omitempty"`
	Tenant     string `json:"tenant,omitempty"`
	Redacted   *bool  `json:"redacted,omitempty"`
}

type ManifestExport struct {
	ManifestCount int              `json:"manifest_count"`
	Redacted      bool             `json:"redacted"`
	Manifests     []map[string]any `json:"manifests"`
}

type ManifestExploreQuery struct {
	Tenant   string
	Kind     string
	Contract Contract
	State    string
	Limit    int
	Redacted *bool
}

type ManifestExplorerReport struct {
	ManifestCount int              `json:"manifest_count"`
	Returned      int              `json:"returned"`
	Filters       map[string]any   `json:"filters"`
	ByKind        map[string]int   `json:"by_kind"`
	ByContract    map[string]int   `json:"by_contract"`
	ByState       map[string]int   `json:"by_state"`
	Totals        map[string]int   `json:"totals"`
	Rows          []map[string]any `json:"rows"`
}

type ManifestRange struct {
	Start int64 `json:"start"`
	End   int64 `json:"end"`
}

type LedgerQuery struct {
	Tenant     string   `json:"tenant,omitempty"`
	WorkUnitID string   `json:"work_unit_id,omitempty"`
	ManifestID string   `json:"manifest_id,omitempty"`
	EventTypes []string `json:"event_types,omitempty"`
	Limit      int      `json:"limit,omitempty"`
}

type LogQuery struct {
	Tenant     string   `json:"tenant,omitempty"`
	WorkUnitID string   `json:"work_unit_id,omitempty"`
	ManifestID string   `json:"manifest_id,omitempty"`
	EventTypes []string `json:"event_types,omitempty"`
	TraceID    string   `json:"trace_id,omitempty"`
	Severity   string   `json:"severity,omitempty"`
	ErrorCode  string   `json:"error_code,omitempty"`
	Limit      int      `json:"limit,omitempty"`
}

type LedgerEvent struct {
	EventID        string         `json:"event_id"`
	EventType      string         `json:"event_type"`
	Tenant         string         `json:"tenant"`
	WorkUnitID     string         `json:"work_unit_id,omitempty"`
	ManifestID     string         `json:"manifest_id,omitempty"`
	PolicyBundleID string         `json:"policy_bundle_id,omitempty"`
	TraceID        string         `json:"trace_id,omitempty"`
	Details        map[string]any `json:"details,omitempty"`
}

type StructuredLogEntry struct {
	LogID          string         `json:"log_id"`
	CreatedAt      string         `json:"created_at"`
	Severity       string         `json:"severity"`
	EventType      string         `json:"event_type"`
	Tenant         string         `json:"tenant,omitempty"`
	WorkUnitID     string         `json:"work_unit_id,omitempty"`
	ManifestID     string         `json:"manifest_id,omitempty"`
	PolicyBundleID string         `json:"policy_bundle_id,omitempty"`
	TraceID        string         `json:"trace_id,omitempty"`
	ErrorCode      string         `json:"error_code,omitempty"`
	Message        string         `json:"message"`
	Details        map[string]any `json:"details,omitempty"`
}

type ReportQuery struct {
	Tenant string
}

type ConformanceResult struct {
	Name    string          `json:"name"`
	Passed  bool            `json:"passed"`
	Checks  map[string]bool `json:"checks"`
	Details map[string]any  `json:"details"`
}

type ProductionReadinessResult struct {
	Name    string          `json:"name"`
	Passed  bool            `json:"passed"`
	Checks  map[string]bool `json:"checks"`
	Details map[string]any  `json:"details"`
}

type PlatformProfile struct {
	Name                 string   `json:"name"`
	DisplayName          string   `json:"display_name"`
	Category             string   `json:"category"`
	DeploymentTargets    []string `json:"deployment_targets"`
	StorageBackends      []string `json:"storage_backends"`
	ComputeBackends      []string `json:"compute_backends"`
	AIProviders          []string `json:"ai_providers"`
	RequiredCapabilities []string `json:"required_capabilities"`
	RequiredArtifacts    []string `json:"required_artifacts"`
	LiveCredentialEnv    []string `json:"live_credential_env"`
	OptionalEnv          []string `json:"optional_env"`
	ConfigKeys           []string `json:"config_keys"`
	Notes                []string `json:"notes"`
}

type PlatformReadinessResult struct {
	Target        string          `json:"target"`
	ContractReady bool            `json:"contract_ready"`
	LiveReady     bool            `json:"live_ready"`
	Passed        bool            `json:"passed"`
	Checks        map[string]bool `json:"checks"`
	Details       map[string]any  `json:"details"`
}

type PlatformReadinessQuery struct {
	Target      string
	RequireLive bool
}

type PlatformMatrix struct {
	PlatformCount      int                       `json:"platform_count"`
	ContractReadyCount int                       `json:"contract_ready_count"`
	LiveReadyCount     int                       `json:"live_ready_count"`
	Targets            []PlatformReadinessResult `json:"targets"`
}

type PolicyReloadResult struct {
	Name              string         `json:"name"`
	Version           string         `json:"version"`
	ReloadedAt        string         `json:"reloaded_at"`
	RecordHashMatches bool           `json:"record_hash_matches"`
	Bundle            map[string]any `json:"bundle,omitempty"`
}

type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ChatCompletionRequest struct {
	Model       string         `json:"model,omitempty"`
	Messages    []ChatMessage  `json:"messages"`
	Temperature float64        `json:"temperature,omitempty"`
	Tools       []any          `json:"tools,omitempty"`
	URP         map[string]any `json:"urp,omitempty"`
}

type CompletionRequest struct {
	Model       string         `json:"model,omitempty"`
	Prompt      any            `json:"prompt"`
	Temperature float64        `json:"temperature,omitempty"`
	URP         map[string]any `json:"urp,omitempty"`
}

type EmbeddingRequest struct {
	Model string         `json:"model,omitempty"`
	Input any            `json:"input"`
	URP   map[string]any `json:"urp,omitempty"`
}

type CacheLookupRequest struct {
	Key                string   `json:"key"`
	Tenant             string   `json:"tenant"`
	Namespace          string   `json:"namespace,omitempty"`
	SourceFingerprints []string `json:"source_fingerprints,omitempty"`
}

type CacheLookupResponse struct {
	Hit    bool   `json:"hit"`
	Value  any    `json:"value,omitempty"`
	Reason string `json:"reason,omitempty"`
}

type CacheStoreRequest struct {
	Key                string            `json:"key"`
	Tenant             string            `json:"tenant"`
	Namespace          string            `json:"namespace,omitempty"`
	Value              any               `json:"value"`
	SourceFingerprints []string          `json:"source_fingerprints,omitempty"`
	Verification       CacheVerification `json:"verification"`
	TTLSeconds         int               `json:"ttl_seconds,omitempty"`
}

type CacheVerification struct {
	Type         string   `json:"type"`
	Expected     string   `json:"expected,omitempty"`
	RequiredKeys []string `json:"required_keys,omitempty"`
}

type CacheStoreResponse struct {
	Stored       bool           `json:"stored"`
	Reason       string         `json:"reason,omitempty"`
	Verification map[string]any `json:"verification,omitempty"`
}

type Approval struct {
	ApprovalID     string   `json:"approval_id"`
	Tenant         string   `json:"tenant"`
	Actor          string   `json:"actor"`
	Contract       Contract `json:"contract"`
	PolicyBundleID string   `json:"policy_bundle_id"`
	CreatedAt      string   `json:"created_at"`
	ExpiresAt      string   `json:"expires_at"`
	WorkUnitID     string   `json:"work_unit_id,omitempty"`
	Reason         string   `json:"reason"`
	Signature      string   `json:"signature"`
}

type ApprovalRequest struct {
	Tenant         string   `json:"tenant"`
	Contract       Contract `json:"contract"`
	PolicyBundleID string   `json:"policy_bundle_id"`
	Reason         string   `json:"reason"`
	WorkUnitID     string   `json:"work_unit_id,omitempty"`
	TTLSeconds     int      `json:"ttl_seconds,omitempty"`
}

type S3PutObjectRequest struct {
	Tenant     string         `json:"tenant,omitempty"`
	Namespace  string         `json:"namespace,omitempty"`
	Bucket     string         `json:"bucket"`
	Key        string         `json:"key"`
	BodyText   string         `json:"body_text,omitempty"`
	BodyBase64 string         `json:"body_base64,omitempty"`
	Metadata   map[string]any `json:"metadata,omitempty"`
	Tags       map[string]any `json:"tags,omitempty"`
}

type S3ObjectByManifestRequest struct {
	ManifestID string `json:"manifest_id"`
	Tenant     string `json:"tenant,omitempty"`
}

type S3RangeRequest struct {
	ManifestID string `json:"manifest_id"`
	Tenant     string `json:"tenant,omitempty"`
	Start      int64  `json:"start"`
	End        int64  `json:"end"`
}

type S3ListObjectsRequest struct {
	Tenant            string `json:"tenant,omitempty"`
	Bucket            string `json:"bucket,omitempty"`
	Prefix            string `json:"prefix,omitempty"`
	IncludeTombstoned bool   `json:"include_tombstoned,omitempty"`
}

type S3DeleteObjectRequest struct {
	ManifestID  string `json:"manifest_id"`
	Tenant      string `json:"tenant,omitempty"`
	Actor       string `json:"actor,omitempty"`
	AllowDelete bool   `json:"allow_delete,omitempty"`
}

type S3MultipartCreateRequest struct {
	Tenant    string         `json:"tenant,omitempty"`
	Namespace string         `json:"namespace,omitempty"`
	Bucket    string         `json:"bucket"`
	Key       string         `json:"key"`
	Metadata  map[string]any `json:"metadata,omitempty"`
	Tags      map[string]any `json:"tags,omitempty"`
}

type S3MultipartPartRequest struct {
	UploadID   string `json:"upload_id"`
	PartNumber int    `json:"part_number"`
	Tenant     string `json:"tenant,omitempty"`
	BodyText   string `json:"body_text,omitempty"`
	BodyBase64 string `json:"body_base64,omitempty"`
}

type Client struct {
	BaseURL string
	HTTP    *http.Client
	APIKey  string
	Tenant  string
}

func NewClient(baseURL string) *Client {
	return &Client{BaseURL: strings.TrimRight(baseURL, "/"), HTTP: http.DefaultClient}
}

func NewAuthenticatedClient(baseURL, apiKey, tenant string) *Client {
	return NewClient(baseURL).WithAPIKey(apiKey).WithTenant(tenant)
}

func (c *Client) WithAPIKey(apiKey string) *Client {
	c.APIKey = apiKey
	return c
}

func (c *Client) WithTenant(tenant string) *Client {
	c.Tenant = tenant
	return c
}

func (c *Client) CreateWorkUnit(ctx context.Context, wu WorkUnit) (*WorkUnitCreateResult, error) {
	var out WorkUnitCreateResult
	err := c.post(ctx, "/v1/work-units", wu, &out)
	return &out, err
}

func (c *Client) ListWorkUnits(ctx context.Context, query WorkUnitListQuery) ([]WorkUnit, error) {
	values := url.Values{}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	path := "/v1/work-units"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out []WorkUnit
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) GetWorkUnit(ctx context.Context, workUnitID string) (*WorkUnit, error) {
	var out WorkUnit
	err := c.get(ctx, "/v1/work-units/"+url.PathEscape(workUnitID), &out)
	return &out, err
}

func (c *Client) PlanWorkUnit(ctx context.Context, workUnitID string) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/work-units/"+url.PathEscape(workUnitID)+"/plan", map[string]any{}, &out)
	return out, err
}

func (c *Client) ExecuteWorkUnit(ctx context.Context, workUnitID string, mode ...string) (*ExecutionResult, error) {
	selectedMode := "enforce"
	if len(mode) > 0 && mode[0] != "" {
		selectedMode = mode[0]
	}
	var out ExecutionResult
	err := c.post(ctx, "/v1/work-units/"+url.PathEscape(workUnitID)+"/execute", map[string]any{"mode": selectedMode}, &out)
	return &out, err
}

func (c *Client) Plan(ctx context.Context, wu WorkUnit) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/work-units/plan", wu, &out)
	return out, err
}

func (c *Client) CreatePlan(ctx context.Context, wu WorkUnit, mode ...string) (map[string]any, error) {
	selectedMode := "observe"
	if len(mode) > 0 && mode[0] != "" {
		selectedMode = mode[0]
	}
	payload := struct {
		WorkUnit
		Mode string `json:"mode"`
	}{WorkUnit: wu, Mode: selectedMode}
	var out map[string]any
	err := c.post(ctx, "/v1/plans", payload, &out)
	return out, err
}

func (c *Client) ListPlans(ctx context.Context, query PlanQuery) ([]map[string]any, error) {
	values := url.Values{}
	if query.WorkUnitID != "" {
		values.Set("work_unit_id", query.WorkUnitID)
	}
	path := "/v1/plans"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out []map[string]any
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) GetPlan(ctx context.Context, planID string) (map[string]any, error) {
	var out map[string]any
	err := c.get(ctx, "/v1/plans/"+url.PathEscape(planID), &out)
	return out, err
}

func (c *Client) Execute(ctx context.Context, wu WorkUnit, mode ...string) (*ExecutionResult, error) {
	selectedMode := "enforce"
	if len(mode) > 0 && mode[0] != "" {
		selectedMode = mode[0]
	}
	payload := struct {
		WorkUnit
		Mode string `json:"mode"`
	}{WorkUnit: wu, Mode: selectedMode}
	var out ExecutionResult
	err := c.post(ctx, "/v1/work-units/execute", payload, &out)
	return &out, err
}

func (c *Client) Manifest(ctx context.Context, manifestID string) (*Manifest, error) {
	var out Manifest
	if err := c.get(ctx, "/v1/manifests/"+url.PathEscape(manifestID), &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (c *Client) ListManifests(ctx context.Context, query ManifestQuery) ([]map[string]any, error) {
	values := url.Values{}
	if query.LogicalRef != "" {
		values.Set("logical_ref", query.LogicalRef)
	}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	if query.Redacted {
		values.Set("redacted", "true")
	}
	path := "/v1/manifests"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out []map[string]any
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) ExportManifests(ctx context.Context, request ManifestExportRequest) (*ManifestExport, error) {
	var out ManifestExport
	err := c.post(ctx, "/v1/manifests/export", request, &out)
	return &out, err
}

func (c *Client) ExploreManifests(ctx context.Context, query ManifestExploreQuery) (*ManifestExplorerReport, error) {
	values := url.Values{}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	if query.Kind != "" {
		values.Set("kind", query.Kind)
	}
	if query.Contract != "" {
		values.Set("contract", string(query.Contract))
	}
	if query.State != "" {
		values.Set("state", query.State)
	}
	if query.Limit > 0 {
		values.Set("limit", fmt.Sprint(query.Limit))
	}
	if query.Redacted != nil {
		values.Set("redacted", fmt.Sprint(*query.Redacted))
	}
	path := "/v1/manifests/explore"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out ManifestExplorerReport
	err := c.get(ctx, path, &out)
	return &out, err
}

func (c *Client) RehydrateManifest(ctx context.Context, manifestID string, rangeRequest *ManifestRange) ([]byte, error) {
	payload := map[string]any{}
	if rangeRequest != nil {
		payload["range"] = rangeRequest
	}
	return c.postBytes(ctx, "/v1/manifests/"+url.PathEscape(manifestID)+"/rehydrate", payload)
}

func (c *Client) LedgerQuery(ctx context.Context, query LedgerQuery) ([]LedgerEvent, error) {
	var out []LedgerEvent
	err := c.post(ctx, "/v1/ledger/query", query, &out)
	return out, err
}

func (c *Client) LogsQuery(ctx context.Context, query LogQuery) ([]StructuredLogEntry, error) {
	var out []StructuredLogEntry
	err := c.post(ctx, "/v1/logs/query", query, &out)
	return out, err
}

func (c *Client) LedgerStreamURL(query LedgerQuery) string {
	values := url.Values{}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	if query.WorkUnitID != "" {
		values.Set("work_unit_id", query.WorkUnitID)
	}
	if query.ManifestID != "" {
		values.Set("manifest_id", query.ManifestID)
	}
	if len(query.EventTypes) > 0 {
		values.Set("event_types", strings.Join(query.EventTypes, ","))
	}
	if query.Limit > 0 {
		values.Set("limit", fmt.Sprint(query.Limit))
	}
	path := c.BaseURL + "/v1/ledger/stream"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	return path
}

func (c *Client) SavingsReport(ctx context.Context, query ReportQuery) (map[string]any, error) {
	values := url.Values{}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	path := "/v1/reports/savings"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out map[string]any
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) DashboardReport(ctx context.Context, query ReportQuery) (map[string]any, error) {
	values := url.Values{}
	if query.Tenant != "" {
		values.Set("tenant", query.Tenant)
	}
	path := "/v1/reports/dashboard"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var out map[string]any
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) AIConformance(ctx context.Context) (*ConformanceResult, error) {
	var out ConformanceResult
	err := c.get(ctx, "/v1/conformance/ai", &out)
	return &out, err
}

func (c *Client) ProductionReadiness(ctx context.Context) (*ProductionReadinessResult, error) {
	var out ProductionReadinessResult
	err := c.get(ctx, "/v1/admin/readiness", &out)
	return &out, err
}

func (c *Client) PlatformProfiles(ctx context.Context) ([]PlatformProfile, error) {
	var out []PlatformProfile
	err := c.get(ctx, "/v1/platforms", &out)
	return out, err
}

func (c *Client) PlatformReadiness(ctx context.Context, query PlatformReadinessQuery) ([]PlatformReadinessResult, error) {
	values := url.Values{}
	if query.Target != "" {
		values.Set("target", query.Target)
	}
	if query.RequireLive {
		values.Set("require_live", "true")
	}
	path := "/v1/platforms/readiness"
	if encoded := values.Encode(); encoded != "" {
		path += "?" + encoded
	}
	var many []PlatformReadinessResult
	if err := c.get(ctx, path, &many); err == nil {
		return many, nil
	}
	var one PlatformReadinessResult
	if err := c.get(ctx, path, &one); err != nil {
		return nil, err
	}
	return []PlatformReadinessResult{one}, nil
}

func (c *Client) PlatformMatrix(ctx context.Context) (*PlatformMatrix, error) {
	var out PlatformMatrix
	err := c.get(ctx, "/v1/platforms/matrix", &out)
	return &out, err
}

func (c *Client) ReloadPolicyBundle(ctx context.Context, name string, actor ...string) (*PolicyReloadResult, error) {
	if name == "" {
		name = "default-safe"
	}
	selectedActor := "sdk"
	if len(actor) > 0 && actor[0] != "" {
		selectedActor = actor[0]
	}
	var out PolicyReloadResult
	err := c.post(ctx, "/v1/policies/bundles/"+url.PathEscape(name)+"/reload", map[string]any{"actor": selectedActor}, &out)
	return &out, err
}

func (c *Client) ExactCacheLookup(ctx context.Context, request CacheLookupRequest) (*CacheLookupResponse, error) {
	var out CacheLookupResponse
	err := c.post(ctx, "/v1/cache/exact/lookup", request, &out)
	return &out, err
}

func (c *Client) StoreCacheEntry(ctx context.Context, request CacheStoreRequest) (*CacheStoreResponse, error) {
	var out CacheStoreResponse
	err := c.post(ctx, "/v1/cache/store", request, &out)
	return &out, err
}

func (c *Client) IssueApproval(ctx context.Context, request ApprovalRequest) (*Approval, error) {
	var out Approval
	err := c.post(ctx, "/v1/approvals", request, &out)
	return &out, err
}

func (c *Client) ListApprovals(ctx context.Context, tenant string) ([]Approval, error) {
	path := "/v1/approvals"
	if tenant != "" {
		path += "?tenant=" + url.QueryEscape(tenant)
	}
	var out []Approval
	err := c.get(ctx, path, &out)
	return out, err
}

func (c *Client) S3PutObject(ctx context.Context, request S3PutObjectRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/objects", request, &out)
	return out, err
}

func (c *Client) S3HeadObject(ctx context.Context, request S3ObjectByManifestRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/objects/head", request, &out)
	return out, err
}

func (c *Client) S3GetObject(ctx context.Context, request S3ObjectByManifestRequest) ([]byte, error) {
	return c.postBytes(ctx, "/v1/s3/objects/get", request)
}

func (c *Client) S3RangeRead(ctx context.Context, request S3RangeRequest) ([]byte, error) {
	return c.postBytes(ctx, "/v1/s3/objects/range", request)
}

func (c *Client) S3ListObjects(ctx context.Context, request S3ListObjectsRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/objects/list", request, &out)
	return out, err
}

func (c *Client) S3DeleteObject(ctx context.Context, request S3DeleteObjectRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/objects/delete", request, &out)
	return out, err
}

func (c *Client) S3CreateMultipartUpload(ctx context.Context, request S3MultipartCreateRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/multipart/create", request, &out)
	return out, err
}

func (c *Client) S3UploadMultipartPart(ctx context.Context, request S3MultipartPartRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/s3/multipart/part", request, &out)
	return out, err
}

func (c *Client) S3CompleteMultipartUpload(ctx context.Context, uploadID string, tenant ...string) (map[string]any, error) {
	payload := map[string]any{"upload_id": uploadID}
	if len(tenant) > 0 && tenant[0] != "" {
		payload["tenant"] = tenant[0]
	}
	var out map[string]any
	err := c.post(ctx, "/v1/s3/multipart/complete", payload, &out)
	return out, err
}

func (c *Client) S3AbortMultipartUpload(ctx context.Context, uploadID string, tenant ...string) (map[string]any, error) {
	payload := map[string]any{"upload_id": uploadID}
	if len(tenant) > 0 && tenant[0] != "" {
		payload["tenant"] = tenant[0]
	}
	var out map[string]any
	err := c.post(ctx, "/v1/s3/multipart/abort", payload, &out)
	return out, err
}

func (c *Client) ChatCompletions(ctx context.Context, request ChatCompletionRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/chat/completions", request, &out)
	return out, err
}

func (c *Client) Completions(ctx context.Context, request CompletionRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/completions", request, &out)
	return out, err
}

func (c *Client) Embeddings(ctx context.Context, request EmbeddingRequest) (map[string]any, error) {
	var out map[string]any
	err := c.post(ctx, "/v1/embeddings", request, &out)
	return out, err
}

func (c *Client) Models(ctx context.Context) (map[string]any, error) {
	var out map[string]any
	err := c.get(ctx, "/v1/models", &out)
	return out, err
}

func (c *Client) get(ctx context.Context, path string, out any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+path, nil)
	if err != nil {
		return err
	}
	return c.do(req, out)
}

func (c *Client) post(ctx context.Context, path string, payload any, out any) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("content-type", "application/json")
	return c.do(req, out)
}

func (c *Client) postBytes(ctx context.Context, path string, payload any) ([]byte, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.BaseURL+path, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("content-type", "application/json")
	c.authorize(req)
	res, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer res.Body.Close()
	if res.StatusCode < 200 || res.StatusCode > 299 {
		return nil, responseError(res)
	}
	return io.ReadAll(res.Body)
}

func (c *Client) do(req *http.Request, out any) error {
	c.authorize(req)
	res, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode < 200 || res.StatusCode > 299 {
		return responseError(res)
	}
	return json.NewDecoder(res.Body).Decode(out)
}

func (c *Client) authorize(req *http.Request) {
	if c.APIKey != "" && req.Header.Get("authorization") == "" {
		req.Header.Set("authorization", "Bearer "+c.APIKey)
	}
	if c.Tenant != "" && req.Header.Get("x-urp-tenant") == "" {
		req.Header.Set("x-urp-tenant", c.Tenant)
	}
}

func responseError(res *http.Response) error {
	body, _ := io.ReadAll(io.LimitReader(res.Body, 64*1024))
	if len(body) == 0 {
		return fmt.Errorf("urp request failed: %s", res.Status)
	}
	return fmt.Errorf("urp request failed: %s: %s", res.Status, strings.TrimSpace(string(body)))
}

func encodeJSONValue(value any) any {
	switch typed := value.(type) {
	case []byte:
		return map[string]any{"_urp_encoding": "base64", "data": base64.StdEncoding.EncodeToString(typed)}
	case map[string]any:
		result := make(map[string]any, len(typed))
		for key, item := range typed {
			result[key] = encodeJSONValue(item)
		}
		return result
	case []any:
		result := make([]any, len(typed))
		for index, item := range typed {
			result[index] = encodeJSONValue(item)
		}
		return result
	default:
		return value
	}
}

func decodeJSONValue(value any) (any, error) {
	switch typed := value.(type) {
	case map[string]any:
		if len(typed) == 2 && typed["_urp_encoding"] == "base64" {
			encoded, ok := typed["data"].(string)
			if !ok {
				return nil, fmt.Errorf("base64 envelope data must be a string")
			}
			decoded, err := base64.StdEncoding.DecodeString(encoded)
			if err != nil {
				return nil, fmt.Errorf("invalid base64 envelope: %w", err)
			}
			return decoded, nil
		}
		result := make(map[string]any, len(typed))
		for key, item := range typed {
			decoded, err := decodeJSONValue(item)
			if err != nil {
				return nil, err
			}
			result[key] = decoded
		}
		return result, nil
	case []any:
		result := make([]any, len(typed))
		for index, item := range typed {
			decoded, err := decodeJSONValue(item)
			if err != nil {
				return nil, err
			}
			result[index] = decoded
		}
		return result, nil
	default:
		return value, nil
	}
}

func newID(prefix string) string {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return fmt.Sprintf("%s_%d", prefix, time.Now().UTC().UnixNano())
	}
	return prefix + "_" + hex.EncodeToString(buf)
}
