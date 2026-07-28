/**
 * AI Worker 独立进程入口(QUEUE_DRIVER=bullmq 模式)。
 * 消费 Redis 队列,处理后通过 HTTP 回调任务中心。
 * 本地开发/测试用 inline 模式时不需要启动本进程。
 */
import type { GenerationTaskInput, WorkerCallbackEvent } from "@ppe/api-contracts";
import { processJob } from "./processor";

const QUEUE_NAME = process.env.QUEUE_NAME ?? "generation-jobs";
const REDIS_URL = process.env.REDIS_URL ?? "redis://127.0.0.1:6379";
const API_BASE = process.env.API_BASE ?? "http://127.0.0.1:3100";

async function callback(event: WorkerCallbackEvent): Promise<void> {
  const response = await fetch(`${API_BASE}/internal/v1/jobs/${event.jobId}/events`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(event),
  });
  if (!response.ok) {
    throw new Error(`callback failed: ${response.status} ${await response.text()}`);
  }
}

async function main(): Promise<void> {
  const { Worker } = await import("bullmq");
  const worker = new Worker<GenerationTaskInput>(
    QUEUE_NAME,
    async (job) => {
      await processJob(job.data, callback);
    },
    { connection: { url: REDIS_URL } },
  );
  worker.on("failed", (job, error) => {
    console.error(JSON.stringify({ level: "error", jobId: job?.data?.jobId, traceId: job?.data?.traceId, message: error.message }));
  });
  console.log(JSON.stringify({ level: "info", message: `ai-worker consuming ${QUEUE_NAME}`, redis: REDIS_URL }));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
