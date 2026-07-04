import io
import base64
from typing import Dict, Any, List, Optional
from loguru import logger

from app.vision.base import BaseVisionProvider


class VisionProvider(BaseVisionProvider):
    def __init__(self) -> None:
        self._pil_available = False
        self._tesseract_available = False
        self._load_dependencies()

    def _load_dependencies(self) -> None:
        try:
            from PIL import Image
            self._pil = Image
            self._pil_available = True
        except ImportError:
            logger.warning("Pillow not installed. Image processing will use stubs.")
            self._pil = None

        try:
            import pytesseract
            self._tesseract = pytesseract
            self._tesseract_available = True
        except ImportError:
            logger.info("pytesseract not installed. OCR will use placeholder output.")
            self._tesseract = None

    @property
    def name(self) -> str:
        return "default"

    def _open_image(self, image_data: bytes):
        if self._pil_available:
            return self._pil.open(io.BytesIO(image_data))
        return None

    def _image_to_base64(self, image_data: bytes) -> str:
        return base64.b64encode(image_data).decode("utf-8")

    def _get_image_format(self, image_data: bytes) -> str:
        if image_data[:4] == b'\x89PNG':
            return "png"
        if image_data[:2] in (b'\xff\xd8',):
            return "jpeg"
        if image_data[:4] == b'RIFF':
            return "webp"
        if image_data[:2] == b'BM':
            return "bmp"
        return "unknown"

    def _get_image_metadata(self, image_data: bytes) -> Dict[str, Any]:
        meta = {
            "size_bytes": len(image_data),
            "format": self._get_image_format(image_data),
        }
        if self._pil_available:
            try:
                img = self._pil.open(io.BytesIO(image_data))
                meta["width"] = img.width
                meta["height"] = img.height
                meta["mode"] = img.mode
            except Exception:
                pass
        return meta

    async def analyze_image(self, image_data: bytes, prompt: Optional[str] = None) -> Dict[str, Any]:
        metadata = self._get_image_metadata(image_data)
        description = f"Image ({metadata.get('width', '?')}x{metadata.get('height', '?')}, {metadata['format']}, {metadata['size_bytes']} bytes)"
        if prompt:
            description += f" | Prompt: {prompt}"
        logger.info(f"VisionProvider.analyze_image: {description}")
        return {
            "success": True,
            "provider": self.name,
            "description": description,
            "metadata": metadata,
        }

    async def ocr(self, image_data: bytes) -> str:
        metadata = self._get_image_metadata(image_data)
        if self._tesseract_available:
            try:
                img = self._pil.open(io.BytesIO(image_data))
                text = self._tesseract.image_to_string(img)
                logger.info(f"VisionProvider.ocr: extracted {len(text)} characters")
                return text
            except Exception as e:
                logger.error(f"VisionProvider.ocr failed: {e}")
                return f"[OCR Error: {e}]"
        else:
            logger.info("VisionProvider.ocr: pytesseract not available, returning placeholder")
            return "[OCR unavailable - pytesseract not installed]"

    async def detect_ui_elements(self, image_data: bytes) -> List[Dict[str, Any]]:
        metadata = self._get_image_metadata(image_data)
        logger.info(f"VisionProvider.detect_ui_elements: analyzing {metadata.get('width', '?')}x{metadata.get('height', '?')} image")
        if not self._pil_available or not image_data:
            return []
        try:
            img = self._pil.open(io.BytesIO(image_data)).convert("RGB")
            width, height = img.size
            pixels = img.load()
            elements = self._detect_buttons(img, pixels, width, height)
            elements += self._detect_inputs(img, pixels, width, height)
            elements += self._detect_text_blocks(img, pixels, width, height)
            if not elements:
                elements = self._detect_regions(img, pixels, width, height)
            return elements
        except Exception as e:
            logger.error(f"UI element detection failed: {e}")
            return []

    def _detect_regions(self, img: Any, pixels: Any, width: int, height: int) -> List[Dict[str, Any]]:
        elements = []
        step_x = max(width // 8, 10)
        step_y = max(height // 8, 10)
        min_region = 30
        for y in range(0, height - min_region, step_y):
            for x in range(0, width - min_region, step_x):
                region_pixels = []
                for dy in range(min(min_region, height - y)):
                    for dx in range(min(min_region, width - x)):
                        region_pixels.append(pixels[x + dx, y + dy])
                r_avg = sum(p[0] for p in region_pixels) / len(region_pixels)
                g_avg = sum(p[1] for p in region_pixels) / len(region_pixels)
                b_avg = sum(p[2] for p in region_pixels) / len(region_pixels)
                variance = sum(
                    (p[0] - r_avg) ** 2 + (p[1] - g_avg) ** 2 + (p[2] - b_avg) ** 2
                    for p in region_pixels
                ) / len(region_pixels)
                if variance > 500:
                    elem_type = "button" if variance > 2000 else "region"
                    elements.append({
                        "type": elem_type,
                        "text": "",
                        "bbox": {"x": x, "y": y, "width": min_region, "height": min_region},
                        "confidence": min(1.0, variance / 5000),
                    })
                    if len(elements) >= 15:
                        break
            if len(elements) >= 15:
                break
        return elements

    def _detect_buttons(self, img: Any, pixels: Any, width: int, height: int) -> List[Dict[str, Any]]:
        elements = []
        for y in range(0, height - 10, 15):
            for x in range(0, width - 30, 15):
                region = []
                for dy in range(min(20, height - y)):
                    for dx in range(min(60, width - x)):
                        p = pixels[x + dx, y + dy]
                        region.append(p)
                if not region:
                    continue
                r_avg = sum(p[0] for p in region) / len(region)
                b_avg = sum(p[2] for p in region) / len(region)
                if r_avg > 180 and b_avg < 100:
                    confidence = min(1.0, (r_avg - b_avg) / 200)
                    if confidence > 0.4:
                        elements.append({
                            "type": "button",
                            "text": "",
                            "bbox": {"x": x, "y": y, "width": 60, "height": 20},
                            "confidence": round(confidence, 2),
                        })
                        if len(elements) >= 8:
                            return elements
        return elements

    def _detect_inputs(self, img: Any, pixels: Any, width: int, height: int) -> List[Dict[str, Any]]:
        elements = []
        for y in range(0, height - 10, 15):
            for x in range(0, width - 30, 15):
                region = []
                for dy in range(min(24, height - y)):
                    for dx in range(min(100, width - x)):
                        p = pixels[x + dx, y + dy]
                        region.append(p)
                if not region:
                    continue
                white_count = sum(1 for p in region if p[0] > 240 and p[1] > 240 and p[2] > 240)
                ratio = white_count / len(region)
                if 0.6 < ratio < 0.95:
                    border_dark = sum(
                        1 for p in region
                        if p[0] < 100 and p[1] < 100 and p[2] < 100
                    )
                    border_ratio = border_dark / len(region)
                    if 0.01 < border_ratio < 0.2:
                        elements.append({
                            "type": "input",
                            "text": "",
                            "bbox": {"x": x, "y": y, "width": 100, "height": 24},
                            "confidence": round(min(1.0, ratio), 2),
                        })
                        if len(elements) >= 5:
                            return elements
        return elements

    def _detect_text_blocks(self, img: Any, pixels: Any, width: int, height: int) -> List[Dict[str, Any]]:
        elements = []
        for y in range(0, height - 10, 12):
            row_bright = 0
            row_dark = 0
            for x in range(0, width, 2):
                p = pixels[x, y]
                brightness = (p[0] + p[1] + p[2]) / 3
                if brightness < 80:
                    row_dark += 1
                elif brightness > 200:
                    row_bright += 1
            if 0.01 < row_dark / max(width // 2, 1) < 0.5:
                text_y = y
                text_height = 12
                for dy in range(1, 20):
                    if y + dy >= height:
                        break
                    row_dark_next = 0
                    for x in range(0, width, 2):
                        p = pixels[x, y + dy]
                        if (p[0] + p[1] + p[2]) / 3 < 80:
                            row_dark_next += 1
                    if row_dark_next / max(width // 2, 1) < 0.01:
                        text_height = dy
                        break
                elements.append({
                    "type": "text",
                    "text": "",
                    "bbox": {"x": 0, "y": text_y, "width": width, "height": text_height},
                    "confidence": round(0.5 + (row_dark / max(width // 2, 1)), 2),
                })
                if len(elements) >= 5:
                    break
        return elements
