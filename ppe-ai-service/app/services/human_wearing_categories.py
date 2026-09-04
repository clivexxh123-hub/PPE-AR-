"""Category strategies used by the human-wearing orchestrator.

This module deliberately contains the existing, deterministic category rules.
It is a structural seam: callers keep the same public functions and values,
while a future Helmet/Vest/Gloves implementation can change independently.
"""
from __future__ import annotations

from typing import Any

from PIL import Image


def _center(box: dict[str, int]) -> tuple[float, float]:
    return (box["x0"] + box["x1"]) / 2.0, (box["y0"] + box["y1"]) / 2.0


def resolve_ppe_placements(
    anchors: dict[str, Any], ppe_category: str, ppe_aspect: float
) -> list[dict[str, Any]]:
    """Resolve the unchanged category-specific body-anchor placements."""
    category = ppe_category.strip().lower()
    face = anchors["face_box"]
    face_center_x, _ = _center(face)
    face_width = float(anchors["face_width"])
    view = anchors["view"]
    slight_side = view == "slight_side"

    if category == "helmet":
        profile = (
            {"name": "helmet_slight_side_contact_v1", "width_ratio": 1.02, "center_x_face_width_offset": -0.085, "rotation": -4.0}
            if slight_side
            else {"name": "helmet_front_contact_v1", "width_ratio": 1.08, "center_x_face_width_offset": 0.0, "rotation": 0.0}
        )
        width = max(1, round(float(anchors["head_width"]) * profile["width_ratio"]))
        height = max(1, round(width * ppe_aspect))
        brim_y = float(anchors["eye_line_y"]) - face_width * 0.15
        return [{
            "role": "head", "center_x": face_center_x + profile["center_x_face_width_offset"] * face_width,
            "center_y": brim_y - height / 2, "width": width, "height": height,
            "rotation": profile["rotation"], "mirror": False,
            "helmet_geometry_profile": profile["name"], "head_top_y": anchors["head_top_y"],
            "head_width": anchors["head_width"], "eye_line_y": anchors["eye_line_y"], "brim_y": round(brim_y, 2),
        }]

    if category == "vest":
        width = max(1, round(float(anchors["shoulder_width"]) * 1.04))
        height = max(1, round(width * ppe_aspect))
        center_x = (anchors["shoulder_left"] + anchors["shoulder_right"]) / 2.0
        placement = {
            "role": "torso", "center_x": center_x,
            "center_y": float(anchors["shoulder_y"]) + height / 2, "width": width, "height": height,
            "rotation": -2.0 if slight_side else 0.0, "mirror": False,
        }
        placement["torso_quad"] = _vest_torso_quad(anchors, placement)
        return [placement]

    if category == "goggles":
        width = max(1, round(face_width * 1.48))
        height = max(1, round(width * ppe_aspect))
        eye_y = face["y0"] + (face["y1"] - face["y0"]) * 0.43
        return [{"role": "eyes", "center_x": face_center_x + (-0.035 * face_width if slight_side else 0),
                 "center_y": eye_y, "width": width, "height": height,
                 "rotation": -3.0 if slight_side else 0.0, "mirror": False}]

    if category == "gloves":
        if not anchors["hands_visible"]:
            raise ValueError("当前模特没有完整露出双手，不能可靠生成手套。请更换露出双手的半身或全身模特。")
        placements = []
        for index, hand in enumerate(sorted(anchors["hands"], key=lambda box: box["x0"])):
            hand_width = max(1, hand["x1"] - hand["x0"])
            hand_height = max(1, hand["y1"] - hand["y0"])
            height = max(round(face_width * 0.68), round(hand_height * 1.18))
            width = max(round(face_width * 0.42), round(height / max(0.2, ppe_aspect)), hand_width)
            center_x, center_y = _center(hand)
            placements.append({"role": "left_hand" if index == 0 else "right_hand", "center_x": center_x,
                               "center_y": center_y, "width": width, "height": height,
                               "rotation": (-8.0 if index == 0 else 8.0) + (-4.0 if slight_side else 0.0),
                               "mirror": index == 1})
        return placements

    if category == "boots":
        if anchors["framing"] != "full_body":
            raise ValueError("鞋子只能使用全身模特生成，请切换到同角度、同性别的全身模特。")
        if not anchors["feet_visible"]:
            raise ValueError("当前全身模特的双脚不完整，不能可靠生成鞋子。请更换双脚完整可见的模特。")
        placements = []
        for index, foot in enumerate(sorted(anchors["feet"], key=lambda box: box["x0"])):
            foot_width = max(1, foot["x1"] - foot["x0"])
            width = max(round(face_width * 0.82), round(foot_width * 1.12))
            height = max(1, round(width * ppe_aspect))
            center_x, _ = _center(foot)
            placements.append({"role": "left_foot" if index == 0 else "right_foot", "center_x": center_x,
                               "center_y": foot["y1"] - height / 2, "width": width, "height": height,
                               "rotation": -5.0 if index == 0 else 5.0, "mirror": index == 1})
        return placements

    raise ValueError(f"当前人体锚点暂不支持 PPE 类别：{category or 'unknown'}。")


