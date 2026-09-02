# 数据库说明

`init` 目录用于全新 MySQL 8 数据库初始化，按文件名顺序执行。

- `000_product_catalog.sql`：商品目录、分类和文件表；
- `001`–`008`、`010`–`013`：适用于全新数据库的业务迁移；
- `020_sanitized_catalog_seed.sql`：从当前测试库导出的非敏感业务种子。

脱敏种子仅包含以下表的数据：

- `product_category`
- `product_catalog`
- `product_files`
- `ai_model_assets`
- `ai_scene_assets`
- `ai_logo_assets`
- `business_product_showcase_profiles`

历史升级文件 `009_ai_model_view_type.sql` 会为旧版 `ai_model_assets` 增加视角字段；当前 `001` 已直接包含该字段，所以全新初始化时不重复执行。完整 `009` 文件仍保留在 `ppe-product-admin/server/migrations`。

案例标准数据由 `011`–`013` 创建和修复。用户、密码、会话、客户、审计、生成记录及客户归档均未导出。

如需迁移已有数据库，请先备份，再仅执行尚未应用的迁移文件；不要对已有正式库重新执行 `000_product_catalog.sql`。
