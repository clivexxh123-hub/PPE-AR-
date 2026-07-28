/**
 * Mock AI 处理器 — MS1 用于跑通任务闭环(架构 §12.2)。
 * AI 同事接入真实 ComfyUI/Flux 时只替换本文件内部实现,
 * 输入(GenerationTaskInput)与回调(WorkerCallbackEvent)协议不变。
 *
 * 强约束(§4.2):Worker 不读写业务数据库,只消费任务、回调任务中心。
 */
import { createHash } from "node:crypto";
import type { GenerationTaskInput, WorkerCallbackEvent } from "@ppe/api-contracts";

export type Report = (event: WorkerCallbackEvent) => Promise<void>;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function processJob(task: GenerationTaskInput, report: Report): Promise<void> {
  const startedAt = Date.now();
  const versions = {
    modelProfileId: task.modelProfileId,
    workflowVersion: task.workflowVersion,
  };
  const base = { jobId: task.jobId, ...versions };

  await report({ ...base, status: "running", progress: 10 });

  // 演练"可重试失败"路径:首次尝试失败,由任务中心决定重试(§6.2)
  if (task.parameters["failFirstAttempt"] === true && task.attempt === 0) {
    await report({
      ...base,
      status: "failed",
      retryable: true,
      errorCode: "AI_502_NETWORK_RETRYABLE",
      errorMessage: "mock: simulated retryable network error",
      elapsedMs: Date.now() - startedAt,
    });
    return;
  }

  // 演练"不可重试失败"路径:输入不合法,任务中心不得重试
  if (task.parameters["failInvalidInput"] === true) {
    await report({
      ...base,
      status: "failed",
      retryable: false,
      errorCode: "AI_400_INPUT_INVALID",
      errorMessage: "mock: simulated invalid input",
      elapsedMs: Date.now() - startedAt,
    });
    return;
  }

  await sleep(10);
  await report({ ...base, status: "running", progress: 60 });
  await sleep(10);

  // 成功:结果"先落 OSS"(mock 只生成 key),再回调登记(§4.2 步骤4)
  const assetKey = `results/${task.tenantId}/${task.jobId}.png`;
  await report({
    ...base,
    status: "succeeded",
    progress: 100,
    elapsedMs: Date.now() - startedAt,
    result: {
      assetKey,
      width: 2048,
      height: 2048,
      hash: createHash("sha256").update(task.jobId).digest("hex").slice(0, 16),
    },
  });
}
