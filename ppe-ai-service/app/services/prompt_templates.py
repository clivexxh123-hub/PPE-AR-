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
