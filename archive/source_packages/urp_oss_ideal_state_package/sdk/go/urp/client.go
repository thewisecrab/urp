package urp

type ResourceRef struct { LogicalID string; ResourceType string; Tenant string; ContentType string }
type PlanRequest struct { Resource ResourceRef; Contract string; Sample string }
type Client struct { BaseURL string; Token string }
