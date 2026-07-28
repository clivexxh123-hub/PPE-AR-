import type { GenerationTaskInput } from "@ppe/api-contracts";

/** 队列适配层(§1:AI 调用只通过队列,可替换) */
export interface JobQueue {
  enqueue(task: GenerationTaskInput): Promise<void>;
}
