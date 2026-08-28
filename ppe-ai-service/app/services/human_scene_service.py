"""Place a studio-model composite into the selected scene reference."""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.core.config import ensure_storage_dirs, settings
from app.services.human_anchor_service import analyze_body_anchors


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def _median_color(pixels: list[tuple[int, int, int]]) -> tuple[int, int, int]:
    if not pixels:
        return (220, 220, 220)
    return tuple(sorted(pixel[channel] for pixel in pixels)[len(pixels) // 2] for channel in range(3))


def _studio_subject_mask(
    reference: Image.Image,
    composite: Image.Image,
    box: dict[str, int],
) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Segment the untouched model, then add all deterministic PPE differences."""
    original = reference.convert("RGB")
    current = composite.convert("RGB")
    width, height = original.size
    pixels = original.load()
    subject = Image.new("L", original.size, 0)
    subject_pixels = subject.load()
    left_bound = max(0, box["x0"])
    right_bound = min(width, box["x1"])

    for y in range(max(0, box["y0"]), min(height, box["y1"])):
        left_samples = [
            pixels[x, y]
            for x in range(max(0, left_bound - 28), max(1, left_bound - 4))
        ]
        right_samples = [
            pixels[x, y]
            for x in range(min(width - 1, right_bound + 4), min(width, right_bound + 28))
        ]
        left_color = _median_color(left_samples)
        right_color = _median_color(right_samples)
        span = max(1, right_bound - left_bound - 1)
        for x in range(left_bound, right_bound):
            ratio = (x - left_bound) / span
            expected = tuple(
                round(left_color[channel] * (1 - ratio) + right_color[channel] * ratio)
                for channel in range(3)
            )
            if sum(abs(pixels[x, y][channel] - expected[channel]) for channel in range(3)) >= 48:
                subject_pixels[x, y] = 255

    # PPE layers were composited onto the exact fitted reference. Their pixel
    # delta safely restores helmet brims, glove cuffs and vest edges that extend
    # beyond the original human silhouette.
    ppe_delta = ImageChops.difference(current, original).convert("L").point(
        lambda value: 255 if value >= 18 else 0
    )
    combined = ImageChops.lighter(subject, ppe_delta).filter(ImageFilter.MedianFilter(3))
    return combined, subject, ppe_delta


def _keep_primary_subject(mask: Image.Image, face: dict[str, int]) -> Image.Image:
    """Keep the face-connected silhouette and discard studio shadows/speckles."""
    binary = mask.convert("L").point(lambda value: 255 if value >= 96 else 0).filter(ImageFilter.MinFilter(3))
    width, height = binary.size
    pixels = binary.load()
    center_x = max(0, min(width - 1, round((face["x0"] + face["x1"]) / 2)))
    center_y = max(0, min(height - 1, round((face["y0"] + face["y1"]) / 2)))
    seed: tuple[int, int] | None = None
    for radius in range(0, 32):
        for x in range(max(0, center_x - radius), min(width, center_x + radius + 1)):
            for y in (center_y - radius, center_y + radius):
                if 0 <= y < height and pixels[x, y]:
                    seed = (x, y)
                    break
            if seed:
                break
        if seed:
            break
    if seed is None:
        return binary

    component = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque([seed])
    component[seed[1] * width + seed[0]] = 1
    while pending:
        x, y = pending.popleft()
        for next_x, next_y in (
            (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1),
            (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1), (x + 1, y + 1),
        ):
            if not (0 <= next_x < width and 0 <= next_y < height):
                continue
            index = next_y * width + next_x
            if component[index] or not pixels[next_x, next_y]:
                continue
            component[index] = 1
            pending.append((next_x, next_y))

    result = Image.new("L", binary.size, 0)
    result.putdata([255 if value else 0 for value in component])
    return result.filter(ImageFilter.MaxFilter(3))


def _human_shape_prior(size: tuple[int, int], anchors: dict[str, object]) -> Image.Image:
    """Build a generous body corridor that excludes connected studio shadows."""
    prior = Image.new("L", size, 0)
    draw = ImageDraw.Draw(prior)
    face = anchors["face_box"]
    subject = anchors["subject_box"]
    face_width = float(anchors["face_width"])
    head_width = float(anchors["head_width"])
    head_height = float(anchors["head_height"])
    center_x = (face["x0"] + face["x1"]) / 2
    head_top = float(anchors["hairline_y"]) - head_height * 0.35
    head_bottom = face["y1"] + head_height * 0.35
    draw.ellipse(
        (
            center_x - head_width * 0.86,
            head_top,
            center_x + head_width * 0.86,
            head_bottom,
        ),
        fill=255,
    )

    shoulder_y = float(anchors["shoulder_y"])
    shoulder_left = float(anchors["shoulder_left"])
    shoulder_right = float(anchors["shoulder_right"])
    shoulder_width = max(1.0, shoulder_right - shoulder_left)
    hip_y = shoulder_y + (float(subject["y1"]) - shoulder_y) * 0.34
    torso_pad = max(8.0, face_width * 0.62)
    draw.polygon(
        (
            (shoulder_left - torso_pad, shoulder_y - face_width * 0.35),
            (shoulder_right + torso_pad, shoulder_y - face_width * 0.35),
            (center_x + shoulder_width * 0.72, hip_y),
            (center_x - shoulder_width * 0.72, hip_y),
        ),
        fill=255,
    )

    hands = sorted(anchors.get("hands", []), key=lambda item: item["x0"])
    arm_width = max(12, round(face_width * 0.72))
    shoulder_points = (
        (round(shoulder_left), round(shoulder_y + face_width * 0.3)),
        (round(shoulder_right), round(shoulder_y + face_width * 0.3)),
    )
    for index, hand in enumerate(hands[:2]):
        hand_center = (round((hand["x0"] + hand["x1"]) / 2), round((hand["y0"] + hand["y1"]) / 2))
        draw.line((shoulder_points[index], hand_center), fill=255, width=arm_width)
        radius = max(8, round(face_width * 0.55))
        draw.ellipse(
            (hand_center[0] - radius, hand_center[1] - radius, hand_center[0] + radius, hand_center[1] + radius),
            fill=255,
        )

    feet = sorted(anchors.get("feet", []), key=lambda item: item["x0"])
    if len(feet) >= 2:
        leg_width = max(16, round(face_width * 0.98))
        hip_centers = (center_x - shoulder_width * 0.24, center_x + shoulder_width * 0.24)
        for index, foot in enumerate(feet[:2]):
            foot_center = ((foot["x0"] + foot["x1"]) / 2, (foot["y0"] + foot["y1"]) / 2)
            draw.line(
                ((round(hip_centers[index]), round(hip_y - 4)), (round(foot_center[0]), round(foot_center[1]))),
                fill=255,
                width=leg_width,
            )
            foot_pad = max(7, round(face_width * 0.30))
            draw.ellipse(
                (
                    foot["x0"] - foot_pad,
                    foot["y0"] - foot_pad,
                    foot["x1"] + foot_pad,
                    foot["y1"] + foot_pad,
                ),
                fill=255,
            )
    else:
        draw.rectangle(
            (
                center_x - shoulder_width * 0.72,
                hip_y,
                center_x + shoulder_width * 0.72,
                subject["y1"],
            ),
            fill=255,
        )
    return prior.filter(ImageFilter.MaxFilter(5))


def _scene_with_ground_shadow(scene: Image.Image, anchors: dict[str, object]) -> tuple[Image.Image, dict[str, object]]:
    feet = anchors.get("feet", [])
    if not isinstance(feet, list) or len(feet) < 2:
        return scene, {"ground_shadow_applied": False}
    left = min(float(foot["x0"]) for foot in feet)
    right = max(float(foot["x1"]) for foot in feet)
    bottom = max(float(foot["y1"]) for foot in feet)
    face_width = float(anchors["face_width"])
    shadow_mask = Image.new("L", scene.size, 0)
    ImageDraw.Draw(shadow_mask).ellipse(
        (
            left - face_width * 0.55,
            bottom - face_width * 0.18,
            right + face_width * 0.75,
            bottom + face_width * 0.32,
        ),
        fill=88,
    )
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(max(2.0, face_width * 0.16)))
    darkened = Image.eval(scene.convert("RGB"), lambda value: round(value * 0.72))
    return Image.composite(darkened, scene.convert("RGB"), shadow_mask), {
        "ground_shadow_applied": True,
        "ground_shadow_bounds": [round(left), round(bottom), round(right)],
    }


def render_human_in_scene(
    task_id: str,
    human_path: Path,
    scene_path: Path,
    *,
    view: str,
    framing: str,
    subject_reference_path: Path | None = None,
) -> tuple[Path, Path]:
    ensure_storage_dirs()
    if not human_path.exists() or not scene_path.exists():
        raise ValueError("human composite or scene reference does not exist.")
    with Image.open(human_path) as source:
        human = source.convert("RGB")
    if subject_reference_path is not None and subject_reference_path.exists():
        with Image.open(subject_reference_path) as source:
            subject_reference = source.convert("RGB").resize(human.size, Image.Resampling.LANCZOS)
    else:
        subject_reference = human
    with Image.open(scene_path) as source:
        scene = _cover(source.convert("RGB"), human.size)

    anchors = analyze_body_anchors(subject_reference, view=view, framing=framing)
    box = anchors["subject_box"]
    raw_mask, reference_mask, ppe_delta = _studio_subject_mask(subject_reference, human, box)
    shape_prior = _human_shape_prior(human.size, anchors)
    constrained_mask = ImageChops.multiply(raw_mask, shape_prior)
    mask = _keep_primary_subject(constrained_mask, anchors["face_box"]).filter(ImageFilter.GaussianBlur(1.0))

    scene, shadow_metadata = _scene_with_ground_shadow(scene, anchors)
    result = Image.composite(human, scene, mask)
    output_dir = settings.output_dir / task_id
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / "human_scene_input.png"
    mask_path = output_dir / "human_scene_subject_mask.png"
    raw_mask_path = output_dir / "human_scene_subject_mask_raw.png"
    reference_mask_path = output_dir / "human_scene_reference_mask.png"
    ppe_delta_path = output_dir / "human_scene_ppe_delta_mask.png"
    shape_prior_path = output_dir / "human_scene_shape_prior.png"
    metadata_path = output_dir / "human_scene_metadata.json"
    result.save(image_path, format="PNG")
    mask.save(mask_path, format="PNG")
    raw_mask.save(raw_mask_path, format="PNG")
    reference_mask.save(reference_mask_path, format="PNG")
    ppe_delta.save(ppe_delta_path, format="PNG")
    shape_prior.save(shape_prior_path, format="PNG")
    metadata_path.write_text(
        json.dumps(
            {
                "engine": "pillow-selected-scene-composite",
                "scene_reference_path": str(scene_path),
                "human_composite_path": str(human_path),
                "output_path": str(image_path),
                "subject_mask_path": str(mask_path),
                "raw_subject_mask_path": str(raw_mask_path),
                "reference_mask_path": str(reference_mask_path),
                "ppe_delta_mask_path": str(ppe_delta_path),
                "shape_prior_path": str(shape_prior_path),
                "subject_reference_path": str(subject_reference_path) if subject_reference_path else str(human_path),
                "subject_mask_strategy": "original_model_row_background_plus_ppe_delta",
                **shadow_metadata,
                "selected_scene_used": True,
                "view": view,
                "framing": framing,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return image_path, metadata_path
