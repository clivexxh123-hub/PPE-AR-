"""Body-aware anchors for deterministic PPE placement.

The service deliberately exposes a small, model-independent anchor contract.
The current provider uses Pillow-only image measurements so it can run in the
existing AI service virtualenv.  A future DWPose provider can return the same
contract without changing the placement, mask, or generation pipeline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from PIL import Image, ImageChops, ImageFilter


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2.0


def _profile(mask: Image.Image, axis: str) -> list[float]:
    width, height = mask.size
    if axis == "row":
        strip = mask.resize((1, height), Image.Resampling.BOX)
        return [strip.getpixel((0, y)) / 255.0 for y in range(height)]
    strip = mask.resize((width, 1), Image.Resampling.BOX)
    return [strip.getpixel((x, 0)) / 255.0 for x in range(width)]


def _runs(profile: list[float], threshold: float) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(profile):
        if value >= threshold and start is None:
            start = index
        elif value < threshold and start is not None:
            result.append((start, index))
            start = None
    if start is not None:
        result.append((start, len(profile)))
    return result


def _merge_runs(runs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    if not runs:
        return []
    merged = [list(runs[0])]
    for start, end in runs[1:]:
        if start - merged[-1][1] <= max_gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _skin_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    mask = Image.new("L", rgb.size, 0)
    values = []
    for red, green, blue in rgb.getdata():
        chroma = max(red, green, blue) - min(red, green, blue)
        is_skin = (
            red >= 82
            and green >= 38
            and blue >= 18
            and red > green
            and red > blue
            and red - green >= 7
            and chroma >= 18
        )
        values.append(255 if is_skin else 0)
    mask.putdata(values)
    return mask


def detect_face_box(image: Image.Image, search_top_ratio: float = 0.64) -> Box | None:
    """Measure the dominant skin region in the upper frame."""
    width, height = image.size
    search_height = max(1, round(height * search_top_ratio))
    mask = _skin_mask(image.crop((0, 0, width, search_height)))
    rows = _profile(mask, "row")
    peak = max(rows, default=0.0)
    if peak <= 0.01:
        return None
    row_runs = _merge_runs(
        _runs(rows, max(0.018, peak * 0.28)),
        max(3, round(search_height * 0.045)),
    )
    if not row_runs:
        return None
    top, bottom = max(row_runs, key=lambda run: sum(rows[run[0] : run[1]]))

    cols = _profile(mask.crop((0, top, width, bottom)), "col")
    col_peak = max(cols, default=0.0)
    if col_peak <= 0.01:
        return None
    col_runs = _merge_runs(
        _runs(cols, max(0.018, col_peak * 0.28)),
        max(2, round(width * 0.018)),
    )
    if not col_runs:
        return None
    left, right = max(col_runs, key=lambda run: sum(cols[run[0] : run[1]]))
    face = Box(left, top, right, bottom)
    if not round(width * 0.035) <= face.width <= round(width * 0.52):
        return None
    return face


def _background_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    patch = max(2, round(min(rgb.size) * 0.025))
    samples: list[tuple[int, int, int]] = []
    for x0, y0 in (
        (0, 0),
        (rgb.width - patch, 0),
        (0, rgb.height - patch),
        (rgb.width - patch, rgb.height - patch),
    ):
        crop = rgb.crop((x0, y0, x0 + patch, y0 + patch)).resize((1, 1), Image.Resampling.BOX)
        samples.append(crop.getpixel((0, 0)))
    return tuple(sum(sample[channel] for sample in samples) // len(samples) for channel in range(3))


def _subject_mask(image: Image.Image) -> Image.Image:
    """Separate a studio subject from its mostly uniform corner background."""
    rgb = image.convert("RGB")
    background = _background_color(rgb)
    pixels = []
    for red, green, blue in rgb.getdata():
        distance = abs(red - background[0]) + abs(green - background[1]) + abs(blue - background[2])
        pixels.append(255 if distance >= 42 else 0)
    mask = Image.new("L", rgb.size, 0)
    mask.putdata(pixels)
    return mask.filter(ImageFilter.GaussianBlur(max(1, round(min(rgb.size) * 0.006)))).point(
        lambda value: 255 if value >= 42 else 0
    )


def _dominant_subject_box(mask: Image.Image, face: Box) -> Box:
    width, height = mask.size
    cols = _profile(mask, "col")
    runs = _merge_runs(_runs(cols, 0.025), max(2, round(width * 0.02)))
    center_candidates = [run for run in runs if run[0] <= face.center_x <= run[1]]
    left, right = max(center_candidates or runs or [(0, width)], key=lambda run: run[1] - run[0])
    cropped = mask.crop((left, 0, right, height))
    rows = _profile(cropped, "row")
    row_runs = _merge_runs(_runs(rows, 0.02), max(3, round(height * 0.025)))
    top, bottom = max(row_runs or [(0, height)], key=lambda run: run[1] - run[0])
    top = min(top, face.y0)
    bottom = max(bottom, face.y1)
    return Box(max(0, left), max(0, top), min(width, right), min(height, bottom))


def _mask_box(mask: Image.Image, bounds: Box, minimum_pixels: int) -> Box | None:
    crop = mask.crop((bounds.x0, bounds.y0, bounds.x1, bounds.y1))
    histogram = crop.histogram()
    if sum(histogram[128:]) < minimum_pixels:
        return None
    bbox = crop.point(lambda value: 255 if value >= 128 else 0).getbbox()
    if bbox is None:
        return None
    return Box(bounds.x0 + bbox[0], bounds.y0 + bbox[1], bounds.x0 + bbox[2], bounds.y0 + bbox[3])


def _hand_boxes(image: Image.Image, face: Box, subject: Box, shoulder_y: int) -> list[Box]:
    skin = _skin_mask(image)
    minimum = max(8, round(face.width * face.width * 0.012))
    center_margin = max(round(face.width * 0.55), round(image.width * 0.06))
    search_top = min(image.height - 1, max(shoulder_y, face.y1))
    searches = (
        Box(0, search_top, max(1, round(face.center_x - center_margin)), image.height),
        Box(min(image.width - 1, round(face.center_x + center_margin)), search_top, image.width, image.height),
    )
    boxes: list[Box] = []
    for bounds in searches:
        if bounds.width <= 1 or bounds.height <= 1:
            continue
        crop = skin.crop((bounds.x0, bounds.y0, bounds.x1, bounds.y1))
        rows = _profile(crop, "row")
        row_runs = _merge_runs(_runs(rows, 0.008), max(2, round(face.width * 0.08)))
        for row_start, row_end in row_runs:
            component_bounds = Box(
                bounds.x0,
                bounds.y0 + row_start,
                bounds.x1,
                bounds.y0 + row_end,
            )
            detected = _mask_box(skin, component_bounds, minimum)
            if detected is not None and detected.height >= max(3, round(face.width * 0.08)):
                boxes.append(detected)
                break
    return boxes


def _foot_boxes(image: Image.Image, subject: Box) -> list[Box]:
    mask = _skin_mask(image)
    lower_top = subject.y0 + round(subject.height * 0.82)
    center = round(image.width / 2)
    boxes: list[Box] = []
    for bounds in (
        Box(0, lower_top, center, image.height),
        Box(center, lower_top, image.width, image.height),
    ):
        detected = _mask_box(mask, bounds, max(6, round(subject.width * subject.height * 0.00025)))
        if detected is not None:
            boxes.append(detected)
    return boxes


def analyze_body_anchors(image: Image.Image, *, view: str, framing: str) -> dict[str, Any]:
    """Return a stable anchor contract for the PPE placement layer."""
    face = detect_face_box(image)
    if face is None:
        raise ValueError("无法识别模特面部，不能可靠定位 PPE。请更换正面或微侧身标准模特。")
    subject_mask = _subject_mask(image)
    subject = _dominant_subject_box(subject_mask, face)
    face_width = float(face.width)
    head_width = face_width * 1.32
    head_height = face_width * 1.54
    shoulder_y = min(image.height - 1, round(face.y0 + face_width * 1.75))
    expected_shoulder_width = face_width * 2.45
    shoulder_left = max(subject.x0, round(face.center_x - expected_shoulder_width / 2))
    shoulder_right = min(subject.x1, round(face.center_x + expected_shoulder_width / 2))
    hands = _hand_boxes(image, face, subject, shoulder_y)
    feet = _foot_boxes(image, subject) if framing == "full_body" else []
    return {
        "provider": "pillow_body_measurement_v1",
        "view": view,
        "framing": framing,
        "face_box": asdict(face),
        "subject_box": asdict(subject),
        "face_width": round(face_width, 2),
        "head_width": round(head_width, 2),
        "head_height": round(head_height, 2),
        "hairline_y": face.y0,
        "shoulder_y": shoulder_y,
        "shoulder_left": shoulder_left,
        "shoulder_right": shoulder_right,
        "shoulder_width": shoulder_right - shoulder_left,
        "hands": [asdict(box) for box in hands],
        "feet": [asdict(box) for box in feet],
        "hands_visible": len(hands) == 2,
        "feet_visible": len(feet) == 2 and framing == "full_body",
        "subject_mask": subject_mask,
    }


def _center(box: dict[str, int]) -> tuple[float, float]:
    return (box["x0"] + box["x1"]) / 2.0, (box["y0"] + box["y1"]) / 2.0


def resolve_ppe_placements(
    anchors: dict[str, Any],
    ppe_category: str,
    ppe_aspect: float,
) -> list[dict[str, Any]]:
    """Resolve one or two PPE placements from measured body anchors."""
    category = ppe_category.strip().lower()
    face = anchors["face_box"]
    face_center_x, _ = _center(face)
    face_width = float(anchors["face_width"])
    view = anchors["view"]
    slight_side = view == "slight_side"

    if category == "helmet":
        width = max(1, round(float(anchors["head_width"]) * 1.16))
        height = max(1, round(width * ppe_aspect))
        brow_y = float(anchors["hairline_y"]) + face_width * 0.45
        return [{
            "role": "head",
            "center_x": face_center_x + (-0.06 * face_width if slight_side else 0),
            "center_y": brow_y - height / 2,
            "width": width,
            "height": height,
            "rotation": -4.0 if slight_side else 0.0,
            "mirror": False,
        }]

    if category == "vest":
        width = max(1, round(float(anchors["shoulder_width"]) * 1.04))
        height = max(1, round(width * ppe_aspect))
        return [{
            "role": "torso",
            "center_x": (anchors["shoulder_left"] + anchors["shoulder_right"]) / 2.0,
            "center_y": float(anchors["shoulder_y"]) + height / 2,
            "width": width,
            "height": height,
            "rotation": -2.0 if slight_side else 0.0,
            "mirror": False,
        }]

    if category == "goggles":
        width = max(1, round(face_width * 1.48))
        height = max(1, round(width * ppe_aspect))
        eye_y = face["y0"] + (face["y1"] - face["y0"]) * 0.43
        return [{
            "role": "eyes",
            "center_x": face_center_x + (-0.035 * face_width if slight_side else 0),
            "center_y": eye_y,
            "width": width,
            "height": height,
            "rotation": -3.0 if slight_side else 0.0,
            "mirror": False,
        }]

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
            placements.append({
                "role": "left_hand" if index == 0 else "right_hand",
                "center_x": center_x,
                "center_y": center_y,
                "width": width,
                "height": height,
                "rotation": (-8.0 if index == 0 else 8.0) + (-4.0 if slight_side else 0.0),
                "mirror": index == 1,
            })
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
            placements.append({
                "role": "left_foot" if index == 0 else "right_foot",
                "center_x": center_x,
                "center_y": foot["y1"] - height / 2,
                "width": width,
                "height": height,
                "rotation": -5.0 if index == 0 else 5.0,
                "mirror": index == 1,
            })
        return placements

    raise ValueError(f"当前人体锚点暂不支持 PPE 类别：{category or 'unknown'}。")


def public_anchor_metadata(anchors: dict[str, Any]) -> dict[str, Any]:
    """Drop the in-memory mask before persisting JSON metadata."""
    return {key: value for key, value in anchors.items() if key != "subject_mask"}
