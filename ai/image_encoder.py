"""
ai/image_encoder.py
Utility to encode image files as base64 data URLs for OpenAI vision API format.
"""
import base64
import mimetypes
from pathlib import Path


def encode_image(path: str) -> tuple[str, str]:
    """Return (base64_data, mime_type) for OpenAI vision content."""
    data = Path(path).read_bytes()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return base64.b64encode(data).decode(), mime


def to_openai_image_block(path: str) -> dict:
    """Convert image file path to OpenAI vision content block."""
    b64, mime = encode_image(path)
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}