/** 产品与印刷规范模块(§3):产品、视角、可印刷面与标定数据。 */
import { randomUUID } from "node:crypto";
import type { PrintArea, Product, ProductView } from "@ppe/domain-types";
import { ERROR_CODES } from "@ppe/api-contracts";
import { ApiProblem, notFound } from "../middleware";
import type { Repo } from "../repo/types";
import type { Ctx } from "./generation";

interface CreateProductInput {
  name: string;
  category: string;
  views?: { name: string; printAreas?: { name: string; widthMm: number; heightMm: number; calibration?: Record<string, unknown> }[] }[];
}

export class ProductService {
  constructor(private repo: Repo) {}

  async create(ctx: Ctx, input: CreateProductInput) {
    if (!input?.name || !input?.category) {
      throw new ApiProblem(400, ERROR_CODES.VALIDATION_FAILED, "name and category are required");
    }
    const now = new Date().toISOString();
    const base = { tenantId: ctx.tenantId, createdAt: now, createdBy: ctx.userId };

    const product: Product = { id: `prd_${randomUUID()}`, ...base, name: input.name, category: input.category };
    await this.repo.createProduct(product);

    const views: (ProductView & { printAreas: PrintArea[] })[] = [];
    for (const v of input.views ?? []) {
      const view: ProductView = { id: `pvw_${randomUUID()}`, ...base, productId: product.id, name: v.name, imageAssetId: null };
      await this.repo.createProductView(view);
      const areas: PrintArea[] = [];
      for (const a of v.printAreas ?? []) {
        const area: PrintArea = {
          id: `par_${randomUUID()}`, ...base, productViewId: view.id,
          name: a.name, widthMm: a.widthMm, heightMm: a.heightMm, calibration: a.calibration ?? {},
        };
        await this.repo.createPrintArea(area);
        areas.push(area);
      }
      views.push({ ...view, printAreas: areas });
    }
    return { ...product, views };
  }

  async get(ctx: Ctx, id: string): Promise<Product> {
    const product = await this.repo.getProduct(ctx.tenantId, id);
    if (!product) throw notFound("product not found");
    return product;
  }
}
