/**
 * 任务中心(AI 编排模块,§4.2)。
 * - 创建任务立即返回 job_id,不阻塞用户请求
 * - 状态机校验、失败重试决策、结果 Asset 登记都在这里,Worker 不碰业务库
 */
import { randomUUID } from "node:crypto";
import type { GenerationTaskInput, WorkerCallbackEvent } from "@ppe/api-contracts";
import { ERROR_CODES } from "@ppe/api-contracts";
import type { GenerationJob, JobStatus } from "@ppe/domain-types";
import { canTransition } from "@ppe/domain-types";
import { log } from "../logger";
import { ApiProblem, notFound } from "../middleware";
import type { Repo } from "../repo/types";
import type { JobQueue } from "../queue/types";

export interface Ctx {
  tenantId: string;
  userId: string;
  traceId: string;
}

export class GenerationService {
  private queue!: JobQueue;
  constructor(private repo: Repo) {}

  /** 队列在 app 装配时注入(inline 队列需要先拿到 handleEvent 引用) */
  setQueue(queue: JobQueue): void {
    this.queue = queue;
  }

  async createJob(
    ctx: Ctx,
    input: { designVersionId: string; modelProfileId?: string; workflowVersion?: string; parameters?: Record<string, unknown> },
  ): Promise<GenerationJob> {
    const version = await this.repo.getDesignVersion(ctx.tenantId, input.designVersionId);
    if (!version) throw notFound("design version not found");

    const now = new Date().toISOString();
    const job: GenerationJob = {
      id: `gen_${randomUUID()}`,
      tenantId: ctx.tenantId,
      designVersionId: version.id,
      status: "queued",
      progress: 0,
      traceId: ctx.traceId,
      // §4.2 关键原则:模型/工作流版本必须登记,保证可复现
      modelProfileId: input.modelProfileId ?? "model_profile_mock_v1",
      workflowVersion: input.workflowVersion ?? "mock-wearing-v0.1",
      parameters: input.parameters ?? {},
      attempts: 0,
      maxAttempts: 3,
      resultAssetId: null,
      errorCode: null,
      errorMessage: null,
      createdAt: now,
      createdBy: ctx.userId,
      updatedAt: now,
    };
    await this.repo.createJob(job);
    await this.audit(ctx, "generation", "job.create", job.id);
    await this.queue.enqueue(this.toTask(job));
    log("info", "generation job enqueued", { traceId: ctx.traceId, tenantId: ctx.tenantId, module: "generation", resourceId: job.id });
    return job;
  }

  async getJob(ctx: Ctx, id: string): Promise<GenerationJob> {
    const job = await this.repo.getJob(ctx.tenantId, id);
    if (!job) throw notFound("job not found");
    return job;
  }

  /** Worker 回调入口(§6.2)。幂等:终态后重复回调直接忽略。 */
  async handleEvent(event: WorkerCallbackEvent): Promise<void> {
    const job = await this.repo.getJobInternal(event.jobId);
    if (!job) throw notFound("job not found");

    const to = event.status as JobStatus;
    if (["succeeded", "cancelled"].includes(job.status)) return; // 幂等
    const progressOnly = job.status === to;
    if (!progressOnly && !canTransition(job.status, to)) {
      throw new ApiProblem(409, ERROR_CODES.JOB_ILLEGAL_TRANSITION, `illegal transition ${job.status} -> ${to}`);
    }

    job.status = to;
    if (event.progress !== undefined) job.progress = event.progress;
    job.updatedAt = new Date().toISOString();

    if (to === "succeeded" && event.result) {
      // 结果登记为业务 Asset(§4.2 步骤4):由任务中心完成,不由 Worker 写库
      const assetId = `asset_${randomUUID()}`;
      await this.repo.createAsset({
        id: assetId,
        tenantId: job.tenantId,
        kind: "result",
        ossKey: event.result.assetKey,
        meta: { width: event.result.width, height: event.result.height, hash: event.result.hash, jobId: job.id, modelProfileId: job.modelProfileId, workflowVersion: job.workflowVersion },
        createdAt: job.updatedAt,
        createdBy: "task-center",
      });
      job.resultAssetId = assetId;
    }

    if (to === "failed") {
      job.errorCode = event.errorCode ?? ERROR_CODES.AI_MODEL_ERROR;
      job.errorMessage = event.errorMessage ?? "unknown worker error";
      // 分级重试(§10):是否重试由任务中心决定,参数错误不重试
      if (event.retryable === true && job.attempts + 1 < job.maxAttempts) {
        job.attempts += 1;
        job.status = "queued";
        job.errorCode = null;
        job.errorMessage = null;
        await this.repo.updateJob(job);
        await this.queue.enqueue(this.toTask(job));
        log("warn", "job retried", { traceId: job.traceId, tenantId: job.tenantId, module: "generation", resourceId: job.id, attempt: job.attempts });
        return;
      }
    }

    await this.repo.updateJob(job);
    log("info", `job ${job.status}`, { traceId: job.traceId, tenantId: job.tenantId, module: "generation", resourceId: job.id, progress: job.progress });
  }

  private toTask(job: GenerationJob): GenerationTaskInput {
    return {
      jobId: job.id,
      type: "image_generation",
      tenantId: job.tenantId,
      traceId: job.traceId,
      attempt: job.attempts,
      modelProfileId: job.modelProfileId,
      workflowVersion: job.workflowVersion,
      inputAssets: [{ assetId: job.designVersionId, role: "printed_design", version: 1 }],
      parameters: job.parameters,
      callback: `internal://task-center/jobs/${job.id}/events`,
    };
  }

  private async audit(ctx: Ctx, module: string, action: string, resourceId: string): Promise<void> {
    await this.repo.appendAudit({
      id: `aud_${randomUUID()}`,
      tenantId: ctx.tenantId,
      traceId: ctx.traceId,
      actorId: ctx.userId,
      module,
      action,
      resourceId,
      at: new Date().toISOString(),
    });
  }
}
