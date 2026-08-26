from pathlib import Path

from collections import deque

import json
from PIL import Image, ImageChops

from app.core.config import ensure_storage_dirs, settings


_POSITION_RATIOS = {
    "center": (0.5, 0.5),
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}

# Local semantic profiles are relative to detected product bounds, never fixed
# fixture pixels.  ``position`` remains the transport field, so this does not
# freeze a new back-end contract while still allowing database-backed images.
_PRINT_PROFILES = {
    "front": ("helmet_front_print_center", "helmet-view-profile", 0.50, 0.42, 0.56, 0.30, 0.28),
    "helmet-front-center": ("helmet_front_print_center", "helmet-view-profile", 0.50, 0.42, 0.56, 0.30, 0.28),
    "back": ("helmet_back_print_center", "helmet-view-profile", 0.50, 0.40, 0.56, 0.30, 0.28),
    "helmet-back-center": ("helmet_back_print_center", "helmet-view-profile", 0.50, 0.40, 0.56, 0.30, 0.28),
    "left": ("helmet_left_print_center", "helmet-view-profile", 0.50, 0.43, 0.58, 0.30, 0.28),
    "helmet-left-center": ("helmet_left_print_center", "helmet-view-profile", 0.50, 0.43, 0.58, 0.30, 0.28),
    "right": ("helmet_right_print_center", "helmet-view-profile", 0.50, 0.43, 0.58, 0.30, 0.28),
    "helmet-right-center": ("helmet_right_print_center", "helmet-view-profile", 0.50, 0.43, 0.58, 0.30, 0.28),
    "front_left_chest": ("vest_front_left_chest", "vest-region-profile", 0.68, 0.30, 0.28, 0.22, 0.20),
    "front-left-chest": ("vest_front_left_chest", "vest-region-profile", 0.68, 0.30, 0.28, 0.22, 0.20),
    "front_right_chest": ("vest_front_right_chest", "vest-region-profile", 0.32, 0.30, 0.28, 0.22, 0.20),
    "front-right-chest": ("vest_front_right_chest", "vest-region-profile", 0.32, 0.30, 0.28, 0.22, 0.20),
    "back_upper": ("vest_back_upper", "vest-region-profile", 0.50, 0.24, 0.64, 0.20, 0.34),
    "back-upper": ("vest_back_upper", "vest-region-profile", 0.50, 0.24, 0.64, 0.20, 0.34),
    "back_middle": ("vest_back_middle", "vest-region-profile", 0.50, 0.50, 0.68, 0.22, 0.36),
    "back-middle": ("vest_back_middle", "vest-region-profile", 0.50, 0.50, 0.68, 0.22, 0.36),
    "back_lower": ("vest_back_lower", "vest-region-profile", 0.50, 0.75, 0.62, 0.20, 0.32),
    "back-lower": ("vest_back_lower", "vest-region-profile", 0.50, 0.75, 0.62, 0.20, 0.32),
}


