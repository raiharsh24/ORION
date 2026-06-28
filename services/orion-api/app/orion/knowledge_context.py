import time
from typing import Dict, Any, List

class CitationManager:
    """
    Exposes reference schemas for search references.
    """
    def create_citation(self, idx: int, item: Dict[str, Any]) -> Dict[str, Any]:
        metadata = item.get("metadata", {})
        return {
            "citation_id": f"[{idx + 1}]",
            "title": metadata.get("title", "Untitled Document"),
            "path": metadata.get("path", "unknown_path"),
            "chunk_id": item.get("id", f"chunk_{idx}"),
            "score": round(item.get("score", 0.0), 3),
            "timestamp": metadata.get("timestamp", time.time()),
            "source": metadata.get("source", "local")
        }

class ContextAssembler:
    """
    Compiles chunks and citations into standard Markdown/XML context prompts.
    """
    def __init__(self, citation_manager: CitationManager) -> None:
        self._citation_manager = citation_manager

    def assemble_context(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        context_blocks = []
        citations = []

        for idx, item in enumerate(items):
            citation = self._citation_manager.create_citation(idx, item)
            citations.append(citation)

            block = (
                f"<KnowledgeSource id=\"{citation['citation_id']}\" path=\"{citation['path']}\" score=\"{citation['score']}\">\n"
                f"{item.get('text', '')}\n"
                f"</KnowledgeSource>"
            )
            context_blocks.append(block)

        assembled_text = "\n\n".join(context_blocks)

        return {
            "context_text": assembled_text,
            "citations": citations,
            "chunks_count": len(items)
        }
