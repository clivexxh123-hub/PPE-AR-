/**
 * 内存仓储 — 本地开发与自动化测试用(无需 MySQL)。
 * 与 MysqlRepo 行为契约一致:读操作 tenantId 不匹配返回 null。
 */
import type {
  Asset,
  AuditLog,
  Design,
  DesignVersion,
  GenerationJob,
  PrintArea,
  Product,
  ProductView,
} from "@ppe/domain-types";
import type { Repo } from "./types";

export class MemoryRepo implements Repo {
  private products = new Map<string, Product>();
  private productViews = new Map<string, ProductView>();
  private printAreas = new Map<string, PrintArea>();
  private assets = new Map<string, Asset>();
  private designs = new Map<string, Design>();
  private designVersions = new Map<string, DesignVersion>();
  private jobs = new Map<string, GenerationJob>();
  private audits: AuditLog[] = [];

  private scoped<T extends { tenantId: string }>(map: Map<string, T>, tenantId: string, id: string): T | null {
    const row = map.get(id);
    return row && row.tenantId === tenantId ? row : null;
  }

  async createProduct(row: Product) { this.products.set(row.id, row); }
  async getProduct(tenantId: string, id: string) { return this.scoped(this.products, tenantId, id); }

  async createProductView(row: ProductView) { this.productViews.set(row.id, row); }
  async getProductView(tenantId: string, id: string) { return this.scoped(this.productViews, tenantId, id); }

  async createPrintArea(row: PrintArea) { this.printAreas.set(row.id, row); }
  async getPrintArea(tenantId: string, id: string) { return this.scoped(this.printAreas, tenantId, id); }

  async createAsset(row: Asset) { this.assets.set(row.id, row); }
  async getAsset(tenantId: string, id: string) { return this.scoped(this.assets, tenantId, id); }

  async createDesign(row: Design) { this.designs.set(row.id, row); }
  async getDesign(tenantId: string, id: string) { return this.scoped(this.designs, tenantId, id); }

  async createDesignVersion(row: DesignVersion) { this.designVersions.set(row.id, row); }
  async getDesignVersion(tenantId: string, id: string) { return this.scoped(this.designVersions, tenantId, id); }
  async listDesignVersions(tenantId: string, designId: string) {
    return [...this.designVersions.values()]
      .filter((v) => v.tenantId === tenantId && v.designId === designId)
      .sort((a, b) => a.versionNo - b.versionNo);
  }
  async nextDesignVersionNo(tenantId: string, designId: string) {
    const versions = await this.listDesignVersions(tenantId, designId);
    return (versions.at(-1)?.versionNo ?? 0) + 1;
  }

  async createJob(row: GenerationJob) { this.jobs.set(row.id, { ...row }); }
  async getJob(tenantId: string, id: string) { return this.scoped(this.jobs, tenantId, id); }
  async getJobInternal(id: string) { return this.jobs.get(id) ?? null; }
  async updateJob(row: GenerationJob) { this.jobs.set(row.id, { ...row }); }

  async appendAudit(row: AuditLog) { this.audits.push(row); }
  async listAudit(tenantId: string) { return this.audits.filter((a) => a.tenantId === tenantId); }
}
