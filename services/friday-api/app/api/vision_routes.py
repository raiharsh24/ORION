import base64
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

router = APIRouter()

class AnalyzeRequest(BaseModel):
    image_base64: str
    prompt: str = ""

class VisionAnalysisResponse(BaseModel):
    success: bool
    description: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""

class VisionOCRResponse(BaseModel):
    success: bool
    text: str = ""
    char_count: int = 0

class VisionContextResponse(BaseModel):
    source: str = "upload"
    ocr_text: str = ""
    has_text: bool = False
    ui_elements: list = Field(default_factory=list)
    element_count: int = 0

async def _get_vision_engine():
    kernel = FridayKernel.get_instance()
    if kernel.state() == KernelState.STOPPED:
        await kernel.boot()
    engine = kernel.get_service("vision_engine")
    if not engine:
        raise HTTPException(status_code=503, detail="Vision engine not available")
    return engine

@router.post("/vision/analyze", response_model=VisionAnalysisResponse)
async def analyze_image(request: AnalyzeRequest) -> VisionAnalysisResponse:
    engine = await _get_vision_engine()
    try:
        image_data = base64.b64decode(request.image_base64)
    except Exception as e:
        return VisionAnalysisResponse(success=False, error=f"Invalid base64: {e}")
    result = await engine.analyze_image(image_data, request.prompt)
    return VisionAnalysisResponse(
        success=result.get("success", False),
        description=result.get("description", ""),
        metadata=result.get("metadata", {}),
        error=result.get("error", ""),
    )

@router.post("/vision/ocr", response_model=VisionOCRResponse)
async def ocr_image(request: AnalyzeRequest) -> VisionOCRResponse:
    engine = await _get_vision_engine()
    try:
        image_data = base64.b64decode(request.image_base64)
    except Exception as e:
        return VisionOCRResponse(success=False, error=f"Invalid base64: {e}")
    text = await engine.ocr(image_data)
    return VisionOCRResponse(success=True, text=text, char_count=len(text))

@router.post("/vision/upload")
async def upload_image(file: UploadFile = File(...), prompt: str = Form("")):
    engine = await _get_vision_engine()
    image_data = await file.read()
    result = await engine.analyze_image(image_data, prompt)
    return {
        "success": result.get("success", False),
        "filename": file.filename,
        "description": result.get("description", ""),
        "metadata": result.get("metadata", {}),
        "error": result.get("error", ""),
    }

@router.post("/vision/screenshot", response_model=VisionContextResponse)
async def screenshot_analysis() -> VisionContextResponse:
    engine = await _get_vision_engine()
    image_data = await engine.capture_screenshot()
    context = await engine.screen_context(image_data, source="api")
    return VisionContextResponse(
        source=context.get("source", "api"),
        ocr_text=context.get("ocr_text", ""),
        has_text=context.get("has_text", False),
        ui_elements=context.get("ui_elements", []),
        element_count=context.get("element_count", 0),
    )

@router.post("/vision/screenshot/analyze")
async def screenshot_with_analysis():
    engine = await _get_vision_engine()
    image_data = await engine.capture_screenshot()
    analysis = await engine.analyze_image(image_data, "Describe this screen in detail")
    text = await engine.ocr(image_data)
    return {
        "success": True,
        "analysis": analysis.get("description", ""),
        "ocr_text": text,
        "metadata": analysis.get("metadata", {}),
    }

@router.get("/vision/status")
async def vision_status() -> Dict[str, Any]:
    engine = await _get_vision_engine()
    return engine.health()
