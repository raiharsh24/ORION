import json
import urllib.request
import urllib.error

from app.plugin_sdk.base_plugin import BasePlugin


class WeatherPlugin(BasePlugin):
    id = "weather"
    name = "Weather"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Weather plugin loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["network"]

    def get_weather(self, city: str) -> dict:
        url = f"https://wttr.in/{city}?format=j1"
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read().decode())
            current = data.get("current_condition", [{}])[0]
            result = {
                "city": city,
                "temp_c": current.get("temp_C", "?"),
                "humidity": current.get("humidity", "?"),
                "description": current.get("weatherDesc", [{}])[0].get("value", ""),
                "wind_speed": current.get("windspeedKmph", "?"),
            }
            self.log_info(f"Weather for {city}: {result['temp_c']}C, {result['description']}")
            return result
        except urllib.error.URLError as e:
            self.log_error(f"Weather fetch failed: {e}")
            return {"error": str(e), "city": city}
        except Exception as e:
            self.log_error(f"Weather parse failed: {e}")
            return {"error": str(e), "city": city}