def split_paired_product(image: Image.Image) -> list[Image.Image]:
    """Unchanged side-by-side glove/shoe source splitting."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 255 if value >= 24 else 0)
    width, height = rgba.size
    if width < 24 or height < 24:
        return [rgba]
    column_profile = alpha.resize((width, 1), Image.Resampling.BOX)
    search_left, search_right = max(1, round(width * 0.28)), min(width - 1, round(width * 0.72))
    split_x = min(range(search_left, search_right), key=lambda x: column_profile.getpixel((x, 0)))
    if column_profile.getpixel((split_x, 0)) > 40:
        return [rgba]
    parts: list[Image.Image] = []
    total_visible = max(1, sum(alpha.histogram()[128:]))
    for left, right in ((0, split_x), (split_x, width)):
        part_alpha = alpha.crop((left, 0, right, height))
        bounds = part_alpha.getbbox()
        visible = sum(part_alpha.histogram()[128:])
        if bounds is None or visible < total_visible * 0.18:
            return [rgba]
        parts.append(rgba.crop((left + bounds[0], bounds[1], left + bounds[2], bounds[3])))
    return parts


def warp_vest_rows(image: Image.Image, width: int, height: int, view: str) -> Image.Image:
    """Unchanged lightweight vest trapezoid transform."""
    base = image.resize((width, height), Image.Resampling.LANCZOS)
    warped = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    side_view = view == "slight_side"
    for row_index in range(height):
        progress = row_index / max(1, height - 1)
        if side_view:
            left_inset, right_inset = round(width * (0.15 * (1 - progress))), round(width * (0.04 * (1 - progress)))
        else:
            left_inset = right_inset = round(width * (0.09 * (1 - progress)))
        row_width = max(1, width - left_inset - right_inset)
        row = base.crop((0, row_index, width, row_index + 1)).resize((row_width, 1), Image.Resampling.BILINEAR)
        warped.alpha_composite(row, (left_inset, row_index))
    return warped


def _subject_span_at_y(anchors: dict[str, Any], y: int, center_x: float) -> tuple[float, float] | None:
    """Return the central silhouette span without adding a segmentation dependency."""
    mask = anchors.get("subject_mask")
    if not isinstance(mask, Image.Image) or not 0 <= y < mask.height:
        return None
    pixels = mask.convert("L")
    center = min(pixels.width - 1, max(0, round(center_x)))
    if pixels.getpixel((center, y)) < 32:
        return None
    left = center
    while left > 0 and pixels.getpixel((left - 1, y)) >= 32:
        left -= 1
    right = center
    while right < pixels.width - 1 and pixels.getpixel((right + 1, y)) >= 32:
        right += 1
    return float(left), float(right + 1)


def _vest_torso_quad(anchors: dict[str, Any], placement: dict[str, Any]) -> list[list[float]]:
    """Measure shoulder/waist corners for the VEST-GEO-01 pre-composite warp."""
    center_x = float(placement["center_x"])
    shoulder_y = float(anchors["shoulder_y"])
    width = float(placement["width"])
    height = float(placement["height"])
    waist_y = round(shoulder_y + height * 0.88)
    span = _subject_span_at_y(anchors, waist_y, center_x)
    if span is None:
        waist_left, waist_right = center_x - width * 0.43, center_x + width * 0.43
    else:
        waist_left, waist_right = span
        # A silhouette may include both arms. Keep the derived clothing edge in
        # a conservative torso window rather than allowing arm width to stretch
        # the product layer.
        waist_left = max(waist_left, center_x - width * 0.54)
        waist_right = min(waist_right, center_x + width * 0.54)
    return [
        [float(anchors["shoulder_left"]), shoulder_y],
        [float(anchors["shoulder_right"]), shoulder_y],
        [waist_right, float(waist_y)],
        [waist_left, float(waist_y)],
    ]


def _perspective_coefficients(
    destination: list[tuple[float, float]], source: list[tuple[float, float]]
) -> tuple[float, float, float, float, float, float, float, float]:
    """Solve Pillow's output-to-source projective transform without NumPy."""
    rows: list[list[float]] = []
    for (x, y), (u, v) in zip(destination, source, strict=True):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y, u])
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y, v])
    for pivot in range(8):
        best = max(range(pivot, 8), key=lambda row: abs(rows[row][pivot]))
        if abs(rows[best][pivot]) < 1e-8:
            raise ValueError("Vest torso quadrilateral is degenerate.")
        rows[pivot], rows[best] = rows[best], rows[pivot]
        factor = rows[pivot][pivot]
        rows[pivot] = [value / factor for value in rows[pivot]]
        for row in range(8):
            if row == pivot:
                continue
            factor = rows[row][pivot]
            rows[row] = [value - factor * pivot_value for value, pivot_value in zip(rows[row], rows[pivot], strict=True)]
    return tuple(rows[index][8] for index in range(8))


def warp_vest_torso_quad(
    image: Image.Image,
    width: int,
    height: int,
    torso_quad: list[list[float]],
    placement: dict[str, Any],
) -> Image.Image:
    """Project the catalog Vest into measured shoulder/waist geometry only."""
    origin_x = float(placement["center_x"]) - width / 2
    origin_y = float(placement["center_y"]) - height / 2
    destination = [(point[0] - origin_x, point[1] - origin_y) for point in torso_quad]
    source = [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]
    coefficients = _perspective_coefficients(destination, source)
    base = image.resize((width, height), Image.Resampling.LANCZOS)
    return base.transform(
        (width, height), Image.Transform.PERSPECTIVE, coefficients, Image.Resampling.BICUBIC
    )


def render_category_layer(
    category: str,
    image: Image.Image,
    width: int,
    height: int,
    view: str,
    placement: dict[str, Any] | None = None,
) -> Image.Image:
    """Keep category-specific geometry out of the public orchestrator."""
    if category == "vest":
        torso_quad = placement.get("torso_quad") if placement is not None else None
        if torso_quad is not None and placement is not None:
            return warp_vest_torso_quad(image, width, height, torso_quad, placement)
        return warp_vest_rows(image, width, height, view)
    return image.resize((width, height), Image.Resampling.LANCZOS)
