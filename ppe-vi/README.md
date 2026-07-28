# ppe-vi — PPE VI 视觉自动化系统(MS1 骨架)

按《系统架构设计_可持续迭代版.md》落地的 Monorepo。整体规划见仓库上级目录《实施计划_MS1.md》。

## 结构

```text
apps/api           业务 API(Express,模块化单体:产品规范 / 设计方案 / 任务中心)
apps/ai-worker     AI Worker(MS1 为 Mock;接真实 ComfyUI 只改 processor.ts 内部)
packages/api-contracts   OpenAPI v1 + 错误码 + 任务协议(冻结契约,改动需三方评审)
packages/domain-types    领域类型与任务状态机
packages/canvas-core     画布 JSON schema v1 + 校验 + 迁移入口
infra/docker       MySQL 8 + Redis 7(compose 自动执行 migrations/)
```

## 快速开始

```bash
npm install
npm run build
npm test          # 内存 + inline 队列跑 MS1 验收用例,无需外部服务
```

真实环境模式:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
DB_DRIVER=mysql QUEUE_DRIVER=bullmq npm run dev:api
npm run dev:worker
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| DB_DRIVER | memory | memory / mysql |
| DATABASE_URL | mysql://ppe:ppe_dev@127.0.0.1:3306/ppe_vi | mysql 模式连接串 |
| QUEUE_DRIVER | inline | inline / bullmq |
| REDIS_URL | redis://127.0.0.1:6379 | bullmq 模式 |
| PORT | 3100 | API 端口 |

## MS1 鉴权说明

用 `x-tenant-id` / `x-user-id` 请求头模拟登录态;所有查询强制租户隔离,跨租户一律 404。MS2 接入真实 IAM 时仅替换 `tenantMiddleware`,业务代码不动。
