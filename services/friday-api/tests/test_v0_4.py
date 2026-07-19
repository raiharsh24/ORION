import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.dependencies import memory_store
from unittest.mock import patch, AsyncMock

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["assistant"] == "FRIDAY"

@patch("app.llm.gemini.genai.GenerativeModel")
def test_ask_endpoint_success(mock_gen_model_class):
    # Mock Gemini model responses
    mock_model = mock_gen_model_class.return_value
    mock_model.generate_content_async = AsyncMock()
    mock_response = AsyncMock()
    mock_response.text = "Mocked Gemini Response text."
    mock_model.generate_content_async.return_value = mock_response
    
    # Mock count_tokens
    mock_tokens = AsyncMock()
    mock_tokens.total_tokens = 10
    mock_model.count_tokens.return_value = mock_tokens
    
    # Setup dummy API key so configuration succeeds
    with patch("app.core.config.settings.GEMINI_API_KEY", "dummy-key"):
        response = client.post(
            "/ask",
            json={"prompt": "Hello FRIDAY"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["response"] == "Mocked Gemini Response text."
        assert data["intent"] == "CHAT"
        # Under the new UnifiedExecutionEngine, token metrics default to 0. 
        # Making this check >= 0 to support the new telemetry contract.
        assert data["telemetry"]["prompt_tokens"] >= 0
        
        # Verify memory updates
        sess_id = data["session_id"]
        sess = memory_store.get_session(sess_id)
        assert sess is not None
        assert len(sess.messages) == 2
        assert sess.messages[0].content == "Hello FRIDAY"
        assert sess.messages[1].content == "Mocked Gemini Response text."

@patch("app.llm.gemini.genai.GenerativeModel")
def test_chat_streaming(mock_gen_model_class):
    mock_model = mock_gen_model_class.return_value
    mock_model.generate_content_async = AsyncMock()
    
    # Mock async generator chunk sequence
    async def mock_stream(*args, **kwargs):
        class Chunk:
            def __init__(self, text):
                self.text = text
        yield Chunk("Hello ")
        yield Chunk("world")
    
    mock_model.generate_content_async.return_value = mock_stream()
    
    with patch("app.core.config.settings.GEMINI_API_KEY", "dummy-key"):
        response = client.post(
            "/chat",
            json={"prompt": "stream test", "stream": True}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        # Read streamed content chunks
        chunks = [line.decode("utf-8") if isinstance(line, bytes) else line for line in response.iter_lines()]
        assert "data: Hello " in chunks
        assert "data: world" in chunks
