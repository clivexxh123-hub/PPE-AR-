from __future__ import annotations

from dataclasses import dataclass
from string import Template

from app.core.config import settings


PRODUCT_DISPLAY_TEMPLATE_ID = "ppe_product_display"
SCENE_MARKETING_TEMPLATE_ID = "ppe_scene_marketing"
HUMAN_WEARING_TEMPLATE_ID = "ppe_human_wearing"

DEFAULT_TEMPLATE = Template(
    "Create a professional PPE marketing image for ${product_name}. "
    "Category: ${product_category}. Scene: ${scene}. Style: ${style}. "
    "The product should be clear, realistic, safe, and suitable for B2B sales material."
)

SCENE_MARKETING_TEMPLATE = """Commercial PPE product marketing photo featuring exactly one ${product_name}.
PPE category: ${product_category}. Preserve the reference product color, silhouette, and visible structure.
The product is centered, sharp, and the clear primary subject.
Marketing scene: ${scene}. Visual style: ${style}.
Use a realistic supporting background, professional lighting, and clean product-focused composition.
No text, labels, watermark, collage, duplicate products, or people.
${extra_instructions}"""

HUMAN_WEARING_TEMPLATE = """Realistic commercial PPE marketing photo of a person wearing one ${product_name}.
PPE category: ${product_category}. Correct product position on the body; preserve the PPE color, silhouette, and visible structure.
Scene: ${scene}. Visual style: ${style}.
Natural human pose, realistic lighting, and sharp product details.
${extra_instructions}"""

PPE_KEYWORDS = {
    "安全帽": "industrial safety helmet, hard hat, protective helmet",
    "面罩": "protective face shield, clear visor, transparent safety face shield",
    "手套": "protective work gloves, safety gloves, industrial gloves",
    "护目镜": "safety goggles, protective eyewear, clear industrial goggles",
    "反光背心": "high visibility safety vest, reflective vest, industrial safety vest",
}

_TEMPLATE_IDS_BY_MODE = {
    "": PRODUCT_DISPLAY_TEMPLATE_ID,
    "human_wearing": HUMAN_WEARING_TEMPLATE_ID,
    "scene_generation": SCENE_MARKETING_TEMPLATE_ID,
}
_KNOWN_TEMPLATE_IDS = frozenset(_TEMPLATE_IDS_BY_MODE.values())
_CORE_FIELDS = frozenset({"product_name", "product_category", "product_keywords", "scene", "style"})
_COMPOSITION_INSTRUCTIONS = {
    ("front", "half_body"): "Composition: front-facing person, half-body framing from the waist up.",
    ("front", "full_body"): "Composition: front-facing person, full-body framing with the complete figure visible.",
    ("slight_side", "half_body"): "Composition: person in a slight side view, half-body framing from the waist up.",
    ("slight_side", "full_body"): "Composition: person in a slight side view, full-body framing with the complete figure visible.",
}


@dataclass(frozen=True)
class PromptBuildResult:
    template_id: str
    selection_rule: str
    prompt: str
    view: str | None = None
    framing: str | None = None

    @property
    def summary(self) -> str:
        compact = " ".join(self.prompt.split())
        return compact if len(compact) <= 500 else f"{compact[:497]}..."

    def metadata(self) -> dict[str, str]:
        metadata = {
            "prompt_template_id": self.template_id,
            "prompt_template_selection": self.selection_rule,
            "final_prompt_summary": self.summary,
        }
        if self.view is not None:
            metadata["view"] = self.view
        if self.framing is not None:
            metadata["framing"] = self.framing
        return metadata


def list_prompt_template_ids() -> tuple[str, ...]:
    return tuple(sorted(_KNOWN_TEMPLATE_IDS))


def _product_keywords(product_name: str, product_category: str) -> str:
    source = f"{product_name} {product_category}"
    for keyword, english_prompt in PPE_KEYWORDS.items():
        if keyword in source:
            return english_prompt
    return "single PPE safety product, industrial protective equipment"


