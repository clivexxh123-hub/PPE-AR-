from typing import Any, Literal

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, ValidationError, field_validator, model_validator

from app.schemas.tasks import TaskStatus


_FORMAL_ALLOWED_ROLES = {
    "image_generation": {"product_reference", "printed_design"},
    "logo_remove_bg": {"logo"},
    "print_render": {"product_reference", "logo"},
}
_FORMAL_IMAGE_SOURCE_FIELDS = {
    "product_image",
    "logo_image",
    "base_image",
    "scene_image",
    "human_reference",
    "ppe_reference",
}
_IMAGE_SOURCE_KEYS = {"url", "file_id", "local_path"}

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def parse_expiration(value: str, field_name: str) -> datetime:
    """Parse a formal signed-URL expiry as an aware ISO-8601 datetime."""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是合法 ISO-8601 datetime。") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} 必须明确包含 timezone / UTC offset。")
    return parsed


def validate_future_expiration(value: str, field_name: str) -> datetime:
    parsed = parse_expiration(value, field_name)
    if parsed <= datetime.now(timezone.utc):
        raise ValueError(f"{field_name} 已过期。")
    return parsed


def _has_image_source(value: Any) -> bool:
    return isinstance(value, dict) and any(value.get(key) is not None for key in _IMAGE_SOURCE_KEYS)


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
        try:
            _HTTP_URL_ADAPTER.validate_python(self.callback.strip())
        except ValidationError as exc:
            raise ValueError("正式 callback 必须是合法的绝对 HTTP(S) URL。") from exc
        if self.output is None:
            raise ValueError("正式 /ai/tasks 协议要求 output。")

        output_fields = {"assetKey", "uploadUrl", "method", "requiredHeaders", "expiresAt"}
        missing_output = output_fields - self.output.model_fields_set
        if missing_output:
            raise ValueError(f"正式 output 缺少必传字段：{', '.join(sorted(missing_output))}。")
        if not self.output.expiresAt:
            raise ValueError("正式 output.expiresAt 不能为空。")
        validate_future_expiration(self.output.expiresAt, "output.expiresAt")

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
        for index, asset in enumerate(self.inputAssets):
            validate_future_expiration(asset.expiresAt or "", f"inputAssets[{index}].expiresAt")

        roles = {asset.role for asset in self.inputAssets}
        allowed_roles = _FORMAL_ALLOWED_ROLES[self.type]
        unsupported_roles = roles - allowed_roles
        if unsupported_roles:
            raise ValueError(f"{self.type} 不支持 inputAssets role：{', '.join(sorted(unsupported_roles))}。")
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

        for role in roles:
            if sum(asset.role == role for asset in self.inputAssets) > 1:
                raise ValueError(f"正式 inputAssets 不允许重复 role：{role}。")

        for field in _FORMAL_IMAGE_SOURCE_FIELDS:
            if _has_image_source(self.parameters.get(field)):
                raise ValueError(f"正式模式下 parameters.{field} 不能提供图片来源；请使用 inputAssets[].url。")

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
