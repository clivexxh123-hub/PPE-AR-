import os
from pathlib import Path

from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parents[2]
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    app_name: str = "PPE AI 营销物料生成服务"
    app_version: str = "0.1.0"
    base_dir: Path = BASE_DIR
    storage_dir: Path = base_dir / "storage"
    input_dir: Path = storage_dir / "inputs"
    output_dir: Path = storage_dir / "outputs"
    task_dir: Path = storage_dir / "tasks"
    prompt_template_dir: Path = base_dir / "app" / "templates" / "prompt"
    default_output_format: str = "png"

    # AI_ENGINE 默认使用 mock；改为 comfyui 后会调用本机 ComfyUI 服务。
    ai_engine: str = os.getenv("AI_ENGINE", "mock").strip().lower()
    comfyui_base_url: str = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    comfyui_workflow_path: Path = Path(
        os.getenv("COMFYUI_WORKFLOW_PATH", str(base_dir / "app" / "templates" / "comfyui" / "text_to_image_workflow.json"))
    )
    comfyui_text_to_image_workflow_path: Path = Path(
        os.getenv("COMFYUI_TEXT_TO_IMAGE_WORKFLOW_PATH", str(comfyui_workflow_path))
    )
    comfyui_image_to_image_workflow_path: Path = Path(
        os.getenv("COMFYUI_IMAGE_TO_IMAGE_WORKFLOW_PATH", str(base_dir / "app" / "templates" / "comfyui" / "image_to_image_workflow.json"))
    )
    comfyui_image_node_id: str | None = os.getenv("COMFYUI_IMAGE_NODE_ID")
    comfyui_denoise: float = float(os.getenv("COMFYUI_DENOISE", "0.60"))
    comfyui_scene_generation_denoise: float = float(os.getenv("COMFYUI_SCENE_GENERATION_DENOISE", "0.35"))
    comfyui_positive_node_id: str | None = os.getenv("COMFYUI_POSITIVE_NODE_ID")
    comfyui_negative_node_id: str | None = os.getenv("COMFYUI_NEGATIVE_NODE_ID")
    comfyui_latent_node_id: str | None = os.getenv("COMFYUI_LATENT_NODE_ID")
    comfyui_save_node_id: str | None = os.getenv("COMFYUI_SAVE_NODE_ID")
    comfyui_timeout_seconds: int = int(os.getenv("COMFYUI_TIMEOUT_SECONDS", "300"))
    comfyui_poll_interval_seconds: float = float(os.getenv("COMFYUI_POLL_INTERVAL_SECONDS", "1.5"))
    comfyui_poll_attempts: int = int(os.getenv("COMFYUI_POLL_ATTEMPTS", "200"))
    task_center_base_url: str | None = os.getenv("TASK_CENTER_BASE_URL")
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local").strip().lower()
    comfyui_default_negative_prompt: str = os.getenv(
        "COMFYUI_NEGATIVE_PROMPT",
        (
            "low quality, blurry, noisy, low resolution, deformed product, distorted product, "
            "bad proportions, extra products, duplicate products, multiple panels, collage, grid layout, "
            "website screenshot, user interface, poster layout, magazine layout, text, typography, letters, "
            "caption, label, watermark, logo, brand mark, random symbols, cropped product, messy background, "
            "people, workers, human body, face, head, portrait, person wearing PPE, empty room, "
            "machinery as main subject, factory scene as main subject"
        ),
    )


settings = Settings()


def ensure_storage_dirs() -> None:
    for path in (settings.input_dir, settings.output_dir, settings.task_dir):
        path.mkdir(parents=True, exist_ok=True)

