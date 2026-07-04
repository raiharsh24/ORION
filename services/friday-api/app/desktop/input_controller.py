import asyncio
import shutil
import subprocess
import time
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger


class InputController:
    def __init__(self) -> None:
        self._xdotool_available = shutil.which("xdotool") is not None
        self._xclip_available = shutil.which("xclip") is not None
        self._ydotool_available = shutil.which("ydotool") is not None
        self._env = {}

    async def mouse_move(self, x: int, y: int) -> bool:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "mousemove", str(x), str(y)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_move failed: {e}")
                return False
        elif self._ydotool_available:
            try:
                proc = subprocess.run(
                    ["ydotool", "mousemove", str(x), str(y)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_move (ydotool) failed: {e}")
                return False
        return False

    async def mouse_click(self, button: str = "left") -> bool:
        btn_map = {"left": 1, "middle": 2, "right": 3}
        btn = btn_map.get(button, 1)
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "click", str(btn)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_click failed: {e}")
                return False
        elif self._ydotool_available:
            try:
                proc = subprocess.run(
                    ["ydotool", "click", str(btn)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_click (ydotool) failed: {e}")
                return False
        return False

    async def mouse_double_click(self, button: str = "left") -> bool:
        btn_map = {"left": 1, "middle": 2, "right": 3}
        btn = btn_map.get(button, 1)
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "click", "--repeat", "2", str(btn)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_double_click failed: {e}")
                return False
        return False

    async def mouse_right_click(self) -> bool:
        return await self.mouse_click("right")

    async def mouse_drag_drop(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "mousemove", str(start_x), str(start_y)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if proc.returncode != 0:
                    return False
                proc = subprocess.run(
                    ["xdotool", "mousedown", "1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if proc.returncode != 0:
                    return False
                await asyncio.sleep(0.1)
                proc = subprocess.run(
                    ["xdotool", "mousemove", str(end_x), str(end_y)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                if proc.returncode != 0:
                    subprocess.run(["xdotool", "mouseup", "1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return False
                await asyncio.sleep(0.1)
                proc = subprocess.run(
                    ["xdotool", "mouseup", "1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"mouse_drag_drop failed: {e}")
                return False
        return False

    async def mouse_position(self) -> Optional[Tuple[int, int]]:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "getmouselocation"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                )
                if proc.returncode == 0:
                    parts = proc.stdout.strip().split()
                    x = y = 0
                    for p in parts:
                        if p.startswith("x:"):
                            x = int(p.split(":")[1])
                        elif p.startswith("y:"):
                            y = int(p.split(":")[1])
                    return (x, y)
            except Exception as e:
                logger.error(f"mouse_position failed: {e}")
        return None

    async def keyboard_type(self, text: str) -> bool:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "type", "--delay", "12", text],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"keyboard_type failed: {e}")
                return False
        elif self._ydotool_available:
            try:
                proc = subprocess.run(
                    ["ydotool", "type", text],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"keyboard_type (ydotool) failed: {e}")
                return False
        return False

    async def keyboard_hotkey(self, *keys: str) -> bool:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "key"] + list(keys),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return proc.returncode == 0
            except Exception as e:
                logger.error(f"keyboard_hotkey failed: {e}")
                return False
        return False

    async def keyboard_shortcut(self, combo: str) -> bool:
        keys = combo.replace("+", " ").lower().split()
        return await self.keyboard_hotkey(*keys)

    async def key_press(self, key: str) -> bool:
        return await self.keyboard_hotkey(key)

    async def get_active_window_id(self) -> Optional[str]:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "getactivewindow"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                )
                if proc.returncode == 0:
                    return proc.stdout.strip()
            except Exception as e:
                logger.error(f"get_active_window_id failed: {e}")
        return None

    async def get_screen_dimensions(self) -> Optional[Tuple[int, int]]:
        if self._xdotool_available:
            try:
                proc = subprocess.run(
                    ["xdotool", "getdisplaygeometry"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                )
                if proc.returncode == 0:
                    parts = proc.stdout.strip().split()
                    if len(parts) >= 2:
                        return (int(parts[0]), int(parts[1]))
            except Exception as e:
                logger.error(f"get_screen_dimensions failed: {e}")
        return None
