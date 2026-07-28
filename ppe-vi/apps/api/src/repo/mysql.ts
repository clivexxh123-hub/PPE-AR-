/**
 * MySQL 仓储(DB_DRIVER=mysql)。表结构见 migrations/0001_init.sql。
 * 注意:这里只是应用侧最小实现;索引与完整字段字典由 DB 同事在迁移文件中扩展。
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
import type { Pool, RowDataPacket } from "mysql2/promise";
import type { Repo } from "./types";

export async function createMysqlRepo(url: string): Promise<Repo> {
  const mysql = await import("mysql2/promise");
  const pool = mysql.createPool({ uri: url, connectionLimit: 10, namedPlaceholders: true });
  return new MysqlRepo(pool);
}

const j = (value: unknown) => JSON.stringify(value ?? null);
const p = <T>(value: unknown): T => (typeof value === "string" ? JSON.parse(value) : (value as T));

class MysqlRepo implements Repo {
  constructor(private pool: Pool) {}

  private async one<T extends RowDataPacket>(sql: string, params: unknown[]): Promise<T | null> {
    const [rows] = await this.pool.query<T[]>(sql, params);
    return rows[0] ?? null;
  }

  async createProduct(r: Product) {
    await this.pool.query(
      "INSERT INTO products (id, tenant_id, name, category, created_at, created_by) VALUES (?,?,?,?,?,?)",
      [r.id, r.tenantId, r.name, r.category, r.createdAt, r.createdBy],
    );
  }
  async getProduct(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM products WHERE id=? AND tenant_id=? AND deleted_at IS NULL", [id, tenantId]);
    return row ? ({ id: row.id, tenantId: row.tenant_id, name: row.name, category: row.category, createdAt: row.created_at, createdBy: row.created_by } as Product) : null;
  }

  async createProductView(r: ProductView) {
    await this.pool.query(
      "INSERT INTO product_views (id, tenant_id, product_id, name, image_asset_id, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
      [r.id, r.tenantId, r.productId, r.name, r.imageAssetId, r.createdAt, r.createdBy],
    );
  }
  async getProductView(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM product_views WHERE id=? AND tenant_id=?", [id, tenantId]);
    return row ? ({ id: row.id, tenantId: row.tenant_id, productId: row.product_id, name: row.name, imageAssetId: row.image_asset_id, createdAt: row.created_at, createdBy: row.created_by } as ProductView) : null;
  }

  async createPrintArea(r: PrintArea) {
    await this.pool.query(
      "INSERT INTO print_areas (id, tenant_id, product_view_id, name, width_mm, height_mm, calibration, created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?)",
      [r.id, r.tenantId, r.productViewId, r.name, r.widthMm, r.heightMm, j(r.calibration), r.createdAt, r.createdBy],
    );
  }
  async getPrintArea(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM print_areas WHERE id=? AND tenant_id=?", [id, tenantId]);
    return row ? ({ id: row.id, tenantId: row.tenant_id, productViewId: row.product_view_id, name: row.name, widthMm: Number(row.width_mm), heightMm: Number(row.height_mm), calibration: p(row.calibration), createdAt: row.created_at, createdBy: row.created_by } as PrintArea) : null;
  }

  async createAsset(r: Asset) {
    await this.pool.query(
      "INSERT INTO assets (id, tenant_id, kind, oss_key, meta, created_at, created_by) VALUES (?,?,?,?,?,?,?)",
      [r.id, r.tenantId, r.kind, r.ossKey, j(r.meta), r.createdAt, r.createdBy],
    );
  }
  async getAsset(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM assets WHERE id=? AND tenant_id=? AND deleted_at IS NULL", [id, tenantId]);
    return row ? ({ id: row.id, tenantId: row.tenant_id, kind: row.kind, ossKey: row.oss_key, meta: p(row.meta), createdAt: row.created_at, createdBy: row.created_by } as Asset) : null;
  }

  async createDesign(r: Design) {
    await this.pool.query(
      "INSERT INTO designs (id, tenant_id, product_id, name, created_at, created_by) VALUES (?,?,?,?,?,?)",
      [r.id, r.tenantId, r.productId, r.name, r.createdAt, r.createdBy],
    );
  }
  async getDesign(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM designs WHERE id=? AND tenant_id=? AND deleted_at IS NULL", [id, tenantId]);
    return row ? ({ id: row.id, tenantId: row.tenant_id, productId: row.product_id, name: row.name, createdAt: row.created_at, createdBy: row.created_by } as Design) : null;
  }

  private mapVersion(row: RowDataPacket): DesignVersion {
    return { id: row.id, tenantId: row.tenant_id, designId: row.design_id, versionNo: row.version_no, canvasSchemaVersion: row.canvas_schema_version, canvasJson: p(row.canvas_json), createdAt: row.created_at, createdBy: row.created_by };
  }
  async createDesignVersion(r: DesignVersion) {
    await this.pool.query(
      "INSERT INTO design_versions (id, tenant_id, design_id, version_no, canvas_schema_version, canvas_json, created_at, created_by) VALUES (?,?,?,?,?,?,?,?)",
      [r.id, r.tenantId, r.designId, r.versionNo, r.canvasSchemaVersion, j(r.canvasJson), r.createdAt, r.createdBy],
    );
  }
  async getDesignVersion(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM design_versions WHERE id=? AND tenant_id=?", [id, tenantId]);
    return row ? this.mapVersion(row) : null;
  }
  async listDesignVersions(tenantId: string, designId: string) {
    const [rows] = await this.pool.query<RowDataPacket[]>(
      "SELECT * FROM design_versions WHERE tenant_id=? AND design_id=? ORDER BY version_no",
      [tenantId, designId],
    );
    return rows.map((row) => this.mapVersion(row));
  }
  async nextDesignVersionNo(tenantId: string, designId: string) {
    const row = await this.one<RowDataPacket>(
      "SELECT COALESCE(MAX(version_no),0)+1 AS next_no FROM design_versions WHERE tenant_id=? AND design_id=?",
      [tenantId, designId],
    );
    return Number(row?.next_no ?? 1);
  }

  private mapJob(row: RowDataPacket): GenerationJob {
    return {
      id: row.id, tenantId: row.tenant_id, designVersionId: row.design_version_id, status: row.status,
      progress: row.progress, traceId: row.trace_id, modelProfileId: row.model_profile_id,
      workflowVersion: row.workflow_version, parameters: p(row.parameters), attempts: row.attempts,
      maxAttempts: row.max_attempts, resultAssetId: row.result_asset_id, errorCode: row.error_code,
      errorMessage: row.error_message, createdAt: row.created_at, createdBy: row.created_by, updatedAt: row.updated_at,
    };
  }
  async createJob(r: GenerationJob) {
    await this.pool.query(
      `INSERT INTO generation_jobs (id, tenant_id, design_version_id, status, progress, trace_id, model_profile_id,
        workflow_version, parameters, attempts, max_attempts, result_asset_id, error_code, error_message, created_at, created_by, updated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      [r.id, r.tenantId, r.designVersionId, r.status, r.progress, r.traceId, r.modelProfileId, r.workflowVersion,
       j(r.parameters), r.attempts, r.maxAttempts, r.resultAssetId, r.errorCode, r.errorMessage, r.createdAt, r.createdBy, r.updatedAt],
    );
  }
  async getJob(tenantId: string, id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM generation_jobs WHERE id=? AND tenant_id=?", [id, tenantId]);
    return row ? this.mapJob(row) : null;
  }
  async getJobInternal(id: string) {
    const row = await this.one<RowDataPacket>("SELECT * FROM generation_jobs WHERE id=?", [id]);
    return row ? this.mapJob(row) : null;
  }
  async updateJob(r: GenerationJob) {
    await this.pool.query(
      "UPDATE generation_jobs SET status=?, progress=?, attempts=?, result_asset_id=?, error_code=?, error_message=?, updated_at=? WHERE id=?",
      [r.status, r.progress, r.attempts, r.resultAssetId, r.errorCode, r.errorMessage, r.updatedAt, r.id],
    );
  }

  async appendAudit(r: AuditLog) {
    await this.pool.query(
      "INSERT INTO audit_logs (id, tenant_id, trace_id, actor_id, module, action, resource_id, at) VALUES (?,?,?,?,?,?,?,?)",
      [r.id, r.tenantId, r.traceId, r.actorId, r.module, r.action, r.resourceId, r.at],
    );
  }
  async listAudit(tenantId: string) {
    const [rows] = await this.pool.query<RowDataPacket[]>("SELECT * FROM audit_logs WHERE tenant_id=? ORDER BY at", [tenantId]);
    return rows.map((row) => ({ id: row.id, tenantId: row.tenant_id, traceId: row.trace_id, actorId: row.actor_id, module: row.module, action: row.action, resourceId: row.resource_id, at: row.at }) as AuditLog);
  }
}
