from fastapi import APIRouter, Depends
from app.models.schemas import AskRequest, AskResponse, ChatRequest, TelemetryDetail
from app.orion import OrionOrchestrator, IntentClassifier, PromptManager
from app.llm import GeminiAdapter, LLMRouter
from app.memory import EmbeddingsManager
from app.core.config import settings
from app.core.dependencies import memory_store, tool_registry
from fastapi.responses import StreamingResponse

router = APIRouter()

def get_orchestrator() -> OrionOrchestrator:
    gemini = GeminiAdapter(
        api_key=settings.GEMINI_API_KEY,
        model_name=settings.MODEL_NAME,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        top_p=settings.TOP_P
    )
    
    router_llm = LLMRouter()
    router_llm.register_provider("gemini", gemini, is_default=True)
    
    intent_classifier = IntentClassifier()
    prompt_manager = PromptManager()
    embeddings = EmbeddingsManager()
    
    return OrionOrchestrator(
        llm_router=router_llm,
        intent_classifier=intent_classifier,
        memory=memory_store,
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        embeddings=embeddings
    )

@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    orchestrator: OrionOrchestrator = Depends(get_orchestrator)
) -> AskResponse:
    # Pass confirmation details to orchestrator
    result = await orchestrator.process_query(
        prompt=request.prompt,
        confirmed=request.confirmed,
        confirmation_token=request.confirmation_token
    )
    
    telemetry_detail = None
    if result.telemetry:
        telemetry_detail = TelemetryDetail(
            model=result.telemetry.model,
            prompt_tokens=result.telemetry.prompt_tokens,
            completion_tokens=result.telemetry.completion_tokens,
            total_tokens=result.telemetry.total_tokens,
            error=result.telemetry.error
        )
        
    return AskResponse(
        success=result.success,
        intent=result.intent,
        response=result.response,
        tool_used=result.tool_used,
        tool_output=getattr(result, "tool_output", None),
        session_id=result.session_id,
        execution_time_ms=result.execution_time_ms,
        telemetry=telemetry_detail,
        confirmation_required=getattr(result, "confirmation_required", False),
        confirmation_token=getattr(result, "confirmation_token", None)
    )

@router.post("/chat")
async def chat(
    request: ChatRequest,
    orchestrator: OrionOrchestrator = Depends(get_orchestrator)
):
    # Check confirmation loop first
    requires_conf, token, warning, tool_name = await orchestrator.check_confirmation(
        prompt=request.prompt,
        confirmed=request.confirmed,
        confirmation_token=request.confirmation_token
    )
    
    if requires_conf:
        # Halt stream and return a flat JSON request for confirmation
        return AskResponse(
            success=False,
            intent="SYSTEM_COMMAND",
            response=warning or "Confirmation required.",
            tool_used=tool_name,
            session_id=request.session_id or "",
            execution_time_ms=0,
            confirmation_required=True,
            confirmation_token=token
        )

    if request.stream:
        async def event_generator():
            async for chunk in orchestrator.process_stream(
                prompt=request.prompt,
                session_id=request.session_id,
                confirmed=request.confirmed,
                confirmation_token=request.confirmation_token
            ):
                yield f"data: {chunk}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        result = await orchestrator.process_query(
            prompt=request.prompt,
            session_id=request.session_id,
            confirmed=request.confirmed,
            confirmation_token=request.confirmation_token
        )
        return result
