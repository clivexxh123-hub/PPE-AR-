/**
 * 应用装配:router → controller 只做协议转换,业务在 service(§7 分层)。
 * DB_DRIVER=memory|mysql, QUEUE_DRIVER=inline|bullmq — 适配器可替换(§1)。
 */
import express, { type Express, type NextFunction, type Request, type Response } from "express";
import { errorHandler, tenantMiddleware, traceMiddleware } from "./middleware";
import { DesignService } from "./modules/designs";
import { GenerationService } from "./modules/generation";
import { ProductService } from "./modules/products";
import { InlineQueue } from "./queue/inline";
import type { JobQueue } from "./queue/types";
import { MemoryRepo } from "./repo/memory";
import type { Repo } from "./repo/types";

export interface AppOptions {
  repo?: Repo;
  queueFactory?: (generation: GenerationService) => Promise<JobQueue> | JobQueue;
}

const wrap =
  (fn: (req: Request, res: Response) => Promise<void>) =>
  (req: Request, res: Response, next: NextFunction) =>
    fn(req, res).catch(next);

const ctx = (req: Request) => ({ tenantId: req.tenantId, userId: req.userId, traceId: req.traceId });

export async function createApp(options: AppOptions = {}): Promise<Express> {
  const repo = options.repo ?? (await buildRepoFromEnv());
  const products = new ProductService(repo);
  const designs = new DesignService(repo);
  const generation = new GenerationService(repo);
  const queue = options.queueFactory
    ? await options.queueFactory(generation)
    : await buildQueueFromEnv(generation);
  generation.setQueue(queue);

  const app = express();
  app.use(express.json({ limit: "2mb" }));
  app.use(traceMiddleware);

  app.get("/health", (_req, res) => { res.json({ ok: true }); });

  // ---- Worker 内部回调(不走租户中间件;生产环境应限内网/签名) ----
  app.post("/internal/v1/jobs/:id/events", wrap(async (req, res) => {
    await generation.handleEvent({ ...req.body, jobId: req.params.id });
    res.json({ ok: true });
  }));

  // ---- 业务 API v1(§8:版本化路径) ----
  const v1 = express.Router();
  v1.use(tenantMiddleware);

  v1.post("/products", wrap(async (req, res) => { res.status(201).json(await products.create(ctx(req), req.body)); }));
  v1.get("/products/:id", wrap(async (req, res) => { res.json(await products.get(ctx(req), req.params.id)); }));

  v1.post("/designs", wrap(async (req, res) => { res.status(201).json(await designs.create(ctx(req), req.body)); }));
  v1.post("/designs/:id/versions", wrap(async (req, res) => { res.status(201).json(await designs.saveVersion(ctx(req), req.params.id, req.body?.canvasJson)); }));
  v1.get("/designs/:id/versions", wrap(async (req, res) => { res.json(await designs.listVersions(ctx(req), req.params.id)); }));

  v1.post("/generation-jobs", wrap(async (req, res) => {
    const job = await generation.createJob(ctx(req), req.body);
    res.status(202).json({ jobId: job.id, status: job.status, traceId: job.traceId, pollUrl: `/api/v1/generation-jobs/${job.id}` });
  }));
  v1.get("/generation-jobs/:id", wrap(async (req, res) => { res.json(await generation.getJob(ctx(req), req.params.id)); }));

  app.use("/api/v1", v1);
  app.use(errorHandler);
  return app;
}

async function buildRepoFromEnv(): Promise<Repo> {
  if (process.env.DB_DRIVER === "mysql") {
    const { createMysqlRepo } = await import("./repo/mysql");
    return createMysqlRepo(process.env.DATABASE_URL ?? "mysql://ppe:ppe_dev@127.0.0.1:3306/ppe_vi");
  }
  return new MemoryRepo();
}

async function buildQueueFromEnv(generation: GenerationService): Promise<JobQueue> {
  if (process.env.QUEUE_DRIVER === "bullmq") {
    const { createBullQueue } = await import("./queue/bullmq");
    return createBullQueue(process.env.REDIS_URL ?? "redis://127.0.0.1:6379");
  }
  return new InlineQueue((event) => generation.handleEvent(event));
}
