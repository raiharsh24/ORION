import pytest
import os
import shutil
import tempfile
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.tools.base_tool import BaseTool
from app.tools.filesystem import FilesystemTool
from app.tools.terminal import TerminalTool
from app.tools.browser import BrowserTool
from app.tools.clipboard import ClipboardTool
from app.tools.open_app import OpenAppTool
from app.friday.planner import Planner, ToolPlan
from app.friday.intent import IntentType
from app.friday.executor import ToolExecutor
from app.friday import ToolRegistry

client = TestClient(app)

# ----------------- 1. Tools Tests -----------------

@pytest.mark.anyio
async def test_filesystem_tool():
    tool = FilesystemTool()
    assert tool.name == "filesystem"
    assert "filesystem" in tool.description.lower()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")

        # Test write (does not require confirmation when path doesn't exist)
        assert tool.requires_confirmation(op="write", path=test_file) is False
        write_res = await tool.execute(op="write", path=test_file, content="hello action engine")
        assert "written successfully" in write_res
        assert os.path.exists(test_file)

        # Test write (requires confirmation when path exists)
        assert tool.requires_confirmation(op="write", path=test_file) is True

        # Test read
        read_res = await tool.execute(op="read", path=test_file)
        assert read_res == "hello action engine"

        # Test read non-existent
        bad_file = os.path.join(tmpdir, "missing.txt")
        read_bad = await tool.execute(op="read", path=bad_file)
        assert "Error: File not found" in read_bad

        # Test list
        list_res = await tool.execute(op="list", path=tmpdir)
        assert "test.txt" in list_res

        # Test delete (requires confirmation)
        assert tool.requires_confirmation(op="delete", path=test_file) is True
        del_res = await tool.execute(op="delete", path=test_file)
        assert "deleted successfully" in del_res
        assert not os.path.exists(test_file)


@pytest.mark.anyio
async def test_terminal_tool():
    tool = TerminalTool()
    assert tool.name == "terminal"

    # Test normal command (no confirmation)
    assert tool.requires_confirmation(cmd="echo hello") is False
    res = await tool.execute(cmd="echo hello")
    assert "hello" in res.strip()

    # Test dangerous command (requires confirmation)
    assert tool.requires_confirmation(cmd="rm -rf /") is True
    assert tool.requires_confirmation(cmd="kill -9 1234") is True


@pytest.mark.anyio
async def test_browser_tool():
    tool = BrowserTool()
    assert tool.name == "browser"
    assert tool.requires_confirmation(url="http://example.com") is False

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "Example Page Content"
        mock_get.return_value = mock_response

        res = await tool.execute(url="http://example.com")
        assert "Example Page Content" in res


@pytest.mark.anyio
async def test_clipboard_tool():
    tool = ClipboardTool()
    assert tool.name == "clipboard"

    # Test virtual copy/paste (headless fallback is robust)
    res_copy = await tool.execute(op="copy", text="friday_test_data")
    assert "copied text to clipboard" in res_copy.lower()

    res_paste = await tool.execute(op="paste")
    assert res_paste == "friday_test_data"


@pytest.mark.anyio
async def test_open_app_tool():
    tool = OpenAppTool()
    assert tool.name == "open_app"

    # Mock subprocess.Popen
    with patch("subprocess.Popen") as mock_popen:
        res = await tool.execute(app_name="echo", target="hi")
        assert "successfully launched" in res.lower()
        assert mock_popen.called


# ----------------- 2. Planner Tests -----------------

@pytest.mark.anyio
async def test_planner():
    planner = Planner()

    # File Operation plan
    plan = await planner.plan("delete file 'test.txt'", IntentType.FILE_OPERATION)
    assert plan is not None
    assert plan.tool_name == "filesystem"
    assert plan.args["op"] == "delete"
    assert plan.args["path"] == "test.txt"

    # Terminal command plan
    plan = await planner.plan("run command ls -la", IntentType.SYSTEM_COMMAND)
    assert plan is not None
    assert plan.tool_name == "terminal"
    assert plan.args["cmd"] == "ls -la"

    # Open app plan
    plan = await planner.plan("open browser http://google.com", IntentType.OPEN_APP)
    assert plan is not None
    assert plan.tool_name == "open_app"
    assert plan.args["app_name"] == "browser"
    assert plan.args["target"] == "http://google.com"


# ----------------- 3. Tool Executor Tests -----------------

@pytest.mark.anyio
async def test_executor_confirmation():
    registry = ToolRegistry()
    fs = FilesystemTool()
    registry.register("filesystem", fs)
    executor = ToolExecutor(registry)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        # Pre-create file to trigger overwrite warning
        with open(test_file, "w") as f:
            f.write("existing content")

        plan = ToolPlan(
            tool_name="filesystem",
            args={"op": "write", "path": test_file, "content": "new content"},
            reasoning="write test"
        )

        # 1. Without confirmation
        res = await executor.execute(plan, confirmed=False)
        assert res.confirmation_required is True
        assert res.confirmation_token is not None
        assert "overwrite" in res.output

        # 2. With confirmation
        res_confirmed = await executor.execute(
            plan,
            confirmed=True,
            confirmation_token=res.confirmation_token
        )
        assert res_confirmed.confirmation_required is False
        assert res_confirmed.success is True
        assert "written successfully" in res_confirmed.output


# ----------------- 4. Route Confirmation Loop Integration Tests -----------------

@patch("app.llm.gemini.genai.GenerativeModel")
def test_ask_route_confirmation_loop(mock_gen_model_class):
    # Mock LLM API setup
    mock_model = mock_gen_model_class.return_value
    mock_model.generate_content_async = AsyncMock()
    mock_response = AsyncMock()
    mock_response.text = "Model simulated response."
    mock_model.generate_content_async.return_value = mock_response

    # Setup counts
    mock_tokens = AsyncMock()
    mock_tokens.total_tokens = 12
    mock_model.count_tokens.return_value = mock_tokens

    # Create dummy temp file path for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmpf:
        tmp_name = tmpf.name
    try:
        # Prompt a destructive write on existing temp file
        prompt = f"write file '{tmp_name}' with 'new content'"
        
        with patch("app.core.config.settings.GEMINI_API_KEY", "dummy-key"):
            # 1. Unconfirmed request
            response = client.post(
                "/ask",
                json={"prompt": prompt}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["confirmation_required"] is True
            assert data["confirmation_token"] is not None
            assert "overwrite" in data["response"]

            # 2. Confirmed request
            conf_token = data["confirmation_token"]
            response_conf = client.post(
                "/ask",
                json={
                    "prompt": prompt,
                    "confirmed": True,
                    "confirmation_token": conf_token
                }
            )
            assert response_conf.status_code == 200
            data_conf = response_conf.json()
            assert data_conf["confirmation_required"] is False
            assert data_conf["success"] is True
            assert "Model simulated response" in data_conf["response"]
            
            # Verify file actually changed
            with open(tmp_name, "r") as f:
                assert f.read() == "new content"
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
