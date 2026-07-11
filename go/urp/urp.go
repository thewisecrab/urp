package urp

import root "github.com/thewisecrab/urp/go"

type Contract = root.Contract

const (
	ExactBytes    = root.ExactBytes
	ExactLogical  = root.ExactLogical
	BoundedApprox = root.BoundedApprox
	Semantic      = root.Semantic
	Derived       = root.Derived
	Tombstone     = root.Tombstone
)

type WorkUnit = root.WorkUnit
type WorkUnitBuilder = root.WorkUnitBuilder
type WorkUnitCreateResult = root.WorkUnitCreateResult
type WorkUnitListQuery = root.WorkUnitListQuery
type PlanQuery = root.PlanQuery
type ExecutionResult = root.ExecutionResult
type Manifest = root.Manifest
type ManifestQuery = root.ManifestQuery
type ManifestExportRequest = root.ManifestExportRequest
type ManifestExport = root.ManifestExport
type ManifestExploreQuery = root.ManifestExploreQuery
type ManifestExplorerReport = root.ManifestExplorerReport
type ManifestRange = root.ManifestRange
type LedgerQuery = root.LedgerQuery
type LedgerEvent = root.LedgerEvent
type LogQuery = root.LogQuery
type StructuredLogEntry = root.StructuredLogEntry
type ReportQuery = root.ReportQuery
type ConformanceResult = root.ConformanceResult
type ProductionReadinessResult = root.ProductionReadinessResult
type PlatformProfile = root.PlatformProfile
type PlatformReadinessResult = root.PlatformReadinessResult
type PlatformReadinessQuery = root.PlatformReadinessQuery
type PlatformMatrix = root.PlatformMatrix
type PolicyReloadResult = root.PolicyReloadResult
type ChatMessage = root.ChatMessage
type ChatCompletionRequest = root.ChatCompletionRequest
type CompletionRequest = root.CompletionRequest
type EmbeddingRequest = root.EmbeddingRequest
type CacheLookupRequest = root.CacheLookupRequest
type CacheLookupResponse = root.CacheLookupResponse
type CacheStoreRequest = root.CacheStoreRequest
type CacheStoreResponse = root.CacheStoreResponse
type CacheVerification = root.CacheVerification
type Approval = root.Approval
type ApprovalRequest = root.ApprovalRequest
type S3PutObjectRequest = root.S3PutObjectRequest
type S3ObjectByManifestRequest = root.S3ObjectByManifestRequest
type S3RangeRequest = root.S3RangeRequest
type S3ListObjectsRequest = root.S3ListObjectsRequest
type S3DeleteObjectRequest = root.S3DeleteObjectRequest
type S3MultipartCreateRequest = root.S3MultipartCreateRequest
type S3MultipartPartRequest = root.S3MultipartPartRequest
type Client = root.Client

var NewWorkUnitBuilder = root.NewWorkUnitBuilder
var ByteObjectWorkUnit = root.ByteObjectWorkUnit
var PromptRequestWorkUnit = root.PromptRequestWorkUnit
var NewClient = root.NewClient
var NewAuthenticatedClient = root.NewAuthenticatedClient
