"""Deterministic Logo/product colour collision checks for local print rendering."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from PIL import Image


Rgb = tuple[int, int, int]


def _visible_mean_rgb(image: Image.Image) -> Rgb:
    rgba = image.convert("RGBA")
    totals = [0.0, 0.0, 0.0]
    weight = 0.0
    for red, green, blue, alpha in rgba.getdata():
        if alpha <= 0:
            continue
        totals[0] += red * alpha
        totals[1] += green * alpha
        totals[2] += blue * alpha
        weight += alpha
    if weight <= 0:
        raise ValueError("Logo has no non-transparent pixels for colour collision detection.")
    return tuple(round(value / weight) for value in totals)  # type: ignore[return-value]


def _luminance(color: Rgb) -> float:
    red, green, blue = color
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255


def _similarity(first: Rgb, second: Rgb) -> float:
    distance = sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))
    return max(0.0, min(1.0, 1 - distance / (sqrt(3) * 255)))


@dataclass(frozen=True)
class LogoCollisionDecision:
    similarity: float
    collision: bool
    adjustment: str
    product_zone_rgb: Rgb
    logo_visible_rgb: Rgb
    product_zone_luminance: float

    def metadata(self) -> dict[str, object]:
        return {
            "logo_color_similarity": round(self.similarity, 6),
            "logo_color_collision": self.collision,
            "logo_color_adjustment": self.adjustment,
            "print_zone_mean_rgb": list(self.product_zone_rgb),
            "logo_visible_mean_rgb": list(self.logo_visible_rgb),
            "print_zone_luminance": round(self.product_zone_luminance, 6),
        }


def apply_logo_collision_rule(
    base: Image.Image,
    logo: Image.Image,
    printable_region_bounds: dict[str, int] | None,
    *,
    similarity_threshold: float,
    dark_luminance_threshold: float,
) -> tuple[Image.Image, LogoCollisionDecision]:
    """Apply the agreed collision rule without touching the source logo."""
    if not 0 <= similarity_threshold <= 1:
        raise ValueError("logo collision similarity threshold must be between 0 and 1.")
    if not 0 <= dark_luminance_threshold <= 1:
        raise ValueError("logo collision dark luminance threshold must be between 0 and 1.")

    zone = base if printable_region_bounds is None else base.crop(
        (
            printable_region_bounds["left"],
            printable_region_bounds["top"],
            printable_region_bounds["right"],
            printable_region_bounds["bottom"],
        )
    )
    product_rgb = _visible_mean_rgb(zone)
    logo_rgb = _visible_mean_rgb(logo)
    similarity = _similarity(product_rgb, logo_rgb)
    collision = similarity >= similarity_threshold
    luminance = _luminance(product_rgb)

    if not collision:
        return logo, LogoCollisionDecision(similarity, False, "preserved", product_rgb, logo_rgb, luminance)

    adjustment = "pure_white" if luminance < dark_luminance_threshold else "pure_black"
    replacement = (255, 255, 255) if adjustment == "pure_white" else (0, 0, 0)
    adjusted = Image.new("RGBA", logo.size, (*replacement, 0))
    adjusted.putalpha(logo.convert("RGBA").getchannel("A"))
    return adjusted, LogoCollisionDecision(similarity, True, adjustment, product_rgb, logo_rgb, luminance)
