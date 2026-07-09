from fastapi import APIRouter, Depends
from app.models.schemas import AskRequest, AskResponse, ChatRequest, TelemetryDetail
from app.friday import FridayOrchestrator, IntentClassifier, PromptManager
from app.llm import LLMRouter
from app.memory import EmbeddingsManager
from app.core.config import settings
from app.core.dependencies import tool_registry
from fastapi.responses import StreamingResponse
from app.kernel import FridayKernel, KernelState
from app.execution.integration import create_execution_engine

router = APIRouter()

async def get_orchestrator() -> FridayOrchestrator:
    kernel = FridayKernel.get_instance()
    if kernel.state() != KernelState.READY:
        await kernel.boot()
        
    llm_router = kernel.get_service("llm_router")
    memory = kernel.get_service("memory_engine")
    runtime_bridge = kernel.get_service("runtime_scheduler_bridge")
    event_bus = kernel.get_service("event_bus")
    mission_runtime = kernel.get_service("mission_runtime")
    
    intent_classifier = IntentClassifier()
    prompt_manager = PromptManager()
    embeddings = EmbeddingsManager()
    
    execution_engine = create_execution_engine(kernel)
    
    return FridayOrchestrator(
        llm_router=llm_router,
        intent_classifier=intent_classifier,
        memory=memory,
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        embeddings=embeddings,
        runtime_bridge=runtime_bridge,
        event_bus=event_bus,
        mission_runtime=mission_runtime,
        execution_engine=execution_engine,
    )

@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    orchestrator: FridayOrchestrator = Depends(get_orchestrator)
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
        confirmation_token=getattr(result, "confirmation_token", None),
        mission_id=getattr(result, "mission_id", None)
    )

@router.post("/chat")
async def chat(
    request: ChatRequest,
    orchestrator: FridayOrchestrator = Depends(get_orchestrator)
):
    # Check confirmation loop first
    print("[DEBUG ROUTE] Entering chat endpoint", flush=True)
    requires_conf, token, warning, tool_name = await orchestrator.check_confirmation(
        prompt=request.prompt,
        confirmed=request.confirmed,
        confirmation_token=request.confirmation_token
    )
    print(f"[DEBUG ROUTE] check_confirmation returned: {requires_conf}", flush=True)
    
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
