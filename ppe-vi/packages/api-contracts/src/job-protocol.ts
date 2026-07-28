/**
 * AI 任务协议 — 与《系统架构设计》§6.1 / §6.2 一一对应。
 * AI 同事内部可任意换 ComfyUI 工作流 / 模型,但该协议不变。
 */
import type { JobStatus } from "@ppe/domain-types";

export interface TaskInputAsset {
  assetId: string;
  role: "product_reference" | "printed_design" | "logo" | "scene";
  version: number;
}

/** §6.1 统一任务输入(队列消息体) */
export interface GenerationTaskInput {
  jobId: string;
  type: "image_generation";
  tenantId: string;
  traceId: string;
  attempt: number;
  modelProfileId: string;
  workflowVersion: string;
  inputAssets: TaskInputAsset[];
  parameters: Record<string, unknown>;
  /** 回调地址(BullMQ 模式下 Worker 通过 HTTP 回调;inline 模式直接调度) */
  callback: string;
}

export interface TaskResult {
  assetKey: string;
  width: number;
  height: number;
  hash: string;
}

/** §6.2 统一状态回调 */
export interface WorkerCallbackEvent {
  jobId: string;
  status: JobStatus;
  progress?: number;
  elapsedMs?: number;
  errorCode?: string;
  errorMessage?: string;
  retryable?: boolean;
  modelProfileId?: string;
  workflowVersion?: string;
  result?: TaskResult;
}
