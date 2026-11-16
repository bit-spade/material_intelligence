import io
import json
import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageOps


MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct"
PROMPT = (
    "Detect all interior items (furniture, decor, lighting, etc.) in the image. "
    'Return a JSON list of {"bbox_2d": [x1, y1, x2, y2], "label": "short descriptive name"}. '
    "Use pixel coordinates on the resized image."
)
_MODEL_LOCK = Lock()


class VisionError(Exception):
    """The local model or visual search could not complete."""


@dataclass(frozen=True)
class Detection:
    label: str
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class VisualMatch:
    title: str
    url: str
    source: str


def open_room_image(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as uploaded:
            image = ImageOps.exif_transpose(uploaded).convert("RGB")
    except (OSError, Image.DecompressionBombError) as exc:
        raise VisionError("Could not open this room image. Use a valid JPG, PNG, or WebP file.") from exc
    image.thumbnail((1800, 1800))
    return image


def parse_detections(
    text: str, image_size: tuple[int, int], model_size: tuple[int, int]
) -> list[Detection]:
    """Retain complete boxes when Qwen's output ends in a truncated JSON list."""
    width, height = image_size
    scale_x, scale_y = width / model_size[0], height / model_size[1]
    detections = []
    for match in re.finditer(r'\{(?:[^{}"]|"(?:[^"\\]|\\.)*")*\}', text):
        try:
            entry = json.loads(match.group())
            label = entry["label"]
            box = entry["bbox_2d"]
            if not isinstance(label, str) or not label.strip() or not isinstance(box, list) or len(box) != 4:
                continue
            if not all(type(value) in (int, float) and math.isfinite(value) for value in box):
                continue
            x1, y1, x2, y2 = box
        except (ValueError, KeyError, OverflowError):
            continue
        left, right = max(0, x1), min(model_size[0], x2)
        top, bottom = max(0, y1), min(model_size[1], y2)
        if left >= right or top >= bottom:
            continue
        pixels = (
            math.floor(left * scale_x), math.floor(top * scale_y),
            min(width, math.ceil(right * scale_x)), min(height, math.ceil(bottom * scale_y)),
        )
        detections.append(Detection(label.strip()[:100], pixels))
    return list(dict.fromkeys(detections))


def vision_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except (ImportError, OSError):
        return False


@lru_cache(maxsize=1)
def _load_model():
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration

    quantization = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
    )
    processor = AutoProcessor.from_pretrained(MODEL_ID, max_pixels=1280 * 28 * 28)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        MODEL_ID, quantization_config=quantization, device_map="auto",
    )
    return model.eval(), processor


def detect_room_items(image: Image.Image) -> list[Detection]:
    if not vision_available():
        raise VisionError("Room scanning requires the vision dependencies and a CUDA-enabled runtime.")
    import torch

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    try:
        with _MODEL_LOCK, torch.inference_mode():
            model, processor = _load_model()
            prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[prompt], images=[image], return_tensors="pt").to(model.device)
            output = model.generate(**inputs, max_new_tokens=1024, do_sample=False)
            generated = output[:, inputs["input_ids"].shape[1]:]
            text = processor.batch_decode(generated, skip_special_tokens=True)[0]
            _, grid_h, grid_w = inputs["image_grid_thw"][0].tolist()
            patch_size = processor.image_processor.patch_size
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise VisionError("Qwen could not scan this image. Check the vision installation and GPU memory.") from exc
    return parse_detections(text, image.size, (grid_w * patch_size, grid_h * patch_size))


def find_visual_matches(crop: Image.Image, label: str, api_key: str | None = None) -> list[VisualMatch]:
    key = api_key or os.getenv("SERPAPI_API_KEY")
    if not key:
        raise VisionError("Visual search needs SERPAPI_API_KEY.")
    image = io.BytesIO()
    crop.save(image, format="JPEG", quality=90)
    try:
        upload = requests.post(
            "https://serpapi.com/image",
            files={"image": ("object.jpg", image.getvalue(), "image/jpeg")},
            data={"api_key": key}, timeout=20, allow_redirects=False,
        )
        upload.raise_for_status()
        image_id = upload.json().get("image_id")
        if not image_id:
            raise VisionError("SerpApi could not accept the selected crop.")
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "engine": "google_lens", "image_id": image_id, "api_key": key,
                "type": "visual_matches", "q": label, "country": "pl", "hl": "pl",
            },
            timeout=30, allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError, AttributeError) as exc:
        raise VisionError("Visual search failed. Check the SerpApi configuration or try again.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise VisionError("SerpApi could not find matches for this crop.")
    matches = []
    for item in payload.get("visual_matches") or []:
        if not isinstance(item, dict):
            continue
        title, url = item.get("title"), item.get("link", "")
        if not title or not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme in {"https", "http"} and parsed.hostname:
            matches.append(VisualMatch(str(title), url, str(item.get("source") or "")))
    return matches[:5]
