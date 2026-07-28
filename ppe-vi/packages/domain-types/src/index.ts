/**
 * 领域类型与状态机 — 不依赖任何框架(架构 §7 domain 层)。
 * 状态命名与《系统架构设计》§6.2 完全一致,API / Worker / 前端共用。
 */

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

/** 合法状态迁移表。running→running 用于进度更新,由服务层单独放行。 */
export const JOB_TRANSITIONS: Record<JobStatus, JobStatus[]> = {
  queued: ["running", "failed", "cancelled", "timed_out"],
  running: ["succeeded", "failed", "cancelled", "timed_out"],
  succeeded: [],
  failed: ["queued"], // 仅任务中心可重试:failed → queued
  cancelled: [],
  timed_out: ["queued"],
};

export function canTransition(from: JobStatus, to: JobStatus): boolean {
  return JOB_TRANSITIONS[from].includes(to);
}

export const TERMINAL_STATUSES: JobStatus[] = ["succeeded", "cancelled"];

/** 统一字段(架构 §5):所有业务行都带租户与审计字段 */
export interface BaseRow {
  id: string;
  tenantId: string;
  createdAt: string;
  createdBy: string;
}

export interface Product extends BaseRow {
  name: string;
  category: string;
}

export interface ProductView extends BaseRow {
  productId: string;
  name: string; // 正面 / 侧面 / 背面...
  imageAssetId: string | null;
}

export interface PrintArea extends BaseRow {
  productViewId: string;
  name: string;
  widthMm: number;
  heightMm: number;
  /** 标定网格、mm↔px 系数等,由产品规范模块负责(§4.1 关键原则) */
  calibration: Record<string, unknown>;
}

export interface Asset extends BaseRow {
  kind: "logo" | "image" | "font" | "result";
  ossKey: string;
  meta: Record<string, unknown>;
}

export interface Design extends BaseRow {
  productId: string;
  name: string;
}

/** 不可变版本快照(§4.1):画布 JSON + schema version 必须随版本保存 */
export interface DesignVersion extends BaseRow {
  designId: string;
  versionNo: number;
  canvasSchemaVersion: number;
  canvasJson: unknown;
}

export interface GenerationJob extends BaseRow {
  designVersionId: string;
  status: JobStatus;
  progress: number;
  traceId: string;
  modelProfileId: string;
  workflowVersion: string;
  parameters: Record<string, unknown>;
  attempts: number;
  maxAttempts: number;
  resultAssetId: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  updatedAt: string;
}

/** 审计日志只追加(§5) */
export interface AuditLog {
  id: string;
  tenantId: string;
  traceId: string;
  actorId: string;
  module: string;
  action: string;
  resourceId: string;
  at: string;
}
