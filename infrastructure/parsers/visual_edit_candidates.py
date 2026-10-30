"""Conservative pixel-line candidate detector, not a redline interpreter.

Trusted OCR adapter supplies a decoded source crop and word bounds in the same
pixel coordinate system. Underlines/table rules can trigger review; no finding
from this heuristic establishes deletion, insertion or contractual effect.
"""
from PIL import Image


def has_midline_candidate(image: Image.Image, bounds: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = bounds
    if (any(type(value) is not int for value in bounds)
            or not 0 <= left < right <= image.width
            or not 0 <= top < bottom <= image.height
            or image.width * image.height > 16_000_000):
        raise ValueError("bounded crop and word geometry required")
    width, height = right - left, bottom - top
    if width < 8 or height < 8:
        return False
    gray = image.crop(bounds).convert("L")
    # A long continuous dark run crossing the middle of a word is only a
    # candidate. Ordinary glyph strokes tend to be separated by white gaps.
    for y in range(height // 3, 2 * height // 3 + 1):
        longest = current = 0
        for x in range(width):
            pixel = gray.getpixel((x, y))
            current = current + 1 if isinstance(pixel, int) and pixel < 100 else 0
            longest = max(longest, current)
        if longest * 5 >= width * 4:
            return True
    return False
