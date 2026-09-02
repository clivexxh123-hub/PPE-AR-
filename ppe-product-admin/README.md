# PPE 业务系统交付包（不含 AI Server）

交付日期：2026-09-03

本目录包含可独立部署的业务前端、Node.js 管理后端、MySQL 数据库初始化文件、必要的产品/模特/场景/Logo 素材、测试与维护脚本。按甲方要求，`ppe-ai-service`、ComfyUI、模型权重及 AI Server 运行数据均未包含。

## 1. 包含内容

```text
ppe-product-admin/
├─ README.md
├─ docker-compose.yml              # 本地 MySQL 8.4
├─ database/
│  ├─ README.md
│  └─ init/                        # 000 基础库、001-013 迁移、020 脱敏业务种子
├─ server/                          # Node.js/Express 后端、迁移、测试、必要上传素材
└─ web/                             # Vue 3/Vite 前端、案例图片与测试
```

未包含：

- `ppe-ai-service`、ComfyUI、模型文件、AI 输出缓存；
- `node_modules`、`dist`、日志、备份文件；
- 真实 `.env`、数据库密码、会话密钥；
- 当前环境的用户手机号、密码哈希、登录会话、客户资料、审计记录和作图历史。

## 2. 环境要求

- Windows 10/11、macOS 或 Linux；
- Node.js 20 或更高版本，npm 10 或更高版本；
- Docker Desktop（推荐，用于 MySQL 8.4），或兼容的 MySQL 8；
- 可用端口：前端 `9531`、后端 `9530`、MySQL `3306`。

## 3. 快速启动

### 3.1 启动数据库

在本 README 所在目录运行：

```powershell
docker compose up -d mysql
docker compose ps
```

首次创建 Docker 数据卷时，`database/init` 会按文件名顺序自动执行：

1. `000_product_catalog.sql`：商品基础表；
2. `001` 至 `008`、`010` 至 `013`：资源、权限、客户、作图、产品展示与案例库迁移；
3. `020_sanitized_catalog_seed.sql`：当前产品、产品图片、模特、场景和 Logo 脱敏种子。

### 3.2 配置并启动后端

```powershell
cd server
Copy-Item .env.example .env
```

打开 `.env`，至少填写：

```dotenv
PORT=9530
AUTH_ENABLED=true
ALLOWED_WEB_ORIGINS=http://127.0.0.1:9531,http://localhost:9531
IAM_SESSION_SECRET=请替换为至少32位随机字符串
IAM_TENANT_ID=shoudun-ppe
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=ppe_app
DB_PASSWORD=ppe_local_change_me
DB_NAME=ppe_vi
IAM_BOOTSTRAP_ADMIN_NAME=系统管理员
IAM_BOOTSTRAP_ADMIN_PHONE=请填写管理员手机号
IAM_BOOTSTRAP_ADMIN_ORG_CODE=platform-management
IAM_BOOTSTRAP_ADMIN_PASSWORD=请填写至少8位且包含字母和数字的密码
```

安装依赖、创建首个管理员并启动：

```powershell
npm.cmd ci
npm.cmd run bootstrap:admin
npm.cmd start
```

后端地址：`http://127.0.0.1:9530`

### 3.3 启动前端

另开一个 PowerShell：

```powershell
cd web
npm.cmd ci
npm.cmd run dev
```

浏览器打开：`http://127.0.0.1:9531`

## 4. AI 功能边界

本包不包含 AI Server，因此客户档案、商品管理、资源管理、产品与案例库、案例新建、作图记录查询等业务功能可以运行，但“开始真实生成”需要另行部署 AI Server。

如已有独立 AI Server，在后端 `.env` 中设置：

```dotenv
AI_SERVICE_BASE_URL=http://AI服务地址:8000
AI_SERVICE_TIMEOUT_MS=15000
```

前端不得直接连接 AI Server，统一通过 Node 后端转发。

## 5. 数据库维护

- 新环境推荐直接使用 `database/init` 初始化，不需要逐条手工执行迁移。历史升级文件 `009_ai_model_view_type.sql` 已由当前 `001` 的完整建表结构覆盖，因此不在全新初始化目录重复执行，但仍保留在后端源码的迁移目录中供旧库升级参考。
- 已有旧数据库需按当前已执行版本继续运行 `server/migrations` 中尚未执行的 SQL。
- `011` 至 `013` 包含客户作图归档、UTF-8 案例修复、客户新建案例和案例封面能力。
- Docker 初始化 SQL 只会在数据卷第一次创建时执行；已有数据卷不会重复初始化。
- 正式环境必须修改 `docker-compose.yml` 中的演示密码，并通过安全方式注入密钥。

## 6. 测试和构建

后端：

```powershell
cd server
npm.cmd test
```

前端：

```powershell
cd web
npm.cmd test -- --run
npm.cmd run build
```

本交付版本验证结果：后端 53 项通过、4 项数据库集成测试按默认配置跳过；前端 16 项通过；Vue 生产构建通过。

## 7. 当前主要功能

- 密码登录、角色权限、组织架构和账号管理；
- 商品、产品多视图、模特、场景、Logo 与客户档案；
- AI 生成中心业务编排、作图记录、客户图片归档；
- 产品与行业案例库合并展示；
- 三个带场景图片的标准案例；
- 客户负责人新建带封面的客户案例，并直接进入生成中心；
- 印刷前颜色、尺寸与比例检查；
- 产品展示图和长图导出。

## 8. 安全说明

- 不要把真实 `.env` 提交到 Git；
- 正式环境必须使用强随机 `IAM_SESSION_SECRET` 和独立数据库密码；
- 管理员通过 `npm run bootstrap:admin` 创建，不在 SQL 中硬编码；
- 上传目录应纳入备份，但不得对公网直接开放目录列表；
- 如部署在公网，请在 Nginx/网关启用 HTTPS、请求大小限制和访问日志保护。
