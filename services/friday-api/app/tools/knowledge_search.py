from typing import List
from app.tools.base import ToolParameter, ToolExample
from app.tools.base_tool import BaseTool
from app.friday.retrieval import RetrievalEngine

class KnowledgeSearchTool(BaseTool):
    """
    Query tool that triggers semantic lookups across local documents.
    """
    def __init__(self, retrieval_engine: RetrievalEngine) -> None:
        self.retrieval_engine = retrieval_engine

    @property
    def name(self) -> str:
        return "knowledge.search"

    @property
    def description(self) -> str:
        return "Search the project knowledge base and codebase for semantic information."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Semantic search query", required=True),
        ]

    @property
    def examples(self) -> List[ToolExample]:
        return [
            ToolExample(prompt="Search for authentication code", args={"query": "authentication middleware"}, description="Search the knowledge base for authentication-related code"),
            ToolExample(prompt="Find database models", args={"query": "database models"}, description="Search for database model definitions"),
        ]

    def requires_confirmation(self, **kwargs) -> bool:
        return False

    async def execute(self, **kwargs) -> str:
        query = kwargs.get("query")
        if not query:
            return "Error: Missing required parameter 'query'."

        results = await self.retrieval_engine.search(query, n_results=4)
        if not results:
            return "No matching documentation or codebase chunks found in knowledge base."

        output_parts = [f"Found {len(results)} relevant project knowledge chunks:\n"]
        for idx, item in enumerate(results):
            meta = item.get("metadata", {})
            file_path = meta.get("file_path", "unknown_path")
            proj = meta.get("project_name", "unknown_project")
            chunk_idx = meta.get("chunk_index", 0)
            score = item.get("score", 0.0)
            
            output_parts.append(
                f"[{idx+1}] File: {file_path} (Project: {proj}, Chunk: {chunk_idx}, Similarity: {score:.2f})\n"
                f"----------------------------------------\n"
                f"{item['document']}\n"
                f"----------------------------------------\n"
            )

        return "\n".join(output_parts)
