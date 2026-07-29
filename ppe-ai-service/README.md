# PPE AI Service

PPE AI Service 是 PPE AI 营销物料生成系统中的独立 AI 服务模块。

本服务负责：

- 接收产品名称、分类、场景、风格等信息
- 生成适合 ComfyUI/Stable Diffusion 的 Prompt
- 调用本机 ComfyUI API 生成图片
- 保存 `result.png` 和 `metadata.json`
- 返回 `task_id`、`result_url`、`metadata_url` 给前端或业务后端

当前已完成真实 AI 出图链路：

```text
产品信息 JSON
↓
FastAPI /ai/generate
↓
Prompt 模板
↓
ComfyUI
↓
Stable Diffusion 1.5
↓
生成图片并返回结果 URL
```

## 项目结构

```text
ppe-ai-service
├─ app
│  ├─ api                  接口路由，例如 /ai/generate
│  ├─ core                 配置项和公共能力
│  ├─ schemas              请求/响应数据结构和字段校验
│  ├─ services             AI 生成、ComfyUI 调用、文件和任务逻辑
│  ├─ templates
│  │  ├─ comfyui           ComfyUI API workflow 模板
│  │  └─ prompt            PPE Prompt 模板
│  └─ main.py              FastAPI 应用入口
├─ samples
│  └─ product_payloads     PPE 产品测试 JSON 样例
├─ scripts                 检查和联调自测脚本
├─ storage                 本地输入、输出和任务记录目录
├─ .env.example            环境变量示例
├─ .gitignore              Git 忽略规则
├─ requirements.txt        Python 依赖
└─ README.md               项目说明
```

## 运行前准备

需要本机先启动 ComfyUI，并确认能打开：

```text
http://127.0.0.1:8188
```

当前测试使用的模型：

```text
v1-5-pruned-emaonly.safetensors
```

模型应能在 ComfyUI 的 `CheckpointLoaderSimple` 中看到。

本项目不提交：

- `.venv/`
- `.env`
- ComfyUI 模型文件
- 生成结果图片
- 本地日志文件

## 配置环境

复制 `.env.example` 为 `.env`，本地开发建议使用：

```env
AI_ENGINE=comfyui
COMFYUI_BASE_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW_PATH=app/templates/comfyui/text_to_image_workflow.json
```

`.env` 是本机配置文件，不要提交到 GitHub。

## 启动 ComfyUI

在终端中执行：

```powershell
cd "D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
.\.venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188
```

看到 ComfyUI 页面可以打开即表示启动成功：

```text
http://127.0.0.1:8188
```

## 启动 AI 服务

在另一个终端中执行：

```powershell
cd "D:\Don't Click it\JOB\XVison\PPE_Test\ppe-ai-service"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开接口文档：

```text
http://127.0.0.1:8000/docs
```

## 生成图片接口

接口：

```text
POST /ai/generate
```

请求示例：

```json
{
  "product_name": "工业安全帽",
  "product_category": "PPE 安全防护用品",
  "scene": "现代化工厂车间，干净背景，产品摄影台面",
  "style": "真实商业产品图风格，黄色工业安全帽，单个产品，居中构图，专业灯光，展示专业、安全、可靠",
  "size": "512x512",
  "prompt_overrides": {
    "material": "ABS 外壳，缓冲内衬",
    "color": "黄色",
    "features": "抗冲击，耐磨，佩戴舒适",
    "target_audience": "工厂采购、安全员、工程施工单位"
  },
  "output_format": "png",
  "sync": true
}
```

成功返回示例：

```json
{
  "task_id": "example-task-id",
  "status": "succeeded",
  "message": "图片已生成，当前使用 comfyui 引擎。",
  "result_url": "/outputs/example-task-id/result.png",
  "metadata_url": "/outputs/example-task-id/metadata.json"
}
```

浏览器查看结果：

```text
http://127.0.0.1:8000/outputs/{task_id}/result.png
```

本地保存位置：

```text
storage/outputs/{task_id}/result.png
storage/outputs/{task_id}/metadata.json
```

## 字段说明

必填字段：

```text
product_name
product_category
scene
style
size
output_format
```

可选字段：

```text
prompt_overrides
sync
product_image
logo_image
```

注意：`product_image` 和 `logo_image` 当前是预留字段，暂未真正参与图生图或 Logo 贴图。

## 测试样例

已准备 5 个 PPE 产品样例：

```text
samples/product_payloads/industrial_helmet.json
samples/product_payloads/face_shield.json
samples/product_payloads/protective_gloves.json
samples/product_payloads/safety_goggles.json
samples/product_payloads/reflective_vest.json
```

批量自测脚本：

```powershell
.\.venv\Scripts\python.exe scripts\batch_generate_test.py --limit 2
```

运行全部样例：

```powershell
.\.venv\Scripts\python.exe scripts\batch_generate_test.py
```

指定样例目录：

```powershell
.\.venv\Scripts\python.exe scripts\batch_generate_test.py --samples-dir samples\product_payloads --limit 3
```

## 当前限制

当前版本已支持文本产品信息驱动的真实 AI 出图，但仍有以下限制：

- 暂不支持产品参考图真正参与生成
- 暂不支持 Logo 贴图
- 暂不支持批量生成正式业务接口
- 暂不支持正式异步任务队列
- 暂未接入数据库归档
- SD 1.5 基础模型的商品图质量不稳定，后续需要评估更适合产品图的模型或 workflow

## 分工边界

AI 服务负责：

```text
产品信息输入
↓
Prompt 生成
↓
ComfyUI 调用
↓
图片生成
↓
结果 URL 返回
```

前端/业务后端负责：

- 客户和产品数据管理
- 用户界面
- 生成记录业务归档
- 画布编辑器
- Logo 位置和最终营销物料编排
