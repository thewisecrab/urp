export type Contract = "exact_bytes" | "exact_logical" | "bounded_approx" | "semantic" | "derived" | "tombstone";

export interface WorkUnit {
  id?: string;
  kind: string;
  tenant: string;
  namespace?: string;
  logicalRef: string;
  requestedContract?: Contract;
  metadata?: Record<string, unknown>;
  payload?: unknown;
}

export class URPClient {
  constructor(private baseUrl: string) {}

  async plan(workUnit: WorkUnit): Promise<unknown> {
    const res = await fetch(`${this.baseUrl}/v1/work-units/plan`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        kind: workUnit.kind,
        tenant: workUnit.tenant,
        logical_ref: workUnit.logicalRef,
        payload: workUnit.payload,
      }),
    });
    if (!res.ok) throw new Error(`URP plan failed: ${res.status}`);
    return res.json();
  }
}
