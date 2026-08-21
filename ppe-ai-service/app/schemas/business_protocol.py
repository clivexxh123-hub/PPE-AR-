from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.tasks import TaskStatus


_ASSET_PARAMETER_FIELDS = {
    "product_reference": "product_image",
    "printed_design": "product_image",
    "logo": "logo_image",
    "scene": "scene_image",
}


def _parameter_url(parameters: dict[str, Any], field: str) -> str | None:
    value = parameters.get(field)
    if isinstance(value, dict):
        value = value.get("url")
    if value is None:
        return None
    url = str(value).strip()
    return url or None


class TaskInputAsset(BaseModel):
    model_config = ConfigDict(title="业务输入资产")

    assetId: str = Field(description="业务数据库资产 ID，只用于追踪审计，AI 服务不查询业务数据库。")
    role: str = Field(description="资产角色，例如 product_reference 或 logo；未知 role 原样记录。")
    version: int = Field(default=1, ge=0, description="资产版本。")
    url: HttpUrl | None = Field(default=None, description="业务端签发的直接 GET 输入资源 URL。")
    expiresAt: str | None = Field(default=None, description="输入资源 URL 过期时间，ISO 字符串。")

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
    attempt: int = Field(ge=0, description="本次任务尝试次数。")
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

    @model_validator(mode="before")
    @classmethod
    def normalize_task_type(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        has_type = payload.get("type") is not None
        has_task_type = payload.get("taskType") is not None

        if has_type and has_task_type and payload["type"] != payload["taskType"]:
            raise ValueError("type 与 taskType 同时传入时必须保持一致。")
        if not has_type and has_task_type:
            payload["type"] = payload["taskType"]

        # taskType 仅作为业务输入兼容别名；内部统一只使用 type。
        payload.pop("taskType", None)
        return payload

    @model_validator(mode="after")
    def validate_generation_mode(self) -> "GenerationTaskInput":
        generation_mode = self.parameters.get("generation_mode")
        if generation_mode is None:
            return self
        if not isinstance(generation_mode, str):
            raise ValueError("generation_mode 必须是字符串。")

        normalized_mode = generation_mode.strip().lower()
        if normalized_mode not in {"", "human_wearing"}:
            raise ValueError("generation_mode 仅支持 human_wearing 或留空。")
        if normalized_mode:
            self.parameters = {**self.parameters, "generation_mode": normalized_mode}
        return self

    def validate_formal_contract(self) -> None:
        """Validate fields that are mandatory only for the frozen back-end contract."""
        required_fields = {
            "jobId",
            "type",
            "tenantId",
            "traceId",
            "attempt",
            "modelProfileId",
            "workflowVersion",
            "inputAssets",
            "parameters",
            "callback",
            "output",
        }
        missing = sorted(required_fields - self.model_fields_set)
        if missing:
            raise ValueError(f"正式 /ai/tasks 协议缺少必传字段：{', '.join(missing)}。")
        if not self.callback or not self.callback.strip():
            raise ValueError("正式 /ai/tasks 协议要求 callback 为非空 HTTP(S) URL。")
        if self.output is None:
            raise ValueError("正式 /ai/tasks 协议要求 output。")

        output_fields = {"assetKey", "uploadUrl", "method", "requiredHeaders", "expiresAt"}
        missing_output = output_fields - self.output.model_fields_set
        if missing_output:
            raise ValueError(f"正式 output 缺少必传字段：{', '.join(sorted(missing_output))}。")
        if not self.output.expiresAt:
            raise ValueError("正式 output.expiresAt 不能为空。")

        missing_asset_fields = [
            asset.assetId
            for asset in self.inputAssets
            if asset.url is None or not asset.expiresAt
        ]
        if missing_asset_fields:
            raise ValueError(
                "正式 inputAssets 每项都要求 url 与 expiresAt；缺失资产："
                + ", ".join(missing_asset_fields)
                + "。"
            )

        roles = {asset.role for asset in self.inputAssets}
        if self.type == "image_generation":
            if {"product_reference", "printed_design"} <= roles:
                raise ValueError("image_generation 不能同时包含 product_reference 与 printed_design。")
            if roles and not ({"product_reference", "printed_design"} & roles):
                raise ValueError(
                    "image_generation 的非空 inputAssets 必须包含 product_reference 或 printed_design。"
                )
        else:
            required_roles = {
                "logo_remove_bg": {"logo"},
                "print_render": {"product_reference", "logo"},
            }[self.type]
            missing_roles = required_roles - roles
            if missing_roles:
                raise ValueError(f"{self.type} 缺少必需 inputAssets role：{', '.join(sorted(missing_roles))}。")

        for role, field in _ASSET_PARAMETER_FIELDS.items():
            matching_assets = [asset for asset in self.inputAssets if asset.role == role]
            if not matching_assets:
                continue
            if len(matching_assets) > 1:
                raise ValueError(f"正式 inputAssets 不允许重复 role：{role}。")
            parameter_url = _parameter_url(self.parameters, field)
            asset_url = str(matching_assets[0].url)
            if parameter_url and parameter_url != asset_url:
                raise ValueError(
                    f"parameters.{field}.url 必须与 inputAssets role={role} 的 url 保持一致。"
                )

        product_asset = next((asset for asset in self.inputAssets if asset.role == "product_reference"), None)
        base_image_url = _parameter_url(self.parameters, "base_image")
        if product_asset is not None and base_image_url and base_image_url != str(product_asset.url):
            raise ValueError("parameters.base_image.url 必须与 inputAssets role=product_reference 的 url 保持一致。")

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
