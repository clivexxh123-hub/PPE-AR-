import type { NextFunction, Request, Response } from "express";
import { randomUUID } from "node:crypto";
import { ERROR_CODES } from "@ppe/api-contracts";
import { log } from "./logger";

declare module "express-serve-static-core" {
  interface Request {
    traceId: string;
    tenantId: string;
    userId: string;
  }
}

/** 全链路追踪(§10):每次请求生成/透传 trace_id */
export function traceMiddleware(req: Request, res: Response, next: NextFunction): void {
  req.traceId = (req.headers["x-trace-id"] as string) || `trc_${randomUUID()}`;
  res.setHeader("x-trace-id", req.traceId);
  next();
}

/**
 * 租户上下文(§5:查询强制隔离)。
 * MS1 用请求头模拟登录态;MS2 接入真实 IAM 后此处换成 token 校验,下游代码不变。
 */
export function tenantMiddleware(req: Request, res: Response, next: NextFunction): void {
  const tenantId = req.headers["x-tenant-id"] as string | undefined;
  const userId = req.headers["x-user-id"] as string | undefined;
  if (!tenantId || !userId) {
    res.status(401).json({
      errorCode: ERROR_CODES.TENANT_REQUIRED,
      message: "x-tenant-id and x-user-id headers are required",
      traceId: req.traceId,
    });
    return;
  }
  req.tenantId = tenantId;
  req.userId = userId;
  next();
}

export class ApiProblem extends Error {
  constructor(
    public status: number,
    public errorCode: string,
    message: string,
  ) {
    super(message);
  }
}

export function notFound(message = "resource not found"): ApiProblem {
  return new ApiProblem(404, ERROR_CODES.RESOURCE_NOT_FOUND, message);
}

export function errorHandler(err: unknown, req: Request, res: Response, _next: NextFunction): void {
  const problem =
    err instanceof ApiProblem ? err : new ApiProblem(500, ERROR_CODES.INTERNAL, err instanceof Error ? err.message : "internal error");
  log(problem.status >= 500 ? "error" : "warn", problem.message, {
    traceId: req.traceId,
    tenantId: req.tenantId,
    errorCode: problem.errorCode,
    path: req.path,
  });
  res.status(problem.status).json({ errorCode: problem.errorCode, message: problem.message, traceId: req.traceId });
}
