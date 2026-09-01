"""Post-generation identity preservation for human-wearing outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageChops


def lock_unmasked_regions(generated_path: Path, input_path: Path, mask_path: Path) -> dict[str, Any]:
    """Apply the existing contact-mask output invariant without changing it."""
    with Image.open(generated_path) as source:
        generated = source.convert("RGB")
    with Image.open(input_path) as source:
        original = source.convert("RGB")
    with Image.open(mask_path) as source:
        mask = source.convert("L")
    if original.size != generated.size or mask.size != generated.size:
        raise ValueError("human_wearing input, mask, and output dimensions must match for core lock.")
    locked = Image.composite(generated, original, mask)
    locked.save(generated_path, format="PNG")
    unchanged_mask = mask.point(lambda value: 255 if value == 0 else 0)
    unmasked_delta = ImageChops.multiply(ImageChops.difference(locked, original).convert("L"), unchanged_mask)
    unmasked_mismatch_pixels = sum(unmasked_delta.histogram()[1:])
    coverage = sum(mask.histogram()[128:]) / float(mask.width * mask.height)
    return {
        "applied": True, "method": "post_composite_unmasked_input_lock",
        "mask_coverage_ratio": round(coverage, 4), "unmasked_mismatch_pixels": unmasked_mismatch_pixels,
        "protected_regions": ["helmet_core", "eyes_face", "shirt", "body_outline", "background"],
    }
