"""Validate an uploaded photo and produce a clean copy that is safe to store.

What we check and why:
- Size limit: protects the server and storage.
- Pillow must decode it as a real JPEG, PNG, or WebP. The browser's filename and
  Content-Type are ignored because anyone can fake them.
- Pixel limit: stops "decompression bombs" (tiny files that expand to huge images).
- Re-encoding drops ALL metadata (EXIF/XMP), including GPS location and phone model,
  which protects the citizen's privacy. The photo is rotated upright first, so
  dropping the EXIF orientation tag doesn't leave it sideways.
"""

import hashlib
import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import FileRejectedError, FileTooLargeError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
MAX_PIXELS = 40_000_000  # about 7700 x 5200, larger than any phone photo
MIN_DIMENSION = 64


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    checksum: str  # SHA-256 of the stored (cleaned) bytes


def validate_and_clean_image(raw: bytes, *, max_bytes: int) -> CleanImage:
    if len(raw) == 0:
        raise FileRejectedError("The file is empty.")
    if len(raw) > max_bytes:
        raise FileTooLargeError(
            f"The photo is larger than {max_bytes // (1024 * 1024)} MB. "
            "Please choose a smaller one.",
            {"max_bytes": max_bytes},
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as probe:
                image_format = probe.format
                width, height = probe.size
                if image_format not in ALLOWED_FORMATS:
                    raise FileRejectedError(
                        "Only JPEG, PNG, and WebP photos are accepted.",
                        {"detected_format": image_format},
                    )
                if width * height > MAX_PIXELS:
                    raise FileRejectedError("The photo's dimensions are too large.")
                if width < MIN_DIMENSION or height < MIN_DIMENSION:
                    raise FileRejectedError(
                        f"The photo is too small (minimum {MIN_DIMENSION}x{MIN_DIMENSION} pixels)."
                    )
                probe.verify()  # checks the file structure without decoding pixels

            # verify() leaves the image unusable, so open it again to decode the pixels.
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                upright = ImageOps.exif_transpose(image)
                cleaned = _reencode_without_metadata(upright, image_format)
    except FileRejectedError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise FileRejectedError("This file isn't a valid JPEG, PNG, or WebP photo.") from None
    except (OSError, SyntaxError, ValueError):  # truncated or corrupted image data
        raise FileRejectedError("The photo appears to be damaged. Please try another.") from None

    mime_type = ALLOWED_FORMATS[image_format]
    return CleanImage(
        data=cleaned,
        mime_type=mime_type,
        extension=EXTENSIONS[mime_type],
        width=upright.width,
        height=upright.height,
        checksum=hashlib.sha256(cleaned).hexdigest(),
    )


def _reencode_without_metadata(image: Image.Image, image_format: str) -> bytes:
    """Save the pixels into a fresh file. Pillow only writes metadata when asked, so the
    output has no EXIF, GPS, XMP, or comments."""
    output = io.BytesIO()
    if image_format == "JPEG":
        image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
    elif image_format == "PNG":
        if image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert("RGBA")
        image.save(output, format="PNG", optimize=True)
    else:  # WEBP
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA")
        image.save(output, format="WEBP", quality=90)
    return output.getvalue()
