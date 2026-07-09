from app.plugin_sdk.base_plugin import BasePlugin


class KnowledgeSearchPlugin(BasePlugin):
    id = "knowledge_search"
    name = "Knowledge Search"
    version = "1.0.0"

    async def on_load(self) -> None:
        self.log_info("Knowledge Search loaded")

    def get_manifest(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
        }

    def get_requested_permissions(self):
        return ["memory.read"]

    async def search(self, query: str, limit: int = 5) -> list:
        if not self.context:
            return []
        results = await self.context.query_memory(query, limit=limit)
        self.log_info(f"Knowledge search '{query}' returned {len(results)} results")
        return results

    async def search_cognitive(self, query: str, top_k: int = 3) -> dict:
        if not self.context:
            return {}
        ctx = await self.context.retrieve_context(query, top_k=top_k)
        self.log_info(f"Cognitive search '{query}' returned context")
        return ctx
