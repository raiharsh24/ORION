from app.plugin_sdk.base_plugin import BasePlugin


class CalculatorPlugin(BasePlugin):
    id = "calculator"
    name = "Calculator"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Calculator plugin loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def add(self, a: float, b: float) -> float:
        result = a + b
        self.log_debug(f"add({a}, {b}) = {result}")
        return result

    def subtract(self, a: float, b: float) -> float:
        result = a - b
        self.log_debug(f"subtract({a}, {b}) = {result}")
        return result

    def multiply(self, a: float, b: float) -> float:
        result = a * b
        self.log_debug(f"multiply({a}, {b}) = {result}")
        return result

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Division by zero")
        result = a / b
        self.log_debug(f"divide({a}, {b}) = {result}")
        return result
