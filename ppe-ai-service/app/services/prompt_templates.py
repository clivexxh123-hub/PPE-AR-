from string import Template

from app.core.config import settings


DEFAULT_TEMPLATE = Template(
    "Create a professional PPE marketing image for ${product_name}. "
    "Category: ${product_category}. Scene: ${scene}. Style: ${style}. "
    "The product should be clear, realistic, safe, and suitable for B2B sales material."
)

PPE_KEYWORDS = {
    "安全帽": "industrial safety helmet, hard hat, protective helmet",
    "面罩": "protective face shield, clear visor, transparent safety face shield",
    "手套": "protective work gloves, safety gloves, industrial gloves",
    "护目镜": "safety goggles, protective eyewear, clear industrial goggles",
    "反光背心": "high visibility safety vest, reflective vest, industrial safety vest",
}


def _product_keywords(product_name: str, product_category: str) -> str:
    source = f"{product_name} {product_category}"
    for keyword, english_prompt in PPE_KEYWORDS.items():
        if keyword in source:
            return english_prompt
    return "single PPE safety product, industrial protective equipment"


def build_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    template_path = settings.prompt_template_dir / "ppe_marketing.txt"
    template_text = template_path.read_text(encoding="utf-8") if template_path.exists() else DEFAULT_TEMPLATE.template
    values = {
        "product_name": product_name,
        "product_category": product_category,
        "product_keywords": _product_keywords(product_name, product_category),
        "scene": scene,
        "style": style,
    }
    if overrides:
        values.update({key: str(value) for key, value in overrides.items()})
    return Template(template_text).safe_substitute(values)


def build_human_wearing_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    """Build a PPE-wearing prompt without the product-only template constraints."""
    prompt = (
        f"Realistic commercial PPE marketing photo of a person wearing one {product_name}. "
        f"PPE category: {product_category}. Correct product position on the body, "
        f"preserve the PPE color, silhouette, and visible structure. "
        f"Scene: {scene}. Style: {style}. Natural human pose, realistic lighting, sharp product details."
    )
    if overrides:
        extra = " ".join(str(value) for value in overrides.values() if value)
        if extra:
            prompt = f"{prompt} {extra}."
    return prompt


def build_scene_generation_prompt(
    product_name: str,
    product_category: str,
    scene: str,
    style: str,
    overrides: dict | None = None,
) -> str:
    """Build a product-first marketing prompt for the scene_generation mode."""
    prompt = (
        f"Commercial PPE product marketing photo featuring exactly one {product_name}. "
        f"PPE category: {product_category}. Preserve the reference product color, silhouette, "
        f"and visible structure. The product is centered, sharp, and the clear primary subject. "
        f"Marketing scene: {scene}. Style: {style}. "
        "Use a realistic supporting background, professional lighting, and clean product-focused composition. "
        "No text, labels, watermark, collage, duplicate products, or people."
    )
    if overrides:
        extra = " ".join(str(value) for value in overrides.values() if value)
        if extra:
            prompt = f"{prompt} {extra}."
    return prompt
