import time
import json
import uuid
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from loguru import logger

from app.memory.store import MemoryStore, InMemoryStore


@dataclass
class Entity:
    id: str = ""
    type: str = "unknown"
    name: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class Relation:
    source_id: str
    target_id: str
    type: str = "related_to"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class KnowledgeGraph:
    """Entity-relationship knowledge graph stored in MemoryStore.

    Extends the existing Knowledge Engine infrastructure with structured
    entity-relationship queries. Entity types: person, project, file, goal,
    mission. Relation types: depends_on, contains, created_by, related_to.
    """

    VALID_ENTITY_TYPES = {"person", "project", "file", "goal", "mission", "concept", "tool"}
    VALID_RELATION_TYPES = {"depends_on", "contains", "created_by", "related_to", "implements", "depends"}

    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self._store = store or InMemoryStore()

    def _entity_key(self, entity_id: str) -> str:
        return f"graph:entity:{entity_id}"

    def _relation_key(self, source_id: str, target_id: str, rel_type: str) -> str:
        return f"graph:relation:{source_id}:{target_id}:{rel_type}"

    def _type_index_key(self, type_: str) -> str:
        return f"graph:idx:type:{type_}"

    def _relation_idx_key(self, entity_id: str) -> str:
        return f"graph:idx:relations:{entity_id}"

    def add_entity(
        self,
        type_: str,
        name: str,
        entity_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        if type_ not in self.VALID_ENTITY_TYPES:
            logger.warning(f"Unknown entity type '{type_}', storing anyway")
        entity = Entity(
            id=entity_id or str(uuid.uuid4()),
            type=type_,
            name=name,
            properties=properties or {},
        )
        self._store.put(self._entity_key(entity.id), self._serialize(entity))

        type_ids: Set[str] = set(self._store.get(self._type_index_key(type_)) or [])
        type_ids.add(entity.id)
        self._store.put(self._type_index_key(type_), list(type_ids))
        return entity

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        type_: str = "related_to",
        properties: Optional[Dict[str, Any]] = None,
    ) -> Relation:
        if type_ not in self.VALID_RELATION_TYPES:
            logger.warning(f"Unknown relation type '{type_}', storing anyway")
        relation = Relation(
            source_id=source_id,
            target_id=target_id,
            type=type_,
            properties=properties or {},
        )
        key = self._relation_key(source_id, target_id, type_)
        self._store.put(key, asdict(relation))

        for eid in (source_id, target_id):
            rels: Set[str] = set(self._store.get(self._relation_idx_key(eid)) or [])
            rels.add(key)
            self._store.put(self._relation_idx_key(eid), list(rels))
        return relation

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        data = self._store.get(self._entity_key(entity_id))
        return self._deserialize_entity(data) if data else None

    def get_entities_by_type(self, type_: str) -> List[Entity]:
        ids = self._store.get(self._type_index_key(type_)) or []
        entities: List[Entity] = []
        for eid in ids:
            ent = self.get_entity(eid)
            if ent:
                entities.append(ent)
        return entities

    def get_relations(
        self,
        entity_id: str,
        relation_type: Optional[str] = None,
    ) -> List[Relation]:
        rel_keys = self._store.get(self._relation_idx_key(entity_id)) or []
        relations: List[Relation] = []
        for key in rel_keys:
            data = self._store.get(key)
            if data:
                rel = Relation(**data)
                if relation_type is None or rel.type == relation_type:
                    relations.append(rel)
        return relations

    def query(
        self,
        entity_type: Optional[str] = None,
        relation_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        name_contains: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        entities: List[Entity] = []
        if entity_id:
            ent = self.get_entity(entity_id)
            if ent:
                entities = [ent]
        elif entity_type:
            entities = self.get_entities_by_type(entity_type)
        else:
            all_ids: Set[str] = set()
            for key in self._store.keys():
                if key.startswith("graph:entity:"):
                    all_ids.add(key.split(":", 2)[2])
            for eid in list(all_ids)[:limit]:
                ent = self.get_entity(eid)
                if ent:
                    entities.append(ent)

        if name_contains:
            entities = [e for e in entities if name_contains.lower() in e.name.lower()]

        entities = entities[:limit]

        result_relations: List[Relation] = []
        for ent in entities:
            rels = self.get_relations(ent.id, relation_type)
            result_relations.extend(rels)

        return {
            "entities": [asdict(e) for e in entities],
            "relations": [asdict(r) for r in result_relations],
            "count": len(entities),
        }

    def delete_entity(self, entity_id: str) -> bool:
        ent = self.get_entity(entity_id)
        if not ent:
            return False

        type_ids: Set[str] = set(self._store.get(self._type_index_key(ent.type)) or [])
        type_ids.discard(entity_id)
        if type_ids:
            self._store.put(self._type_index_key(ent.type), list(type_ids))
        else:
            self._store.delete(self._type_index_key(ent.type))

        rel_keys = self._store.get(self._relation_idx_key(entity_id)) or []
        for rk in rel_keys:
            self._store.delete(rk)

        self._store.delete(self._relation_idx_key(entity_id))
        self._store.delete(self._entity_key(entity_id))
        return True

    def get_stats(self) -> Dict[str, Any]:
        entity_count = 0
        type_counts: Dict[str, int] = {}
        relation_count = 0

        for key in self._store.keys():
            if key.startswith("graph:entity:"):
                entity_count += 1
                ent = self.get_entity(key.split(":", 2)[2])
                if ent:
                    type_counts[ent.type] = type_counts.get(ent.type, 0) + 1
            elif key.startswith("graph:relation:"):
                relation_count += 1

        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "type_counts": type_counts,
        }

    @staticmethod
    def _serialize(entity: Entity) -> Dict[str, Any]:
        return asdict(entity)

    @staticmethod
    def _deserialize_entity(data: Dict[str, Any]) -> Optional[Entity]:
        try:
            return Entity(**data)
        except Exception:
            return None
