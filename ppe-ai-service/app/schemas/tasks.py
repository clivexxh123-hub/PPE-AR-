from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ImageSource(BaseModel):
    model_config = ConfigDict(title="图片来源")

    file_id: str | None = Field(default=None, description="通过 /files 上传后得到的文件 ID。")
    url: HttpUrl | None = Field(default=None, description="远程图片 URL，服务会先下载到本地再处理。")
    local_path: str | None = Field(default=None, description="本地开发调试用图片路径，生产环境不建议直接使用。")
    retryable_auth_failure: bool = Field(default=False, exclude=True, description="正式预签名 GET 的 401/403 可重新签发后重试。")


class GenerateRequest(BaseModel):
    model_config = ConfigDict(title="AI 图片生成请求")

    product_image: ImageSource | None = Field(default=None, description="产品图片，可先为空，后续用于图生图或参考图生成。")
    logo_image: ImageSource | None = Field(default=None, description="Logo 图片，可先为空，后续用于贴图或品牌元素融合。")
    product_name: str = Field(description="产品名称，例如安全帽、护目镜、防护服。")
    product_category: str = Field(description="产品分类，用于辅助生成 Prompt。")
    scene: str = Field(description="营销图场景描述。")
    style: str = Field(description="画面风格描述。")
    size: str = Field(description="输出尺寸，格式为 宽x高，例如 1024x1024。")
    prompt_overrides: dict[str, Any] = Field(default_factory=dict, description="Prompt 补充字段，用于前端或后端临时覆盖模板参数。")
    output_format: str = Field(description="输出图片格式，当前默认 png。")
    sync: bool = Field(default=False, description="是否同步执行。联调时可设为 true，正式环境建议异步。")

    @field_validator("product_name", "product_category", "scene", "style", "size", "output_format")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("该字段不能为空。")
        return value


class LogoPlaceRequest(BaseModel):
    model_config = ConfigDict(title="Logo 处理请求")

    base_image: ImageSource | None = Field(default=None, description="需要贴 Logo 的产品底图。")
    logo_image: ImageSource | None = Field(default=None, description="需要处理或贴到画面上的 Logo 图片。")
    position: str = Field(default="center", description="Logo 放置位置，例如 center、top-left、bottom-right。")
    scale: float = Field(default=0.25, description="Logo 相对底图的缩放比例。")
    position_x_ratio: float = Field(default=0.5, ge=0, le=1, description="Logo 左上角在可用横向区域中的比例。")
    position_y_ratio: float = Field(default=0.5, ge=0, le=1, description="Logo 左上角在可用纵向区域中的比例。")
    logo_width_ratio: float | None = Field(default=None, gt=0, le=1, description="Logo 宽度占底图宽度的比例。")
    opacity: float = Field(default=1.0, ge=0, le=1, description="Logo 不透明度。")
    output_format: str = Field(default="png", description="输出图片格式，当前默认 png。")
    sync: bool = Field(default=False, description="是否同步执行。联调时可设为 true，正式环境建议异步。")


class TaskResponse(BaseModel):
    model_config = ConfigDict(title="任务响应")

    task_id: str = Field(description="任务 ID，用于查询任务状态和结果。")
    status: TaskStatus = Field(description="任务状态：queued、running、succeeded、failed。")
    message: str = Field(description="任务说明信息。")
    result_url: str | None = Field(default=None, description="结果文件访问地址。")
    metadata_url: str | None = Field(default=None, description="本次任务元数据访问地址。")


class TaskRecord(TaskResponse):
    model_config = ConfigDict(title="任务记录")

    kind: str = Field(description="任务类型。")
    request: dict[str, Any] = Field(description="原始请求参数。")
    output_path: str | None = Field(default=None, description="结果文件在服务器上的本地路径。")
    metadata_path: str | None = Field(default=None, description="元数据文件在服务器上的本地路径。")
    error: str | None = Field(default=None, description="失败时的错误信息。")
