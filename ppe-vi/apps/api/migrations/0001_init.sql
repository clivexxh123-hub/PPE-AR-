-- 0001_init: MS1 最小数据域(架构 §5)。
-- 统一字段:id, tenant_id, created_at, created_by, (updated_at/deleted_at 适用时)。
-- DB 同事在此基础上补齐索引方案、字段字典与后续迁移;每次结构变更必须新增迁移文件。

CREATE TABLE IF NOT EXISTS tenants (
  id          VARCHAR(64) PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  created_at  VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  id          VARCHAR(64) PRIMARY KEY,
  tenant_id   VARCHAR(64) NOT NULL,
  email       VARCHAR(255) NOT NULL,
  role        VARCHAR(64) NOT NULL DEFAULT 'member',
  created_at  VARCHAR(40) NOT NULL,
  KEY idx_users_tenant (tenant_id)
);

CREATE TABLE IF NOT EXISTS products (
  id          VARCHAR(64) PRIMARY KEY,
  tenant_id   VARCHAR(64) NOT NULL,
  name        VARCHAR(255) NOT NULL,
  category    VARCHAR(128) NOT NULL,
  created_at  VARCHAR(40) NOT NULL,
  created_by  VARCHAR(64) NOT NULL,
  deleted_at  VARCHAR(40) NULL,
  KEY idx_products_tenant (tenant_id)
);

CREATE TABLE IF NOT EXISTS product_views (
  id              VARCHAR(64) PRIMARY KEY,
  tenant_id       VARCHAR(64) NOT NULL,
  product_id      VARCHAR(64) NOT NULL,
  name            VARCHAR(128) NOT NULL,
  image_asset_id  VARCHAR(64) NULL,
  created_at      VARCHAR(40) NOT NULL,
  created_by      VARCHAR(64) NOT NULL,
  KEY idx_views_tenant_product (tenant_id, product_id)
);

-- 标定网格、mm↔px 系数、尺寸规则版本都在 calibration JSON(§5)
CREATE TABLE IF NOT EXISTS print_areas (
  id               VARCHAR(64) PRIMARY KEY,
  tenant_id        VARCHAR(64) NOT NULL,
  product_view_id  VARCHAR(64) NOT NULL,
  name             VARCHAR(128) NOT NULL,
  width_mm         DECIMAL(10,2) NOT NULL,
  height_mm        DECIMAL(10,2) NOT NULL,
  calibration      JSON NOT NULL,
  created_at       VARCHAR(40) NOT NULL,
  created_by       VARCHAR(64) NOT NULL,
  KEY idx_areas_tenant_view (tenant_id, product_view_id)
);

-- OSS Key 不等于业务 ID;删除采用软删除 + 引用检查(§5)
CREATE TABLE IF NOT EXISTS assets (
  id          VARCHAR(64) PRIMARY KEY,
  tenant_id   VARCHAR(64) NOT NULL,
  kind        VARCHAR(32) NOT NULL,
  oss_key     VARCHAR(512) NOT NULL,
  meta        JSON NOT NULL,
  created_at  VARCHAR(40) NOT NULL,
  created_by  VARCHAR(64) NOT NULL,
  deleted_at  VARCHAR(40) NULL,
  KEY idx_assets_tenant_kind (tenant_id, kind)
);

CREATE TABLE IF NOT EXISTS designs (
  id          VARCHAR(64) PRIMARY KEY,
  tenant_id   VARCHAR(64) NOT NULL,
  product_id  VARCHAR(64) NOT NULL,
  name        VARCHAR(255) NOT NULL,
  created_at  VARCHAR(40) NOT NULL,
  created_by  VARCHAR(64) NOT NULL,
  deleted_at  VARCHAR(40) NULL,
  KEY idx_designs_tenant (tenant_id)
);

-- 画布 JSON 和 schema version 必须随版本快照保存(§5);快照不可变,无 update 语义
CREATE TABLE IF NOT EXISTS design_versions (
  id                     VARCHAR(64) PRIMARY KEY,
  tenant_id              VARCHAR(64) NOT NULL,
  design_id              VARCHAR(64) NOT NULL,
  version_no             INT NOT NULL,
  canvas_schema_version  INT NOT NULL,
  canvas_json            JSON NOT NULL,
  created_at             VARCHAR(40) NOT NULL,
  created_by             VARCHAR(64) NOT NULL,
  UNIQUE KEY uk_versions (tenant_id, design_id, version_no)
);

-- 任务输入、参数、模型与结果必须可关联、可复现(§5)
CREATE TABLE IF NOT EXISTS generation_jobs (
  id                 VARCHAR(64) PRIMARY KEY,
  tenant_id          VARCHAR(64) NOT NULL,
  design_version_id  VARCHAR(64) NOT NULL,
  status             VARCHAR(20) NOT NULL,
  progress           INT NOT NULL DEFAULT 0,
  trace_id           VARCHAR(64) NOT NULL,
  model_profile_id   VARCHAR(128) NOT NULL,
  workflow_version   VARCHAR(128) NOT NULL,
  parameters         JSON NOT NULL,
  attempts           INT NOT NULL DEFAULT 0,
  max_attempts       INT NOT NULL DEFAULT 3,
  result_asset_id    VARCHAR(64) NULL,
  error_code         VARCHAR(64) NULL,
  error_message      TEXT NULL,
  created_at         VARCHAR(40) NOT NULL,
  created_by         VARCHAR(64) NOT NULL,
  updated_at         VARCHAR(40) NOT NULL,
  KEY idx_jobs_tenant_status (tenant_id, status),
  KEY idx_jobs_trace (trace_id)
);

-- 审计日志只追加,不允许业务模块修改历史(§5)
CREATE TABLE IF NOT EXISTS audit_logs (
  id           VARCHAR(64) PRIMARY KEY,
  tenant_id    VARCHAR(64) NOT NULL,
  trace_id     VARCHAR(64) NOT NULL,
  actor_id     VARCHAR(64) NOT NULL,
  module       VARCHAR(64) NOT NULL,
  action       VARCHAR(128) NOT NULL,
  resource_id  VARCHAR(64) NOT NULL,
  at           VARCHAR(40) NOT NULL,
  KEY idx_audit_tenant (tenant_id),
  KEY idx_audit_trace (trace_id)
);
