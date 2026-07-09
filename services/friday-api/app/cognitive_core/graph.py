import time
from typing import Optional, Dict, Any, List
from loguru import logger

from app.memory.graph import KnowledgeGraph
from app.friday.atlas_store import AtlasStore


class CognitiveGraph:
    def __init__(
        self,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        atlas_store: Optional[AtlasStore] = None,
    ) -> None:
        self._kg = knowledge_graph or KnowledgeGraph()
        self._atlas = atlas_store or AtlasStore()

    def query(
        self,
        query_text: str,
        entity_type: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        kg_result = self._kg.query(
            entity_type=entity_type,
            name_contains=query_text,
            limit=limit,
        )

        atlas_result: Dict[str, Any] = {"nodes": [], "links": []}
        try:
            snapshot_id = self._atlas.get_active_snapshot_id()
            if snapshot_id:
                atlas_result = self._atlas.get_graph_data(snapshot_id)
                if query_text:
                    atlas_result["nodes"] = [
                        n for n in atlas_result.get("nodes", [])
                        if query_text.lower() in n.get("title", "").lower()
                        or query_text.lower() in n.get("description", "").lower()
                    ][:limit]
        except Exception as e:
            logger.debug(f"CognitiveGraph atlas query skipped: {e}")

        return self._merge(kg_result, atlas_result, limit)

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        entity = self._kg.get_entity(entity_id)
        if entity:
            return {
                "id": entity.id,
                "type": entity.type,
                "name": entity.name,
                "properties": entity.properties,
                "source": "knowledge_graph",
            }
        return None

    def get_relations(self, entity_id: str) -> List[Dict[str, Any]]:
        return [
            {"source": r.source_id, "target": r.target_id, "type": r.type}
            for r in self._kg.get_relations(entity_id)
        ]

    def add_entity(
        self,
        type_: str,
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        entity = self._kg.add_entity(type_=type_, name=name, properties=properties)
        return entity.id

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        type_: str = "related_to",
    ) -> None:
        self._kg.add_relation(source_id=source_id, target_id=target_id, type_=type_)

    def graph_context(self, query: str, max_entities: int = 5) -> str:
        result = self.query(query, limit=max_entities)
        entities = result.get("entities", [])
        relations = result.get("relations", [])

        if not entities and not result.get("nodes"):
            return ""

        lines = ["[Knowledge Graph Context]:"]
        for e in entities[:max_entities]:
            lines.append(f"  - {e.get('type','?')}: {e.get('name','?')} ({e.get('id','?')[:8]}...)")

        code_nodes = result.get("nodes", [])
        for n in code_nodes[:max_entities]:
            lines.append(f"  - code:{n.get('type','?')}: {n.get('title','?')}")

        for r in relations[:max_entities]:
            lines.append(f"  - {r.get('source','?')[:8]}... --[{r.get('type','?')}]--> {r.get('target','?')[:8]}...")

        lines.append(f"[End Graph Context: {len(entities)+len(code_nodes)} entities, {len(relations)} relations]")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        kg_stats = self._kg.get_stats()
        atlas_health = {}
        try:
            atlas_health = self._atlas.get_health_stats()
        except Exception:
            pass
        return {
            "knowledge_graph": kg_stats,
            "atlas_store": atlas_health,
        }

    @staticmethod
    def _merge(
        kg_result: Dict[str, Any],
        atlas_result: Dict[str, Any],
        limit: int,
    ) -> Dict[str, Any]:
        seen_ids: set = set()
        entities = list(kg_result.get("entities", []))
        for e in entities:
            seen_ids.add(e.get("id", ""))

        for n in atlas_result.get("nodes", []):
            if n.get("id") not in seen_ids and len(entities) < limit:
                entities.append({
                    "id": n["id"],
                    "type": n.get("type", "code"),
                    "name": n.get("title", ""),
                    "source": "atlas",
                })
                seen_ids.add(n["id"])

        return {
            "entities": entities[:limit],
            "relations": kg_result.get("relations", []),
            "code_links": atlas_result.get("links", []),
            "count": len(entities[:limit]),
        }
