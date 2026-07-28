/**
 * MS1 验收自动化(架构 §12):
 * 1. 闭环:产品 → 画布版本 → 生成任务 → Mock Worker → 结果 Asset 登记
 * 2. trace_id 串联:请求 → 任务 → 审计日志
 * 3. 失败重试:首次可重试失败后任务中心自动重试并成功
 * 4. 越权 ×2:跨租户读产品 / 读任务均 404
 */
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import type { Server } from "node:http";
import { createApp } from "../src/app";

let server: Server;
let base: string;

const T1 = { "x-tenant-id": "tenant_a", "x-user-id": "user_a1", "content-type": "application/json" };
const T2 = { "x-tenant-id": "tenant_b", "x-user-id": "user_b1", "content-type": "application/json" };

async function call(method: string, path: string, headers: Record<string, string>, body?: unknown) {
  const response = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return { status: response.status, json: await response.json() };
}

const until = async <T>(fn: () => Promise<T>, pred: (v: T) => boolean, timeoutMs = 3000): Promise<T> => {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    const value = await fn();
    if (pred(value)) return value;
    if (Date.now() > deadline) throw new Error("timeout waiting for condition");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
};

before(async () => {
  const app = await createApp(); // 默认 memory + inline,契约与真实环境一致
  server = app.listen(0);
  const address = server.address();
  base = `http://127.0.0.1:${typeof address === "object" && address ? address.port : 0}`;
});

after(() => server.close());

async function seedDesignVersion(headers: Record<string, string>) {
  const product = await call("POST", "/api/v1/products", headers, {
    name: "ABS 安全帽 V型",
    category: "helmet",
    views: [{ name: "正面", printAreas: [{ name: "前额区", widthMm: 80, heightMm: 40, calibration: { grid: "mock" } }] }],
  });
  assert.equal(product.status, 201);
  const view = product.json.views[0];
  const area = view.printAreas[0];

  const design = await call("POST", "/api/v1/designs", headers, { productId: product.json.id, name: "客户A 前额印标" });
  assert.equal(design.status, 201);

  const version = await call("POST", `/api/v1/designs/${design.json.id}/versions`, headers, {
    canvasJson: {
      schemaVersion: 1,
      productViewId: view.id,
      printAreaId: area.id,
      elements: [{ type: "logo", assetId: "asset_logo_demo", x: 40, y: 20, scale: 1, rotation: 0 }],
    },
  });
  assert.equal(version.status, 201);
  return { product: product.json, design: design.json, version: version.json };
}

test("闭环:创建任务 → 排队 → 进度 → 成功 → 结果登记,trace_id 全程串联", async () => {
  const { version } = await seedDesignVersion(T1);

  const traceId = "trc_e2e_fixed";
  const created = await call("POST", "/api/v1/generation-jobs", { ...T1, "x-trace-id": traceId }, { designVersionId: version.id });
  assert.equal(created.status, 202);
  assert.equal(created.json.status, "queued");
  assert.ok(created.json.jobId.startsWith("gen_"));
  assert.equal(created.json.traceId, traceId); // §12.5:trace_id 可串联

  const done = await until(
    () => call("GET", `/api/v1/generation-jobs/${created.json.jobId}`, T1),
    (r) => r.json.status === "succeeded",
  );
  assert.equal(done.json.progress, 100);
  assert.equal(done.json.traceId, traceId);
  assert.ok(done.json.resultAssetId, "成功后必须登记结果 Asset");
  assert.ok(done.json.modelProfileId, "模型版本必须登记(可复现)");
});

test("画布 schema 校验:非法画布 JSON 被拒绝", async () => {
  const { design } = await seedDesignVersion(T1);
  const bad = await call("POST", `/api/v1/designs/${design.id}/versions`, T1, {
    canvasJson: { schemaVersion: 1, elements: "not-an-array" },
  });
  assert.equal(bad.status, 400);
  assert.equal(bad.json.errorCode, "DESIGN_400_CANVAS_SCHEMA_INVALID");
});

test("失败重试:可重试失败由任务中心自动重试,最终成功且 attempts=1", async () => {
  const { version } = await seedDesignVersion(T1);
  const created = await call("POST", "/api/v1/generation-jobs", T1, {
    designVersionId: version.id,
    parameters: { failFirstAttempt: true },
  });
  assert.equal(created.status, 202);

  const done = await until(
    () => call("GET", `/api/v1/generation-jobs/${created.json.jobId}`, T1),
    (r) => r.json.status === "succeeded",
  );
  assert.equal(done.json.attempts, 1);
});

test("不可重试失败:输入不合法直接终态 failed,保留错误码", async () => {
  const { version } = await seedDesignVersion(T1);
  const created = await call("POST", "/api/v1/generation-jobs", T1, {
    designVersionId: version.id,
    parameters: { failInvalidInput: true },
  });
  const done = await until(
    () => call("GET", `/api/v1/generation-jobs/${created.json.jobId}`, T1),
    (r) => r.json.status === "failed",
  );
  assert.equal(done.json.errorCode, "AI_400_INPUT_INVALID");
  assert.equal(done.json.attempts, 0);
});

test("越权用例1:租户B 读租户A 的产品 → 404(§12.4)", async () => {
  const { product } = await seedDesignVersion(T1);
  const crossRead = await call("GET", `/api/v1/products/${product.id}`, T2);
  assert.equal(crossRead.status, 404);
  assert.equal(crossRead.json.errorCode, "COMMON_404_RESOURCE_NOT_FOUND");
});

test("越权用例2:租户B 读/引用租户A 的任务与方案版本 → 404(§12.4)", async () => {
  const { version } = await seedDesignVersion(T1);
  const created = await call("POST", "/api/v1/generation-jobs", T1, { designVersionId: version.id });
  assert.equal(created.status, 202);

  const crossJob = await call("GET", `/api/v1/generation-jobs/${created.json.jobId}`, T2);
  assert.equal(crossJob.status, 404);

  // 租户B 也不能用租户A 的 designVersionId 创建任务
  const crossCreate = await call("POST", "/api/v1/generation-jobs", T2, { designVersionId: version.id });
  assert.equal(crossCreate.status, 404);
});

test("未带租户上下文 → 401", async () => {
  const anonymous = await call("GET", "/api/v1/products/whatever", { "content-type": "application/json" });
  assert.equal(anonymous.status, 401);
  assert.equal(anonymous.json.errorCode, "IAM_400_TENANT_REQUIRED");
});
