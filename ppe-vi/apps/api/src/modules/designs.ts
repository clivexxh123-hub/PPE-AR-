/** 设计与方案模块(§3/§4.1):画布 JSON 校验 + 不可变版本快照。 */
import { randomUUID } from "node:crypto";
import { CANVAS_SCHEMA_VERSION, validateCanvas } from "@ppe/canvas-core";
import { ERROR_CODES } from "@ppe/api-contracts";
import type { Design, DesignVersion } from "@ppe/domain-types";
import { ApiProblem, notFound } from "../middleware";
import type { Repo } from "../repo/types";
import type { Ctx } from "./generation";

export class DesignService {
  constructor(private repo: Repo) {}

  async create(ctx: Ctx, input: { productId: string; name: string }): Promise<Design> {
    const product = await this.repo.getProduct(ctx.tenantId, input?.productId ?? "");
    if (!product) throw notFound("product not found");
    if (!input.name) throw new ApiProblem(400, ERROR_CODES.VALIDATION_FAILED, "name is required");

    const design: Design = {
      id: `dsn_${randomUUID()}`,
      tenantId: ctx.tenantId,
      productId: product.id,
      name: input.name,
      createdAt: new Date().toISOString(),
      createdBy: ctx.userId,
    };
    await this.repo.createDesign(design);
    return design;
  }

  /** 每次保存生成不可变快照(§4.1 步骤4) */
  async saveVersion(ctx: Ctx, designId: string, canvasJson: unknown): Promise<DesignVersion> {
    const design = await this.repo.getDesign(ctx.tenantId, designId);
    if (!design) throw notFound("design not found");

    const result = validateCanvas(canvasJson);
    if (!result.ok) throw new ApiProblem(400, ERROR_CODES.CANVAS_SCHEMA_INVALID, result.message);

    // 画布引用的视角/印刷面必须属于本租户(ID 串联可追溯,§12.3)
    const view = await this.repo.getProductView(ctx.tenantId, result.canvas.productViewId);
    const area = await this.repo.getPrintArea(ctx.tenantId, result.canvas.printAreaId);
    if (!view || !area) throw notFound("product view or print area not found");

    const version: DesignVersion = {
      id: `dsv_${randomUUID()}`,
      tenantId: ctx.tenantId,
      designId: design.id,
      versionNo: await this.repo.nextDesignVersionNo(ctx.tenantId, design.id),
      canvasSchemaVersion: CANVAS_SCHEMA_VERSION,
      canvasJson: result.canvas,
      createdAt: new Date().toISOString(),
      createdBy: ctx.userId,
    };
    await this.repo.createDesignVersion(version);
    return version;
  }

  async listVersions(ctx: Ctx, designId: string): Promise<DesignVersion[]> {
    const design = await this.repo.getDesign(ctx.tenantId, designId);
    if (!design) throw notFound("design not found");
    return this.repo.listDesignVersions(ctx.tenantId, designId);
  }
}
