/** 结构化日志(§10):所有日志必须携带 traceId / 模块 / 资源 ID */
export interface LogFields {
  traceId?: string;
  tenantId?: string;
  module?: string;
  resourceId?: string;
  [key: string]: unknown;
}

export function log(level: "info" | "warn" | "error", message: string, fields: LogFields = {}): void {
  const line = JSON.stringify({ level, at: new Date().toISOString(), message, ...fields });
  if (level === "error") console.error(line);
  else console.log(line);
}
