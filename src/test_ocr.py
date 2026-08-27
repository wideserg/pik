"""Crop the cursor's text line before OCR; pick that line from OCR boxes."""

import unittest

from PIL import Image, ImageDraw

from ocr import crop_to_cursor_line, line_text_at, prepare_for_ocr


def _two_bars() -> Image.Image:
    img = Image.new("RGB", (200, 70), (20, 20, 20))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 8, 180, 24], fill=(255, 0, 0))
    d.rectangle([10, 42, 180, 58], fill=(0, 255, 0))
    return img


def _count(img: Image.Image) -> tuple[int, int]:
    reds = greens = 0
    for r, g, b in img.getdata():
        if r > 200 and g < 50:
            reds += 1
        elif g > 200 and r < 50:
            greens += 1
    return reds, greens


class CropToCursorLineTests(unittest.TestCase):
    def test_upper_bar_when_cursor_on_upper(self):
        cropped = crop_to_cursor_line(_two_bars(), cy=16)
        self.assertLess(cropped.height, 40)
        reds, greens = _count(cropped)
        self.assertGreater(reds, greens)

    def test_lower_bar_when_cursor_on_lower(self):
        cropped = crop_to_cursor_line(_two_bars(), cy=50)
        self.assertLess(cropped.height, 40)
        reds, greens = _count(cropped)
        self.assertGreater(greens, reds)

    def test_empty_image_returns_original_size(self):
        img = Image.new("RGB", (200, 70), (20, 20, 20))
        cropped = crop_to_cursor_line(img, cy=35)
        self.assertEqual(cropped.size, img.size)


class LineTextAtTests(unittest.TestCase):
    RESULT = {
        "text": "Composer 2.5GPT-5.4",
        "lines": [
            {
                "text": "Composer 2.5",
                "words": [
                    {
                        "text": "Composer",
                        "bounding_rect": {"x": 10, "y": 8, "width": 80, "height": 16},
                    },
                    {
                        "text": "2.5",
                        "bounding_rect": {"x": 95, "y": 8, "width": 30, "height": 16},
                    },
                ],
            },
            {
                "text": "GPT-5.4",
                "words": [
                    {
                        "text": "GPT-5.4",
                        "bounding_rect": {"x": 10, "y": 42, "width": 70, "height": 16},
                    },
                ],
            },
        ],
    }

    def test_picks_upper_line(self):
        self.assertEqual(line_text_at(self.RESULT, 16), "Composer 2.5")

    def test_picks_lower_line(self):
        self.assertEqual(line_text_at(self.RESULT, 50), "GPT-5.4")


class PrepareForOcrTests(unittest.TestCase):
    def test_pads_and_scales_short_strip(self):
        img = Image.new("RGB", (525, 26), (30, 30, 30))
        out, cy = prepare_for_ocr(img, 4)
        self.assertGreaterEqual(out.height, 128)
        self.assertGreater(cy, 4)

    def test_keeps_relative_cursor(self):
        img = Image.new("RGB", (100, 26), (30, 30, 30))
        _out, cy = prepare_for_ocr(img, 13, min_h=64, scale=2)
        # pad_top = (64-26)//2 = 19 → cy 32, then *2 → 64
        self.assertEqual(cy, 64)


if __name__ == "__main__":
    unittest.main()
