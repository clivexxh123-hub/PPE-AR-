/**
 * 仓储接口 — 唯一可访问数据库的层(§7)。
 * 所有读操作都带 tenantId,越权即返回 null(§5:查询强制隔离)。
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

export interface Repo {
  createProduct(row: Product): Promise<void>;
  getProduct(tenantId: string, id: string): Promise<Product | null>;

  createProductView(row: ProductView): Promise<void>;
  getProductView(tenantId: string, id: string): Promise<ProductView | null>;

  createPrintArea(row: PrintArea): Promise<void>;
  getPrintArea(tenantId: string, id: string): Promise<PrintArea | null>;

  createAsset(row: Asset): Promise<void>;
  getAsset(tenantId: string, id: string): Promise<Asset | null>;

  createDesign(row: Design): Promise<void>;
  getDesign(tenantId: string, id: string): Promise<Design | null>;

  createDesignVersion(row: DesignVersion): Promise<void>;
  getDesignVersion(tenantId: string, id: string): Promise<DesignVersion | null>;
  listDesignVersions(tenantId: string, designId: string): Promise<DesignVersion[]>;
  nextDesignVersionNo(tenantId: string, designId: string): Promise<number>;

  createJob(row: GenerationJob): Promise<void>;
  getJob(tenantId: string, id: string): Promise<GenerationJob | null>;
  /** 仅供任务中心处理 Worker 回调使用(回调不带租户上下文) */
  getJobInternal(id: string): Promise<GenerationJob | null>;
  updateJob(row: GenerationJob): Promise<void>;

  appendAudit(row: AuditLog): Promise<void>;
  listAudit(tenantId: string): Promise<AuditLog[]>;
}