def _select_template_id(template_id: str | None, generation_mode: str | None) -> tuple[str, str]:
    normalized_mode = (generation_mode or "").strip().lower()
    if normalized_mode not in _TEMPLATE_IDS_BY_MODE:
        normalized_mode = ""
    expected_id = _TEMPLATE_IDS_BY_MODE[normalized_mode]
    if template_id is None or not template_id.strip():
        return expected_id, "generation_mode_default"

    selected_id = template_id.strip()
    if selected_id not in _KNOWN_TEMPLATE_IDS:
        supported = ", ".join(sorted(_KNOWN_TEMPLATE_IDS))
        raise ValueError(f"未知 Prompt template_id：{selected_id}。支持：{supported}。")
    if normalized_mode and selected_id != expected_id:
        raise ValueError(
            f"generation_mode={normalized_mode} 仅兼容 template_id={expected_id}，收到 {selected_id}。"
        )
    return selected_id, "explicit_template_id"


def _template_text(template_id: str) -> str:
    if template_id == PRODUCT_DISPLAY_TEMPLATE_ID:
        template_path = settings.prompt_template_dir / "ppe_marketing.txt"
        return template_path.read_text(encoding="utf-8") if template_path.exists() else DEFAULT_TEMPLATE.template
    if template_id == SCENE_MARKETING_TEMPLATE_ID:
        return SCENE_MARKETING_TEMPLATE
    return HUMAN_WEARING_TEMPLATE


def _extra_instructions(overrides: dict | None) -> str:
    if not overrides:
        return ""
    extras = [f"{key}: {value}" for key, value in overrides.items() if key not in _CORE_FIELDS and value]
    return f"Additional requirements: {'; '.join(extras)}." if extras else ""


def _composition_instruction(view: str | None, framing: str | None) -> tuple[str | None, str | None, str]:
    if view is None and framing is None:
        return None, None, ""
    normalized_view = (view or "").strip().lower()
    normalized_framing = (framing or "").strip().lower()
    instruction = _COMPOSITION_INSTRUCTIONS.get((normalized_view, normalized_framing))
    if instruction is None:
        supported = ", ".join(f"{item_view}+{item_framing}" for item_view, item_framing in _COMPOSITION_INSTRUCTIONS)
        raise ValueError(f"仅支持成对构图参数：{supported}。")
    return normalized_view, normalized_framing, instruction


def build_managed_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
    *,
    template_id: str | None = None,
    generation_mode: str | None = None,
    view: str | None = None,
    framing: str | None = None,
) -> PromptBuildResult:
    selected_id, selection_rule = _select_template_id(template_id, generation_mode)
    selected_view, selected_framing, composition = _composition_instruction(view, framing)
    values = {
        "product_name": product_name,
        "product_category": product_category,
        "product_keywords": _product_keywords(product_name, product_category),
        "scene": scene,
        "style": style,
        "extra_instructions": _extra_instructions(overrides),
    }
    if overrides:
        values.update({key: str(value) for key, value in overrides.items() if key in _CORE_FIELDS})
    template_text = _template_text(selected_id)
    prompt = Template(template_text).safe_substitute(values).strip()
    extra = values["extra_instructions"]
    if extra and "${extra_instructions}" not in template_text:
        prompt = f"{prompt}\n{extra}"
    if composition:
        # Keep the composition at the beginning so the persisted prompt summary
        # remains distinguishable even when a long template is truncated.
        prompt = f"{composition}\n{prompt}"
    return PromptBuildResult(
        template_id=selected_id,
        selection_rule=selection_rule,
        prompt=prompt,
        view=selected_view,
        framing=selected_framing,
    )


def build_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    return build_managed_prompt(
        product_name,
        product_category,
        scene,
        style,
        overrides,
        template_id=PRODUCT_DISPLAY_TEMPLATE_ID,
    ).prompt


def build_human_wearing_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    return build_managed_prompt(
        product_name,
        product_category,
        scene,
        style,
        overrides,
        template_id=HUMAN_WEARING_TEMPLATE_ID,
        generation_mode="human_wearing",
    ).prompt


def build_scene_generation_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    return build_managed_prompt(
        product_name,
        product_category,
        scene,
        style,
        overrides,
        template_id=SCENE_MARKETING_TEMPLATE_ID,
        generation_mode="scene_generation",
    ).prompt


def build_scene_background_prompt(
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    values = {"scene": scene, "style": style}
    if overrides:
        values.update({key: str(value) for key, value in overrides.items() if key in {"scene", "style"}})
    prompt = (
        "Realistic commercial PPE marketing background with clear empty foreground space for a product. "
        f"Marketing scene: {values['scene']}. Style: {values['style']}. "
        "Professional lighting, realistic depth, clean composition. "
        "No PPE products, no helmets, no people, no text, no labels, no watermark, no collage."
    )
    extra = _extra_instructions(overrides)
    return f"{prompt} {extra}".strip()
