/**
 * 画布 JSON schema v1(架构 §4.1 / §9.5)。
 * 画布只保存"元素 + 参数 + 资源引用",不保存不可追溯的图片状态。
 * schema 升级时:递增 CANVAS_SCHEMA_VERSION,并在 migrateCanvas 中补迁移分支。
 */
import { z } from "zod";

export const CANVAS_SCHEMA_VERSION = 1;

const logoElement = z.object({
  type: z.literal("logo"),
  assetId: z.string().min(1), // 逻辑 Asset ID,不允许直接放 OSS 路径(§5 约定4)
  x: z.number(),
  y: z.number(),
  scale: z.number().positive(),
  rotation: z.number(),
});

const textElement = z.object({
  type: z.literal("text"),
  content: z.string().min(1),
  fontAssetId: z.string().nullable(),
  sizeMm: z.number().positive(),
  color: z.string(),
  x: z.number(),
  y: z.number(),
  rotation: z.number(),
});

export const canvasSchema = z.object({
  schemaVersion: z.literal(1),
  productViewId: z.string().min(1),
  printAreaId: z.string().min(1),
  elements: z.array(z.discriminatedUnion("type", [logoElement, textElement])),
});

export type CanvasJson = z.infer<typeof canvasSchema>;

export function validateCanvas(input: unknown):
  | { ok: true; canvas: CanvasJson }
  | { ok: false; message: string } {
  const parsed = canvasSchema.safeParse(input);
  if (parsed.success) return { ok: true, canvas: parsed.data };
  return { ok: false, message: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") };
}

/** 旧版本画布迁移入口(§9.5:迁移失败保留只读回放) */
export function migrateCanvas(input: unknown): CanvasJson {
  const version = (input as { schemaVersion?: number })?.schemaVersion;
  if (version === CANVAS_SCHEMA_VERSION) {
    const result = validateCanvas(input);
    if (!result.ok) throw new Error(`canvas invalid: ${result.message}`);
    return result.canvas;
  }
  throw new Error(`unsupported canvas schema version: ${String(version)}`);
}
