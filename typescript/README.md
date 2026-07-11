# URP TypeScript SDK

```ts
import { URPClient, WorkUnitBuilder } from "@thewisecrab/urp";

const client = new URPClient("http://127.0.0.1:8080", {
  apiKey: process.env.URP_API_KEY,
  tenant: "acme",
});

const workUnit = WorkUnitBuilder.byteObject("acme", "s3://logs/sample", new TextEncoder().encode("hello")).build();
const created = await client.createWorkUnit(workUnit);
const result = await client.executeWorkUnit(created.work_unit_id);
const restored = await client.rehydrateManifest(result.manifest_id);
```
