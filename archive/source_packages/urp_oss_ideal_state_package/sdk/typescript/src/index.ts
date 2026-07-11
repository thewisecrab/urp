export type ContractMode = "exact-byte" | "exact-logical" | "bounded-approximate" | "semantic-equivalent" | "summary" | "sketch" | "sample" | "tombstone" | "legal-hold" | "do-not-transform";
export interface ResourceRef { logicalId: string; resourceType: string; tenant?: string; contentType?: string; }
export interface PlanRequest { resource: ResourceRef; contract: ContractMode; sample?: string; }
export class URPClient {
  constructor(private baseUrl: string, private token?: string) {}
  async plan(req: PlanRequest): Promise<unknown> {
    const res = await fetch(`${this.baseUrl}/v1/resources/plan`, { method: "POST", headers: { "content-type": "application/json", ...(this.token ? { authorization: `Bearer ${this.token}` } : {}) }, body: JSON.stringify(req) });
    if (!res.ok) throw new Error(`URP plan failed: ${res.status}`);
    return res.json();
  }
}
