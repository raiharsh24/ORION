import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.plugin_runtime.loader import RuntimePluginLoader
from app.plugin_runtime.sandbox import Sandbox
from app.plugin_runtime.monitor import PluginMonitor
from app.plugin_runtime.permissions import PermissionEnforcer
from app.plugins.registry import PluginRegistry as SdkPluginRegistry
from app.plugins.manifest import parse_manifest, validate_manifest
from app.plugin_sdk.base_plugin import BasePlugin
from app.plugin_sdk.plugin_context import PluginContext


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def sdk_registry(event_bus):
    return SdkPluginRegistry(event_bus=event_bus)


@pytest.fixture
def permission_enforcer():
    return PermissionEnforcer()


@pytest.fixture
def monitor():
    return PluginMonitor()


@pytest.fixture
def sandbox():
    return Sandbox()

@pytest.fixture
def loader(sdk_registry, sandbox, monitor, permission_enforcer):
    return RuntimePluginLoader(
        sdk_registry=sdk_registry,
        sandbox=sandbox,
        monitor=monitor,
        permission_enforcer=permission_enforcer,
    )


# ── Manifest Tests ───────────────────────────────────────────────────────

class TestExampleManifests:
    EXAMPLE_PLUGINS_DIR = Path(__file__).parent.parent / "plugins"

    def test_all_example_manifests_exist(self):
        assert self.EXAMPLE_PLUGINS_DIR.exists(), "plugins/ directory not found"
        plugin_dirs = [d for d in self.EXAMPLE_PLUGINS_DIR.iterdir() if d.is_dir()]
        assert len(plugin_dirs) >= 8, f"Expected >=8 example plugins, found {len(plugin_dirs)}"

    @pytest.mark.parametrize("plugin_id", [
        "calculator", "clipboard_manager", "weather", "git_helper",
        "file_search", "vscode_helper", "knowledge_search", "browser_automation",
    ])
    def test_manifest_valid(self, plugin_id):
        manifest_path = self.EXAMPLE_PLUGINS_DIR / plugin_id / "plugin.json"
        assert manifest_path.exists(), f"plugin.json not found for {plugin_id}"
        manifest = parse_manifest(manifest_path)
        assert manifest is not None, f"Failed to parse manifest for {plugin_id}"
        errors = validate_manifest(manifest)
        assert errors == [], f"Manifest validation errors for {plugin_id}: {errors}"
        assert manifest.id == plugin_id
        assert manifest.name
        assert manifest.version

    @pytest.mark.parametrize("plugin_id", [
        "calculator", "clipboard_manager", "weather", "git_helper",
        "file_search", "vscode_helper", "knowledge_search", "browser_automation",
    ])
    def test_entry_point_exists(self, plugin_id):
        entry = self.EXAMPLE_PLUGINS_DIR / plugin_id / "main.py"
        assert entry.exists(), f"main.py not found for {plugin_id}"
        content = entry.read_text()
        assert "BasePlugin" in content, f"main.py missing BasePlugin for {plugin_id}"

    @pytest.mark.parametrize("plugin_id", [
        "calculator", "clipboard_manager", "weather", "git_helper",
        "file_search", "vscode_helper", "knowledge_search", "browser_automation",
    ])
    def test_configuration_schema_optional(self, plugin_id):
        manifest_path = self.EXAMPLE_PLUGINS_DIR / plugin_id / "plugin.json"
        with open(manifest_path) as f:
            data = json.load(f)
        if "configuration_schema" in data:
            schema = data["configuration_schema"]
            assert "type" in schema


# ── BasePlugin Tests ─────────────────────────────────────────────────────

