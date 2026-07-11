import assert from "node:assert/strict";
import test from "node:test";

import { URPClient, WorkUnitBuilder } from "../dist/index.js";

test("client sends auth and binary payload envelope", async () => {
  let captured;
  const client = new URPClient("http://urp.test/", {
    apiKey: "secret",
    tenant: "acme",
    fetch: async (input, init) => {
      captured = { input: String(input), init };
      return new Response(JSON.stringify({ work_unit_id: "wu_test", trace_id: "tr_test", state: "received" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  const workUnit = WorkUnitBuilder.byteObject("acme", "s3://bucket/key", new Uint8Array([0, 1, 255])).build();
  await client.createWorkUnit(workUnit);
  const headers = new Headers(captured.init.headers);
  const body = JSON.parse(captured.init.body);
  assert.equal(headers.get("authorization"), "Bearer secret");
  assert.equal(headers.get("x-urp-tenant"), "acme");
  assert.deepEqual(body.payload, { _urp_encoding: "base64", data: "AAH/" });
});

test("S3 get returns raw bytes", async () => {
  const expected = new Uint8Array([4, 5, 6]);
  const client = new URPClient("http://urp.test", {
    fetch: async () => new Response(expected, { status: 200, headers: { "content-type": "application/octet-stream" } }),
  });
  const result = new Uint8Array(await client.s3GetObject({ manifest_id: "mf_test" }));
  assert.deepEqual(result, expected);
});
