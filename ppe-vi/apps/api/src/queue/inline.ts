/**
 * Inline 队列 — 开发/测试模式:进程内异步调用 Mock Worker,
 * 走的是与 BullMQ 完全相同的任务协议与回调协议,只是不经过 Redis。
 */
import type { GenerationTaskInput, WorkerCallbackEvent } from "@ppe/api-contracts";
import { processJob } from "@ppe/ai-worker/dist/processor";
import type { JobQueue } from "./types";

export class InlineQueue implements JobQueue {
  constructor(private dispatch: (event: WorkerCallbackEvent) => Promise<void>) {}

  async enqueue(task: GenerationTaskInput): Promise<void> {
    setImmediate(() => {
      processJob(task, this.dispatch).catch((error: unknown) => {
        console.error(JSON.stringify({ level: "error", jobId: task.jobId, traceId: task.traceId, message: String(error) }));
      });
    });
  }
}
