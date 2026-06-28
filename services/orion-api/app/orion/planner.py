import re
from typing import Dict, Any, Optional
from app.orion.intent import IntentType
from pydantic import BaseModel

class ToolPlan(BaseModel):
    """
    Structured container for tool choices and kwargs.
    """
    tool_name: str
    args: Dict[str, Any]
    reasoning: str

class Planner:
    """
    Translates user query prompts and classified intent types into structured ToolPlans.
    """
    async def plan(self, prompt: str, intent: IntentType) -> Optional[ToolPlan]:
        prompt_lower = prompt.lower().strip()
        
        # 1. Check for Project Knowledge base / Codebase queries
        is_knowledge_query = (
            intent == IntentType.SEARCH_MEMORY or
            any(w in prompt_lower for w in [
                "where is", "how does", "what is implemented", "find in code",
                "search repository", "knowledge base", "documentation of",
                "explain class", "explain function", "where do we define"
            ])
        )
        if is_knowledge_query:
            return ToolPlan(
                tool_name="knowledge.search",
                args={"query": prompt},
                reasoning=f"Performing semantic search on knowledge base for query: '{prompt}'"
            )

        # 2. File Operations
        if intent == IntentType.FILE_OPERATION:
            op = "read"
            if any(w in prompt_lower for w in ["delete", "remove", "rm", "erase"]):
                op = "delete"
            elif any(w in prompt_lower for w in ["write", "create", "save", "overwrite"]):
                op = "write"
            elif any(w in prompt_lower for w in ["list", "ls", "dir", "show files"]):
                op = "list"
            
            path = None
            quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
            if quotes:
                path = quotes[0]
            else:
                words = prompt.split()
                for w in words:
                    if "." in w or "/" in w:
                        cleaned = w.strip(".,;:?!'\"`()")
                        if cleaned:
                            path = cleaned
                            break
            
            if not path:
                path = "file.txt"
                
            content = None
            if op == "write":
                if len(quotes) > 1:
                    content = quotes[1]
                else:
                    match = re.search(r'(?:content|text|with)\s+["\'`]?(.+?)["\'`]?$', prompt, re.IGNORECASE)
                    if match:
                        content = match.group(1)
                    else:
                        content = "nominal"
                        
            return ToolPlan(
                tool_name="filesystem",
                args={"op": op, "path": path, "content": content},
                reasoning=f"Identified file operation '{op}' on path '{path}'"
            )

        # 3. Terminal Execution
        elif intent == IntentType.SYSTEM_COMMAND:
            cmd = prompt
            for prefix in ["run command", "run", "execute", "terminal", "exec", "sh", "bash"]:
                if prompt_lower.startswith(prefix):
                    candidate = prompt[len(prefix):].strip()
                    if candidate:
                        cmd = candidate
                        break
            
            cmd = cmd.strip("\"'` ")
            return ToolPlan(
                tool_name="terminal",
                args={"cmd": cmd},
                reasoning=f"Identified terminal command run: '{cmd}'"
            )

        # 4. Web Search
        elif intent == IntentType.WEB_SEARCH:
            url = None
            url_match = re.search(r'(https?://\S+)', prompt)
            if url_match:
                url = url_match.group(1)
            else:
                words = prompt.split()
                for w in words:
                    if "." in w and not w.startswith(".") and not w.endswith("."):
                        cleaned = w.strip(".,;:?!'\"`()")
                        if cleaned:
                            url = f"https://{cleaned}"
                            break
            if not url:
                url = "https://google.com"

            return ToolPlan(
                tool_name="browser",
                args={"url": url},
                reasoning=f"Identified web browse request for URL '{url}'"
            )

        # 5. Open Application
        elif intent == IntentType.OPEN_APP:
            words = prompt.split()
            app_name = None
            for i, w in enumerate(words):
                if w.lower() in ["open", "launch", "start"] and i + 1 < len(words):
                    app_name = words[i+1].strip(".,;:?!'\"`()")
                    break
            
            if not app_name:
                app_name = "default"
                
            target = None
            quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
            if quotes:
                target = quotes[0]
            else:
                url_match = re.search(r'(https?://\S+)', prompt)
                if url_match:
                    target = url_match.group(1)
            
            return ToolPlan(
                tool_name="open_app",
                args={"app_name": app_name, "target": target},
                reasoning=f"Identified request to open application '{app_name}'"
            )

        # 6. Clipboard Interaction
        elif "clipboard" in prompt_lower or "copy to clipboard" in prompt_lower:
            op = "paste"
            text = None
            if "copy" in prompt_lower:
                op = "copy"
                quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
                if quotes:
                    text = quotes[0]
                else:
                    match = re.search(r'copy\s+["\'`]?(.+?)["\'`]?\s+to\s+clipboard', prompt, re.IGNORECASE)
                    if match:
                        text = match.group(1)
            return ToolPlan(
                tool_name="clipboard",
                args={"op": op, "text": text},
                reasoning=f"Identified clipboard operation '{op}'"
            )

        return None
