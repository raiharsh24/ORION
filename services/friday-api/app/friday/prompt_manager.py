from typing import List, Dict, Any, Optional
import time

class PromptManager:
    """
    Constructs system prompts combining context details, logs, tools, memory history, and semantic knowledge.
    """
    def format_prompt(
        self,
        system_instruction: str,
        user_message: str,
        history: str,
        available_tools: List[str],
        session_metadata: Dict[str, Any],
        retrieved_context: Optional[str] = None
    ) -> str:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        tools_list = ", ".join(available_tools) if available_tools else "None"
        meta_str = ", ".join([f"{k}: {v}" for k, v in session_metadata.items()])
        
        prompt = (
            f"System Instruction: {system_instruction}\n"
            f"Current Time: {current_time}\n"
            f"Available Tools: [{tools_list}]\n"
            f"Session Metadata: {{{meta_str}}}\n\n"
        )
        
        if retrieved_context:
            prompt += (
                f"=== RETRIEVED PROJECT KNOWLEDGE CONTEXT ===\n"
                f"{retrieved_context}\n"
                f"===========================================\n\n"
            )

        prompt += (
            f"Conversation History:\n{history}\n\n"
            f"User Prompt: {user_message}"
        )
        return prompt
