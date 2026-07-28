# MS1 实施计划 — 架构落地第一步

> 依据:《系统架构设计_可持续迭代版.md》§11/§12、《开发计划_从0到1.md》W1–W2。
> 目标:满足 §12 五条验收标准,让架构"落地而非停留在文档"。
> 现状:`p0-product/` 为前端演示原型(保留作 UI 参考);本计划新建 `ppe-vi/` Monorepo 作为正式工程。

## 1. MS1 验收标准 → 落地项对照

| §12 标准 | 落地项 | 状态 |
|---|---|---|
| 1. OpenAPI v1 + 任务回调协议冻结 | `packages/api-contracts/`(openapi.v1.yaml、错误码、任务协议 TS 类型) | 本次搭出初稿,待三方评审冻结 |
| 2. Mock AI Worker 跑通任务闭环 | `apps/ai-worker/` 消费队列,进度回写任务中心,支持失败重试 | 本次实现 |
| 3. 产品视角/印刷区/画布 JSON/方案版本可 ID 串联 | `apps/api/` product、design 模块 + `packages/canvas-core/` schema v1 | 本次实现最小集 |
| 4. 租户隔离 + ≥2 个越权测试 | 全部查询强制 `tenant_id`;`apps/api/test/` 越权用例 | 本次实现 |
| 5. trace_id 贯穿全链路 | trace 中间件 → 任务 → Worker → 结果,日志统一携带 | 本次实现 |

## 2. 工程结构(§7 裁剪版,先只建 MS1 需要的)

```text
ppe-vi/
  apps/
    api/            # Express 模块化业务 API(router→service→domain→repository 分层)
    ai-worker/      # Mock AI Worker,按 §6 任务协议消费队列
  packages/
    api-contracts/  # OpenAPI v1、错误码、任务协议(三方契约,变更需评审)
    domain-types/   # 领域类型与状态机(不依赖框架)
    canvas-core/    # 画布 JSON schema v1 + 校验 + 迁移入口
  infra/docker/     # docker-compose:MySQL 8 + Redis 7
```

后续 MS2 再补 `apps/pc-web`(Vue3 画布)、`apps/admin-web`、`apps/render-worker`;边界已留好,加目录即可。

## 3. 关键设计决策

- **仓储与队列都走适配层**:`MemoryRepo`/`InlineQueue` 用于本地开发与自动化测试(无需起 MySQL/Redis);`MysqlRepo`/`BullMQ` 用于真实环境。切换只改环境变量,业务代码零改动——这正是 §1"可替换"边界的第一次演练。
- **状态机唯一**:`queued → running → succeeded / failed / cancelled / timed_out`,定义在 domain-types,API、Worker、前端共用,杜绝各写一份。
- **迁移文件先行**:`apps/api/migrations/0001_init.sql` 覆盖 §5 数据域最小集(tenants/users/products/product_views/print_areas/assets/designs/design_versions/generation_jobs/audit_logs),统一字段含 `tenant_id/created_at/created_by/...`。DB 同事在此基础上出完整 ER 与索引。
- **AI Worker 不碰业务库**:Worker 只收任务协议 JSON、只回调任务中心,结果登记由 API 侧完成(§4.2 强约束)。

## 4. 分工与下两周排期(对齐开发计划 W1–W2)

| 角色 | 本周 | 下周(MS1 评审前) |
|---|---|---|
| 后端 | 在本骨架上接真 MySQL/Redis,补 OSS 临时上传 | 补审计日志写入、死信队列、限流 |
| DB | 基于 0001_init.sql 出 ER 图、字段字典、索引方案 | 迁移演练(升级+回滚) |
| AI | 按 `api-contracts` 任务协议对接真实 ComfyUI PoC(抠图/贴图/生图) | 替换 Mock Worker 的处理函数,协议不变 |
| 前端 | 评审 canvas-core schema;p0-product 画布交互迁移到 Vue3 工程 | 用 Mock API 走通"选产品→编辑→提交任务→看结果" |
| PM | 组织契约评审,冻结 OpenAPI v1 | MS1 评审:按 §12 五条逐项验收 |

## 5. 本地运行

```bash
cd ppe-vi
npm install
npm run build
npm test                 # 内存适配器跑闭环 + 越权测试,无需任何外部服务
docker compose -f infra/docker/docker-compose.yml up -d   # 起 MySQL/Redis
DB_DRIVER=mysql QUEUE_DRIVER=bullmq npm run dev:api       # 真实环境模式
npm run dev:worker
```

## 6. MS1 之后(预告)

MS2(W5)核心链路合龙需要:渲染/导出 Worker(Sharp)、OSS 接入、LOGO 资产模块、Vue3 画布正式版。均在现有模块边界内新增,不动已冻结契约。
