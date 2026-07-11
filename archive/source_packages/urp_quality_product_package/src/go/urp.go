package urp

import "context"

type Contract string

const (
	ExactBytes   Contract = "exact_bytes"
	ExactLogical Contract = "exact_logical"
	Semantic     Contract = "semantic"
)

type WorkUnit struct {
	Kind        string
	Tenant      string
	Namespace   string
	LogicalRef  string
	Contract    Contract
	Metadata    map[string]string
}

type Client struct {
	BaseURL string
}

func NewClient(baseURL string) *Client {
	return &Client{BaseURL: baseURL}
}

func (c *Client) Plan(ctx context.Context, wu WorkUnit) error {
	// Skeleton only. Production implementation should call /v1/work-units/plan.
	return nil
}
