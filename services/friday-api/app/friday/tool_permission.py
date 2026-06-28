import hmac
import hashlib
import os
import time
import json
from typing import Dict, Any, Optional
from loguru import logger
from app.friday.capability_registry import CapabilityMetadata

_pending_tokens: set[str] = set()

FRIDAY_SECRET_KEY_STR = os.getenv("FRIDAY_SECRET_KEY")
if not FRIDAY_SECRET_KEY_STR:
    from dotenv import load_dotenv
    # Resolve relative .env file paths
    dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    FRIDAY_SECRET_KEY_STR = os.getenv("FRIDAY_SECRET_KEY")

if not FRIDAY_SECRET_KEY_STR:
    FRIDAY_SECRET_KEY_STR = "dummy-friday-system-key-32-chars-long-standard"

FRIDAY_SECRET_KEY = FRIDAY_SECRET_KEY_STR.encode("utf-8")

class PermissionManager:
    """
    Enforces role permissions and confirms authorization token matching.
    """
    def check_permission(self, cap: CapabilityMetadata, user_role: str = "Developer") -> bool:
        if cap.permissions == "Public":
            return True
        if cap.permissions == "Trusted":
            return user_role in ["Developer", "Admin"]
        if cap.permissions in ["Dangerous", "Privileged", "Restricted"]:
            return user_role in ["Developer", "Admin"]
        return False

    def requires_confirmation(self, cap: CapabilityMetadata, args: Dict[str, Any]) -> bool:
        policy = cap.required_confirmation
        if policy == "Never":
            return False
        if policy == "Always":
            return True
        if policy == "DangerousOnly":
            if cap.id == "filesystem":
                op = args.get("op")
                return op in ["delete", "write"]
            if cap.id == "terminal":
                return True
        if policy in ["UserApproval", "PolicyDriven"]:
            return True
        return False

    def generate_token(self, tool_name: str, args: Dict[str, Any]) -> str:
        time_window = int(time.time() // 300)
        serialized_args = json.dumps(args, sort_keys=True)
        message = f"{tool_name}:{serialized_args}:{time_window}".encode("utf-8")
        token = hmac.new(FRIDAY_SECRET_KEY, message, hashlib.sha256).hexdigest()
        _pending_tokens.add(token)
        return token

    def validate_token(self, tool_name: str, args: Dict[str, Any], token: str) -> bool:
        if not token or token not in _pending_tokens:
            return False
        
        serialized_args = json.dumps(args, sort_keys=True)
        current_window = int(time.time() // 300)
        
        # Check current time window
        msg_current = f"{tool_name}:{serialized_args}:{current_window}".encode("utf-8")
        expected_current = hmac.new(FRIDAY_SECRET_KEY, msg_current, hashlib.sha256).hexdigest()
        
        # Check previous window
        msg_prev = f"{tool_name}:{serialized_args}:{current_window - 1}".encode("utf-8")
        expected_prev = hmac.new(FRIDAY_SECRET_KEY, msg_prev, hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(token, expected_current) or hmac.compare_digest(token, expected_prev):
            _pending_tokens.remove(token)
            return True
            
        return False