def _foreground_bounds(base: Image.Image) -> tuple[int, int, int, int]:
    """Estimate a product region from alpha or a near-solid corner background."""
    alpha = base.getchannel("A")
    alpha_min, _ = alpha.getextrema()
    if alpha_min < 255:
        bounds = alpha.point(lambda value: 255 if value > 16 else 0).getbbox()
        if bounds:
            return bounds

    rgb = base.convert("RGB")
    corners = [rgb.getpixel(point) for point in ((0, 0), (rgb.width - 1, 0), (0, rgb.height - 1), (rgb.width - 1, rgb.height - 1))]
    background_color = tuple(round(sum(color[index] for color in corners) / len(corners)) for index in range(3))
    background = Image.new("RGB", rgb.size, background_color)
    difference = ImageChops.difference(rgb, background).convert("L")
    bounds = difference.point(lambda value: 255 if value > 32 else 0).getbbox()
    if not bounds:
        return (0, 0, base.width, base.height)
    left, top, right, bottom = bounds
    if (right - left) * (bottom - top) >= base.width * base.height * 0.95:
        return (0, 0, base.width, base.height)
    return bounds


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def _resolve_logo_placement(
    base: Image.Image,
    logo: Image.Image,
    *,
    position: str | None,
    position_x_ratio: float | None,
    position_y_ratio: float | None,
    logo_width_ratio: float | None,
) -> tuple[
    Image.Image,
    int,
    int,
    float,
    float,
    float,
    str,
    str | None,
    dict[str, int] | None,
    dict[str, int],
]:
    placement_profile: str | None = None
    profile_mode: str | None = None
    profile_x_ratio: float | None = None
    profile_y_ratio: float | None = None
    profile_region_width_ratio: float | None = None
    profile_region_height_ratio: float | None = None
    profile_artwork_width_ratio: float | None = None
    if position is not None:
        normalized_position = position.strip().lower()
        if normalized_position and normalized_position != "auto":
            profile = _PRINT_PROFILES.get(normalized_position)
            if profile is not None:
                (
                    placement_profile,
                    profile_mode,
                    profile_x_ratio,
                    profile_y_ratio,
                    profile_region_width_ratio,
                    profile_region_height_ratio,
                    profile_artwork_width_ratio,
                ) = profile
            else:
                if normalized_position not in _POSITION_RATIOS:
                    raise ValueError(f"Unsupported position: {position}")
                named_x_ratio, named_y_ratio = _POSITION_RATIOS[normalized_position]
                if position_x_ratio is None:
                    position_x_ratio = named_x_ratio
                if position_y_ratio is None:
                    position_y_ratio = named_y_ratio

    placement_mode = "auto" if position_x_ratio is None and position_y_ratio is None and logo_width_ratio is None else "manual"
    if placement_profile is not None and position_x_ratio is None and position_y_ratio is None:
        placement_mode = str(profile_mode)
    bounds = _foreground_bounds(base)
    left, top, right, bottom = bounds
    product_width = max(1, right - left)
    product_height = max(1, bottom - top)
    margin = max(2, round(min(base.width, base.height) * 0.03))

    if logo_width_ratio is None:
        artwork_width_ratio = profile_artwork_width_ratio if profile_artwork_width_ratio is not None else 0.28
        final_width_ratio = min(0.40, max(0.08, product_width / base.width * artwork_width_ratio))
    else:
        final_width_ratio = float(logo_width_ratio)
    target_width = max(1, round(base.width * final_width_ratio))
    target_width = min(target_width, max(1, base.width - margin * 2))
    target_height = max(1, round(logo.height * target_width / logo.width))
    if target_height > max(1, base.height - margin * 2):
        target_height = max(1, base.height - margin * 2)
        target_width = max(1, round(logo.width * target_height / logo.height))
    logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)

    available_x = max(0, base.width - logo.width)
    available_y = max(0, base.height - logo.height)
    min_x = min(margin, available_x)
    min_y = min(margin, available_y)
    max_x = max(min_x, available_x - margin)
    max_y = max(min_y, available_y - margin)
    printable_region_bounds: dict[str, int] | None = None
    product_bounds = {"left": left, "top": top, "right": right, "bottom": bottom}
    if placement_profile is not None:
        region_width = max(1, round(product_width * float(profile_region_width_ratio)))
        region_height = max(1, round(product_height * float(profile_region_height_ratio)))
        region_center_x = left + product_width * float(profile_x_ratio)
        region_center_y = top + product_height * float(profile_y_ratio)
        region_left = _clamp(round(region_center_x - region_width / 2), left, max(left, right - region_width))
        region_top = _clamp(round(region_center_y - region_height / 2), top, max(top, bottom - region_height))
        region_right = min(right, region_left + region_width)
        region_bottom = min(bottom, region_top + region_height)
        printable_region_bounds = {
            "left": region_left,
            "top": region_top,
            "right": region_right,
            "bottom": region_bottom,
        }
        profile_margin = max(1, min(margin, region_width // 10, region_height // 10))
        profile_min_x = max(min_x, region_left + profile_margin)
        profile_max_x = min(max_x, region_right - logo.width - profile_margin)
        profile_min_y = max(min_y, region_top + profile_margin)
        profile_max_y = min(max_y, region_bottom - logo.height - profile_margin)
    else:
        profile_min_x, profile_max_x = min_x, max_x
        profile_min_y, profile_max_y = min_y, max_y

    if position_x_ratio is None and placement_profile is not None:
        centered_x = round((printable_region_bounds["left"] + printable_region_bounds["right"] - logo.width) / 2)
        x = _clamp(centered_x, profile_min_x, max(profile_min_x, profile_max_x))
    elif position_x_ratio is None:
        x = _clamp(round(left + product_width / 2 - logo.width / 2), min_x, max_x)
    else:
        x = _clamp(round((base.width - logo.width) * float(position_x_ratio)), min_x, max_x)
    if position_y_ratio is None and placement_profile is not None:
        centered_y = round((printable_region_bounds["top"] + printable_region_bounds["bottom"] - logo.height) / 2)
        y = _clamp(centered_y, profile_min_y, max(profile_min_y, profile_max_y))
    elif position_y_ratio is None:
        y = _clamp(round(top + product_height * 0.32 - logo.height / 2), min_y, max_y)
    else:
        y = _clamp(round((base.height - logo.height) * float(position_y_ratio)), min_y, max_y)

    available_width = max(1, base.width - logo.width)
    available_height = max(1, base.height - logo.height)
    return (
        logo,
        x,
        y,
        x / available_width,
        y / available_height,
        logo.width / base.width,
        placement_mode,
        placement_profile,
        printable_region_bounds,
        product_bounds,
    )

def render_printed_design(
    task_id: str,
    base_path: Path | None,
    logo_path: Path | None,
    position: str | None = None,
    position_x_ratio: float | None = None,
    position_y_ratio: float | None = None,
    logo_width_ratio: float | None = None,
    opacity: float = 1.0,
) -> tuple[Path, Path]:
    """Compose an RGBA logo onto a product image using relative coordinates."""
    ensure_storage_dirs()
    if base_path is None or not base_path.exists():
        raise ValueError(f"Base image does not exist: {base_path}")
    if logo_path is None or not logo_path.exists():
        raise ValueError(f"Logo image does not exist: {logo_path}")
    for name, value in (
        ("position_x_ratio", position_x_ratio),
        ("position_y_ratio", position_y_ratio),
        ("logo_width_ratio", logo_width_ratio),
        ("opacity", opacity),
    ):
        if value is None:
            continue
        if not 0 <= float(value) <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if logo_width_ratio is not None and float(logo_width_ratio) <= 0:
        raise ValueError("logo_width_ratio must be greater than 0")

    try:
        with Image.open(base_path) as source:
            base = source.convert("RGBA")
        with Image.open(logo_path) as source:
            logo = source.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"Unable to read image input: {exc}") from exc

    (
        logo,
        x,
        y,
        final_x_ratio,
        final_y_ratio,
        final_width_ratio,
        placement_mode,
        placement_profile,
        printable_region_bounds,
        product_bounds,
    ) = _resolve_logo_placement(
        base,
        logo,
        position=position,
        position_x_ratio=position_x_ratio,
        position_y_ratio=position_y_ratio,
        logo_width_ratio=logo_width_ratio,
    )
    if float(opacity) < 1:
        alpha = logo.getchannel("A").point(lambda value: round(value * float(opacity)))
        logo.putalpha(alpha)

    base.alpha_composite(logo, (x, y))

    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "printed_design.png"
    metadata_path = output_dir / "metadata.json"
    base.save(image_path, format="PNG")
    metadata = {
        "engine": "pillow-alpha-composite",
        "validation_status": "passed",
        "base_image": str(base_path),
        "logo_image": str(logo_path),
        "output_path": str(image_path),
        "width": base.width,
        "height": base.height,
        "has_alpha": True,
        "placement_mode": placement_mode,
        "placement_profile": placement_profile,
        "printable_region_bounds": printable_region_bounds,
        "product_bounds": product_bounds,
        "final_x_ratio": final_x_ratio,
        "final_y_ratio": final_y_ratio,
        "final_width_ratio": final_width_ratio,
        "position_x_ratio": final_x_ratio,
        "position_y_ratio": final_y_ratio,
        "logo_width_ratio": final_width_ratio,
        "opacity": float(opacity),
        "position_x": x,
        "position_y": y,
        "logo_width": logo.width,
        "logo_height": logo.height,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return image_path, metadata_path

def _remove_simple_background(image: Image.Image, tolerance: int = 24) -> tuple[Image.Image, str]:
    """Remove a border-connected, near-solid background without an AI model."""
    rgba = image.convert("RGBA")
    if rgba.getchannel("A").getextrema()[0] < 255:
        return rgba, "preserved_existing_alpha"

    rgb = rgba.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    background = Image.new("L", rgb.size, 0)
    background_pixels = background.load()

    def is_background_color(color: tuple[int, int, int], reference: tuple[int, int, int]) -> bool:
        return all(abs(component - expected) <= tolerance for component, expected in zip(color, reference))

    for start in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        reference = pixels[start]
        pending = deque([start])
        visited: set[tuple[int, int]] = set()
        while pending:
            x, y = pending.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))
            if not is_background_color(pixels[x, y], reference):
                continue
            background_pixels[x, y] = 255
            for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= next_x < width and 0 <= next_y < height:
                    pending.append((next_x, next_y))

    alpha = background.point(lambda value: 0 if value else 255)
    rgba.putalpha(alpha)
    return rgba, "border_flood_fill"


def normalize_logo(task_id: str, logo_path: Path | None, output_format: str = "png") -> tuple[Path, Path]:
    ensure_storage_dirs()
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "logo_normalized.png"
    metadata_path = output_dir / "metadata.json"

    if logo_path is None or not logo_path.exists():
        raise ValueError(f"Logo image does not exist: {logo_path}")
    try:
        with Image.open(logo_path) as source:
            image, background_method = _remove_simple_background(source)
    except OSError as exc:
        raise ValueError(f"Unable to read logo image: {exc}") from exc

    image.thumbnail((512, 512))
    canvas = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
    canvas.alpha_composite(image, ((512 - image.width) // 2, (512 - image.height) // 2))
    canvas.save(image_path, format="PNG")
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "pillow-simple-background-removal",
                "input_path": str(logo_path),
                "output_path": str(image_path),
                "output_format": "png",
                "has_alpha": True,
                "background_method": background_method,
                "output_width": canvas.width,
                "output_height": canvas.height,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return image_path, metadata_path
