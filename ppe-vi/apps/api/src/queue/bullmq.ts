/** BullMQ 队列(QUEUE_DRIVER=bullmq):真实环境,由独立 ai-worker 进程消费。 */
import type { GenerationTaskInput } from "@ppe/api-contracts";
import type { JobQueue } from "./types";

export async function createBullQueue(redisUrl: string, queueName = "generation-jobs"): Promise<JobQueue> {
  const { Queue } = await import("bullmq");
  const queue = new Queue<GenerationTaskInput>(queueName, { connection: { url: redisUrl } });
  return {
    async enqueue(task) {
      // 幂等(§10):jobId+attempt 作为消息 ID,重复投递不会重复执行
      await queue.add("generate", task, { jobId: `${task.jobId}:${task.attempt}` });
    },
  };
}
