"""Prepare a stored photo for an AI model: smaller and JPEG, which is cheaper and faster.

The stored photo is already cleaned (no EXIF/GPS, see evidence/image_validation.py). Claude
works best with images up to about 1.15 megapixels; larger ones are scaled down anyway.
"""

import io

from PIL import Image

from app.integrations.ai_providers.base import ImagePart

MAX_LONG_EDGE = 1568


def prepare_for_model(data: bytes) -> ImagePart:
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        prepared = image.convert("RGB")
    prepared.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE))  # keeps the aspect ratio, never enlarges
    output = io.BytesIO()
    prepared.save(output, format="JPEG", quality=85)
    return ImagePart(data=output.getvalue(), media_type="image/jpeg")
