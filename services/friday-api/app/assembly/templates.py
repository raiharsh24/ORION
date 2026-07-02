from typing import Dict, List, Optional

from app.assembly.base import (
    PromptFormat,
    PromptSection,
    PromptFrame,
    PROVIDER_FORMATS,
    GEMINI_FORMAT,
    OPENAI_FORMAT,
    ANTHROPIC_FORMAT,
    LOCAL_FORMAT,
)


def build_frame(sections: List[PromptSection], provider: str = "gemini") -> PromptFrame:
    fmt = PROVIDER_FORMATS.get(provider, GEMINI_FORMAT)

    if fmt.use_xml_wrappers:
        return _build_xml_frame(sections, fmt)
    elif fmt.use_json_messages:
        return _build_messages_frame(sections, fmt)
    else:
        return _build_text_frame(sections, fmt)


def _build_messages_frame(sections: List[PromptSection], fmt: PromptFormat) -> PromptFrame:
    system_parts: List[str] = []
    messages: List[Dict[str, str]] = []
    user_content: List[str] = []
    current_role = ""

    for section in sections:
        if section.is_omitted or not section.content.strip():
            continue

        if section.name == "system_prompt":
            system_parts.append(section.content)
            continue

        if section.name == "user_query":
            user_content.append(section.content)
            continue

    if fmt.provider == "anthropic":
        for section in sections:
            if section.is_omitted or section.name in ("system_prompt", "user_query"):
                continue
            if not section.content.strip():
                continue

            if current_role != "user":
                messages.append({"role": "user", "content": ""})
                current_role = "user"

            if messages and messages[-1]["role"] == "user":
                content = messages[-1]["content"]
                header = f"[{section.name}]\n" if content else ""
                messages[-1]["content"] = content + header + section.content

        if user_content:
            messages.append({"role": "user", "content": "\n".join(user_content)})

        system_instruction = "\n\n".join(system_parts)

        return PromptFrame(
            system_instruction=system_instruction,
            messages=messages,
            sections=sections,
        )

    if fmt.provider == "gemini":
        for section in sections:
            if section.is_omitted or section.name in ("system_prompt", "user_query"):
                continue
            if not section.content.strip():
                continue

            if current_role != "user":
                messages.append({"role": "user", "parts": [{"text": ""}]})
                current_role = "user"

            if messages and messages[-1]["role"] == "user":
                parts = messages[-1]["parts"]
                header = f"[{section.name}]\n" if parts[0]["text"] else ""
                parts[0]["text"] = parts[0]["text"] + header + section.content

        if user_content:
            messages.append({"role": "user", "parts": [{"text": "\n".join(user_content)}]})

        system_instruction = "\n\n".join(system_parts)

        return PromptFrame(
            system_instruction=system_instruction,
            messages=messages,
            sections=sections,
        )

    for section in sections:
        if section.is_omitted or section.name == "system_prompt":
            continue
        if not section.content.strip():
            continue

        role = fmt.role_user
        if current_role != role:
            messages.append({"role": role, "content": ""})
            current_role = role

        if messages and messages[-1]["role"] == role:
            content = messages[-1]["content"]
            header = f"[{section.name}]\n" if content else ""
            messages[-1]["content"] = content + header + section.content

    if user_content:
        messages.append({"role": fmt.role_user, "content": "\n".join(user_content)})

    system_instruction = "\n\n".join(system_parts)

    if fmt.provider == "openai" and system_instruction:
        messages.insert(0, {"role": "system", "content": system_instruction})
        system_instruction = ""

    return PromptFrame(
        system_instruction=system_instruction,
        messages=messages,
        sections=sections,
    )


def _build_text_frame(sections: List[PromptSection], fmt: PromptFormat) -> PromptFrame:
    parts: List[str] = []

    for section in sections:
        if section.is_omitted or not section.content.strip():
            continue

        if section.name == "system_prompt":
            parts.append(f"### System\n{section.content}")
        elif section.name == "user_query":
            parts.append(f"### User\n{section.content}")
        else:
            label = section.name.replace("_", " ").title()
            parts.append(f"### {label}\n{section.content}")

    text_prompt = fmt.section_separator.join(parts)

    return PromptFrame(
        text_prompt=text_prompt,
        sections=sections,
    )


def _build_xml_frame(sections: List[PromptSection], fmt: PromptFormat) -> PromptFrame:
    parts: List[str] = []

    for section in sections:
        if section.is_omitted or not section.content.strip():
            continue

        tag = section.name
        parts.append(f"<{tag}>\n{section.content}\n</{tag}>")

    text_prompt = fmt.section_separator.join(parts)

    return PromptFrame(
        text_prompt=text_prompt,
        sections=sections,
    )
