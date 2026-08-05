from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.schemas.tasks import TaskStatus


class TaskInputAsset(BaseModel):
    model_config = ConfigDict(title="业务输入资产")

    assetId: str = Field(description="业务数据库资产 ID，只用于追踪审计，AI 服务不查询业务数据库。")
    role: str = Field(description="资产角色，例如 product_reference 或 logo；未知 role 原样记录。")
    version: int = Field(default=1, ge=0, description="资产版本。")

    @field_validator("assetId", "role")
    @classmethod
    def required_asset_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("该字段不能为空。")
        return value


class TaskResult(BaseModel):
    model_config = ConfigDict(title="业务任务结果资产")

    assetKey: str = Field(description="结果 OSS 对象 key，正式联调时由业务端 output.assetKey 提供。")
    width: int = Field(description="结果图片宽度。")
    height: int = Field(description="结果图片高度。")
    hash: str = Field(description="结果图片完整 64 位小写 SHA-256。")


class TaskOutputSpec(BaseModel):
    model_config = ConfigDict(title="业务输出上传配置")

    assetKey: str = Field(description="业务端生成的 OSS 对象 key。")
    uploadUrl: HttpUrl = Field(description="业务端提供的 OSS PUT 预签名 URL。")
    method: Literal["PUT"] = Field(default="PUT", description="上传方法，当前只支持 PUT。")
    requiredHeaders: dict[str, str] = Field(default_factory=dict, description="上传时必须原样携带的请求头。")
    expiresAt: str | None = Field(default=None, description="预签名 URL 过期时间，ISO 字符串。")

    @field_validator("assetKey")
    @classmethod
    def required_asset_key_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("assetKey 不能为空。")
        return value


class WorkerCallbackEvent(BaseModel):
    model_config = ConfigDict(title="业务任务回调事件")

    jobId: str = Field(description="业务任务 ID。")
    status: TaskStatus = Field(description="任务状态。")
    progress: int | None = Field(default=None, ge=0, le=100, description="任务进度。")
    elapsedMs: int | None = Field(default=None, ge=0, description="任务耗时，毫秒。")
    errorCode: str | None = Field(default=None, description="标准错误码。")
    errorMessage: str | None = Field(default=None, description="错误说明。")
    retryable: bool | None = Field(default=None, description="失败是否建议重试。")
    modelProfileId: str | None = Field(default=None, description="模型配置 ID。")
    workflowVersion: str | None = Field(default=None, description="工作流版本。")
    result: TaskResult | None = Field(default=None, description="成功结果资产。")


class GenerationTaskInput(BaseModel):
    model_config = ConfigDict(title="业务图片生成任务输入")

    jobId: str = Field(description="业务任务 ID。")
    type: Literal["image_generation", "logo_remove_bg", "print_render"] = Field(
        default="image_generation",
        description="任务类型：营销图生成、Logo 简单背景抠除或基础印刷设计图合成。",
    )
    tenantId: str = Field(description="租户 ID。")
    traceId: str = Field(description="链路追踪 ID。")
    attempt: int = Field(default=0, ge=0, description="当前尝试次数。")
    modelProfileId: str = Field(description="模型配置 ID。")
    workflowVersion: str = Field(description="工作流版本。")
    inputAssets: list[TaskInputAsset] = Field(default_factory=list, description="输入资产列表，当前用于审计和 metadata 记录。")
    parameters: dict[str, Any] = Field(default_factory=dict, description="生成参数，包含产品信息以及 product_image.url / logo_image.url。")
    callback: str | None = Field(default=None, description="HTTP(S) 回调地址；缺失或不可达不阻塞本地结果记录。")
    output: TaskOutputSpec | None = Field(default=None, description="业务端提供的结果上传配置；正式联调必须提供。")

    @field_validator("jobId", "tenantId", "traceId", "modelProfileId", "workflowVersion")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("该字段不能为空。")
        return value

    @field_validator("jobId")
    @classmethod
    def job_id_must_be_file_safe(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("jobId 不能包含路径分隔符。")
        return value


class BusinessTaskResponse(BaseModel):
    model_config = ConfigDict(title="业务任务响应")

    jobId: str = Field(description="业务任务 ID。")
    task_id: str = Field(description="AI 服务本地任务 ID，当前与 jobId 一致。")
    status: TaskStatus = Field(description="任务状态。")
    message: str = Field(description="任务说明。")
    result_url: str | None = Field(default=None, description="本地结果访问地址。")
    metadata_url: str | None = Field(default=None, description="本地元数据访问地址。")
    errorCode: str | None = Field(default=None, description="标准错误码。")
    errorMessage: str | None = Field(default=None, description="错误说明。")
    retryable: bool | None = Field(default=None, description="失败是否建议重试。")
    result: TaskResult | None = Field(default=None, description="业务结果资产。")