class TestBasePlugin:
    def test_instantiate(self):
        """BasePlugin cannot be instantiated directly (abstract)."""
        with pytest.raises(TypeError):
            BasePlugin()

    def test_concrete_plugin(self):
        class TestPlugin(BasePlugin):
            def get_manifest(self):
                return {"id": "test", "name": "Test", "version": "1.0.0"}

        p = TestPlugin()
        assert p.id == ""
        assert p.name == ""
        assert p.get_manifest()["id"] == "test"

    @pytest.mark.anyio
    async def test_lifecycle_hooks_default(self):
        class TestPlugin(BasePlugin):
            def get_manifest(self):
                return {"id": "test", "name": "Test", "version": "1.0.0"}

        p = TestPlugin()
        ctx = PluginContext(plugin_id="test", plugin_name="Test")
        p.set_context(ctx)

        await p.on_load()
        await p.on_init()
        await p.on_enable()
        await p.on_disable()
        await p.on_unload()
        await p.on_config_change({})

    def test_get_requested_permissions_default(self):
        class TestPlugin(BasePlugin):
            def get_manifest(self):
                return {"id": "test", "name": "Test", "version": "1.0.0"}

        p = TestPlugin()
        assert p.get_requested_permissions() == []

    def test_get_tools_default(self):
        class TestPlugin(BasePlugin):
            def get_manifest(self):
                return {"id": "test", "name": "Test", "version": "1.0.0"}

        p = TestPlugin()
        assert p.get_tools() == []


# ── PluginContext Tests ──────────────────────────────────────────────────

class TestPluginContext:
    def test_logging(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test")
        ctx.log_debug("debug")
        ctx.log_info("info")
        ctx.log_warning("warn")
        ctx.log_error("error")

    def test_settings(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test", config={"key": "val"})
        assert ctx.get_setting("key") == "val"
        assert ctx.get_setting("missing", "default") == "default"
        ctx.update_setting("key", "new_val")
        assert ctx.get_setting("key") == "new_val"

    def test_config_readonly(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test", config={"key": "val"})
        cfg = ctx.config
        assert cfg["key"] == "val"

    def test_register_tool_no_registry(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test")
        result = ctx.register_tool("test.tool", object())
        assert result is False

    def test_query_memory_no_memory(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test")
        import asyncio
        results = asyncio.run(ctx.query_memory("test"))
        assert results == []

    def test_publish_event_no_bus(self):
        ctx = PluginContext(plugin_id="test", plugin_name="Test")
        ctx.publish_event("test_topic", {"key": "val"})


# ── Example Plugin Integration Tests ─────────────────────────────────────

class TestExamplePlugins:
    @pytest.mark.parametrize("plugin_id", [
        "calculator", "clipboard_manager", "weather", "git_helper",
        "file_search", "vscode_helper", "knowledge_search", "browser_automation",
    ])
    def test_import_module(self, plugin_id):
        plugin_dir = Path(__file__).parent.parent / "plugins" / plugin_id
        main_py = plugin_dir / "main.py"
        assert main_py.exists()

        import importlib.util
        import sys
        spec = importlib.util.spec_from_file_location(f"plugin_{plugin_id}", str(main_py))
        assert spec is not None, f"Failed to create spec for {plugin_id}"
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"plugin_{plugin_id}"] = mod
        spec.loader.exec_module(mod)
        assert mod is not None

        from app.plugin_sdk.base_plugin import BasePlugin
        found = False
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                found = True
                instance = attr()
                assert instance.get_manifest()["id"] == plugin_id
                break
        assert found, f"No BasePlugin subclass found in {plugin_id}"

    def test_calculator_logic(self):
        from plugins.calculator.main import CalculatorPlugin
        calc = CalculatorPlugin()
        assert calc.add(2, 3) == 5
        assert calc.subtract(5, 3) == 2
        assert calc.multiply(4, 3) == 12
        assert calc.divide(10, 2) == 5
        with pytest.raises(ValueError, match="Division by zero"):
            calc.divide(1, 0)

    def test_calculator_manifest(self):
        from plugins.calculator.main import CalculatorPlugin
        calc = CalculatorPlugin()
        m = calc.get_manifest()
        assert m["id"] == "calculator"
        assert m["name"] == "Calculator"

    def test_file_search_manifest(self):
        from plugins.file_search.main import FileSearchPlugin
        fs = FileSearchPlugin()
        assert fs.get_requested_permissions() == ["filesystem.read"]

    def test_git_helper_permissions(self):
        from plugins.git_helper.main import GitHelperPlugin
        gh = GitHelperPlugin()
        assert "terminal.execute" in gh.get_requested_permissions()

    def test_knowledge_search_permissions(self):
        from plugins.knowledge_search.main import KnowledgeSearchPlugin
        ks = KnowledgeSearchPlugin()
        assert "memory.read" in ks.get_requested_permissions()

    def test_weather_permissions(self):
        from plugins.weather.main import WeatherPlugin
        wp = WeatherPlugin()
        assert "network" in wp.get_requested_permissions()

    def test_browser_automation_permissions(self):
        from plugins.browser_automation.main import BrowserAutomationPlugin
        ba = BrowserAutomationPlugin()
        assert "network" in ba.get_requested_permissions()
        assert "browser.control" in ba.get_requested_permissions()

    def test_vscode_helper_permissions(self):
        from plugins.vscode_helper.main import VSCodeHelperPlugin
        vsc = VSCodeHelperPlugin()
        assert "terminal.execute" in vsc.get_requested_permissions()

    def test_clipboard_permissions(self):
        from plugins.clipboard_manager.main import ClipboardPlugin
        cp = ClipboardPlugin()
        assert "desktop.access" in cp.get_requested_permissions()

    def test_file_search_by_name(self, tmp_path):
        from plugins.file_search.main import FileSearchPlugin
        (tmp_path / "test.txt").write_text("hello")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "data.log").write_text("log data")

        fs = FileSearchPlugin()
        results = fs.search_by_name("*.txt", root_dir=str(tmp_path))
        assert "test.txt" in results
        results2 = fs.search_by_name("*.log", root_dir=str(tmp_path))
        assert "sub/data.log" in results2

    def test_file_search_by_content(self, tmp_path):
        from plugins.file_search.main import FileSearchPlugin
        (tmp_path / "doc.txt").write_text("The quick brown fox")
        (tmp_path / "other.log").write_text("jumps over the lazy dog")

        fs = FileSearchPlugin()
        results = fs.search_by_content("fox", root_dir=str(tmp_path))
        assert len(results) >= 1
        assert "doc.txt" in results

    def test_git_helper_smoke(self):
        from plugins.git_helper.main import GitHelperPlugin
        gh = GitHelperPlugin()
        result = gh.status()
        assert isinstance(result, str)

    @pytest.mark.anyio
    async def test_lifecycle_hooks_example_plugin(self):
        from plugins.calculator.main import CalculatorPlugin
        calc = CalculatorPlugin()
        ctx = PluginContext(plugin_id="calculator", plugin_name="Calculator")
        calc.set_context(ctx)
        await calc.on_load()
        await calc.on_enable()
        await calc.on_disable()
        await calc.on_unload()


# ── Runtime Loader Tests ─────────────────────────────────────────────────

class TestRuntimeLoader:
    def test_loader_import_module(self, loader, tmp_path):
        plugin_dir = tmp_path / "test_plugin"
        plugin_dir.mkdir()
        manifest = {
            "id": "test_plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "entry_point": "main",
            "permissions": [],
            "dependencies": [],
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
        (plugin_dir / "main.py").write_text("""
from app.plugin_sdk.base_plugin import BasePlugin

class TestPlugin(BasePlugin):
    id = "test_plugin"
    name = "Test Plugin"
    version = "1.0.0"

    def get_manifest(self):
        return {"id": self.id, "name": self.name, "version": self.version}
""")

        discovered = loader.discover(str(tmp_path))
        assert "test_plugin" in discovered

        import asyncio
        inst = asyncio.run(loader.load("test_plugin"))
        assert inst is not None
        assert inst.state.value == "loaded"

        plugin_instance = inst.metadata.get("plugin_instance")
        assert plugin_instance is not None
        assert plugin_instance.get_manifest()["id"] == "test_plugin"

    def test_loader_import_missing_entry_point(self, loader, tmp_path):
        plugin_dir = tmp_path / "no_entry"
        plugin_dir.mkdir()
        manifest = {
            "id": "no_entry",
            "name": "No Entry",
            "version": "1.0.0",
            "entry_point": "missing",
            "permissions": [],
            "dependencies": [],
        }
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest))

        discovered = loader.discover(str(tmp_path))
        assert "no_entry" in discovered

        import asyncio
        inst = asyncio.run(loader.load("no_entry"))
        assert inst is not None
        assert inst.state.value == "loaded"
        assert inst.metadata.get("plugin_instance") is None
