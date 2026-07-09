import time
import math
import hashlib
from typing import List, Set, Optional, Dict, Any, TYPE_CHECKING
from app.memory.schema import MemoryEntry, UserMemory, ProjectMemory, SessionMemory

if TYPE_CHECKING:
    from app.memory.semantic import SemanticMemoryStore


def _compute_mock_embedding(text: str, dimension: int = 768) -> List[float]:
    """Deterministic 768-dim vector based on word hashes (sync, no external deps)."""
    vector = [0.0] * dimension
    words = text.lower().split()
    if not words:
        vector[0] = 1.0
        return vector
    for word in words:
        h = hashlib.md5(word.encode("utf-8")).hexdigest()
        for i in range(4):
            chunk = h[i * 8:(i + 1) * 8]
            val = int(chunk, 16)
            idx = val % dimension
            vector[idx] += (val / 0xFFFFFFFF) + 0.1
    norm = sum(x * x for x in vector) ** 0.5
    if norm:
        vector = [x / norm for x in vector]
    else:
        vector[0] = 1.0
    return vector


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryRetriever:
    """
    Retrieves and ranks memories deterministically from multiple memory layers
    using recency (exponential time decay), importance score, keyword overlap,
    mission/project/preference affinity, and optional semantic similarity.

    When a SemanticMemoryStore is connected and `semantic_scores` are passed
    to `retrieve()`, performs hybrid retrieval: keyword/recency scoring fused
    with semantic vector similarity.
    """
    def __init__(
        self,
        decay_rate: float = 0.00001,
        weights: Optional[Dict[str, float]] = None,
        semantic_store: Optional['SemanticMemoryStore'] = None,
        semantic_weight: float = 0.30,
    ) -> None:
        self.decay_rate = decay_rate
        self._semantic_store = semantic_store
        self.semantic_weight = semantic_weight
        # Default weights for ranking score components
        self.weights = weights or {
            "recency": 0.25,
            "importance": 0.25,
            "keyword": 0.25,
            "mission_affinity": 0.10,
            "project_affinity": 0.10,
            "preference_affinity": 0.05,
        }

    def _tokenize(self, text: str) -> Set[str]:
        """Simple clean tokenization of lowercase alphanumeric words."""
        import re
        words = re.findall(r'\b\w+\b', text.lower())
        return set(words)

    def calculate_score(
        self,
        entry: MemoryEntry,
        query_tokens: Set[str],
        now: float,
        affinity_context: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculates a priority score between 0.0 and 1.0 for a MemoryEntry.
        Supports optional affinity context for mission/project/preference scoring.
        """
        # 1. Recency Score (Exponential Decay)
        age = max(0.0, now - entry.timestamp)
        recency_score = math.exp(-self.decay_rate * age)

        # 2. Importance Score
        importance_score = entry.importance / 10.0

        # 3. Keyword Overlap Score
        content_tokens = self._tokenize(entry.content)
        if query_tokens and content_tokens:
            overlap = query_tokens.intersection(content_tokens)
            keyword_score = len(overlap) / len(query_tokens)
        else:
            keyword_score = 0.0

        # 4. Mission/Project/Preference Affinity Scoring
        mission_score = 0.0
        project_score = 0.0
        preference_score = 0.0

        if affinity_context:
            meta = entry.metadata or {}

            if "mission_id" in affinity_context:
                entry_mission = meta.get("mission_id", "")
                if entry_mission == affinity_context["mission_id"]:
                    mission_score = 1.0
                elif entry_mission and affinity_context.get("mission_id"):
                    mission_score = 0.3

            if "project_id" in affinity_context:
                entry_project = meta.get("project_id", "")
                if entry_project == affinity_context["project_id"]:
                    project_score = 1.0
                elif entry_project and affinity_context.get("project_id"):
                    project_score = 0.3

            if "user_id" in affinity_context:
                entry_user = meta.get("user_id", "")
                if entry_user and entry_user == affinity_context["user_id"]:
                    preference_score = 0.8
                elif entry.category == "preference":
                    preference_score = 0.5

        # Weighted combination
        score = (
            self.weights["recency"] * recency_score +
            self.weights["importance"] * importance_score +
            self.weights["keyword"] * keyword_score +
            self.weights.get("mission_affinity", 0.0) * mission_score +
            self.weights.get("project_affinity", 0.0) * project_score +
            self.weights.get("preference_affinity", 0.0) * preference_score
        )
        return round(score, 4)

    def compute_semantic_scores(
        self,
        query: str,
        candidates: List[MemoryEntry],
        dimension: int = 768,
    ) -> Dict[str, float]:
        """
        Compute semantic similarity scores for all candidates using
        deterministic mock embeddings (sync, no API calls).

        Returns dict of memory_id -> cosine_similarity (0..1).
        """
        if not candidates:
            return {}
        query_vec = _compute_mock_embedding(query, dimension)
        scores: Dict[str, float] = {}
        for entry in candidates:
            entry_vec = _compute_mock_embedding(entry.content, dimension)
            sim = _cosine_similarity(query_vec, entry_vec)
            scores[entry.id] = round(sim, 4)
        return scores

    def retrieve(
        self,
        query: str,
        user_memory: Optional[UserMemory] = None,
        project_memory: Optional[ProjectMemory] = None,
        session_memory: Optional[SessionMemory] = None,
        limit: int = 5,
        affinity_context: Optional[Dict[str, Any]] = None,
        semantic_scores: Optional[Dict[str, float]] = None,
    ) -> List[MemoryEntry]:
        """
        Gathers entries from user, project, and session stores, scores them
        deterministically, and returns the top ranked results.

        When `semantic_scores` dict is provided (memory_id -> score), performs
        hybrid fusion: keyword/recency score * (1 - semantic_weight) + semantic * semantic_weight.

        If `semantic_scores` is None but a `_semantic_store` is configured,
        computes semantic scores internally on the same candidate objects used
        for keyword scoring, ensuring score alignment.

        Optional affinity_context includes mission_id, project_id, user_id
        for mission/project/preference affinity scoring.
        """
        now = time.time()
        query_tokens = self._tokenize(query)
        candidates: List[MemoryEntry] = []

        # 1. Normalize User Memory preferences into MemoryEntry objects
        if user_memory:
            for key, val in user_memory.preferences.items():
                content = f"User preferred {key}: {val}"
                candidates.append(
                    MemoryEntry(
                        id=str(hash(f"pref:{user_memory.user_id}:{key}")),
                        content=content,
                        category="preference",
                        importance=8,
                        timestamp=user_memory.updated_at,
                        metadata={
                            "user_id": user_memory.user_id,
                            "preference_key": key,
                        }
                    )
                )

        # 2. Normalize Project Memory decisions, todos, milestones into MemoryEntry objects
        if project_memory:
            # Decisions
            for i, dec in enumerate(project_memory.decisions):
                candidates.append(
                    MemoryEntry(
                        id=str(hash(f"dec:{project_memory.project_id}:{i}:{dec.get('content', '')}")),
                        content=f"Project decision: {dec.get('content', '')}",
                        category="decision",
                        importance=dec.get("importance", 7),
                        timestamp=dec.get("timestamp", project_memory.updated_at),
                        metadata={"project_id": project_memory.project_id}
                    )
                )
            # Todos
            for i, todo in enumerate(project_memory.todos):
                candidates.append(
                    MemoryEntry(
                        id=str(hash(f"todo:{project_memory.project_id}:{i}:{todo.get('content', '')}")),
                        content=f"Project TODO: {todo.get('content', '')} (Status: {todo.get('status', 'pending')})",
                        category="todo",
                        importance=todo.get("importance", 5),
                        timestamp=todo.get("timestamp", project_memory.updated_at),
                        metadata={"project_id": project_memory.project_id}
                    )
                )
            # Milestones
            for m_name, m_status in project_memory.milestones.items():
                candidates.append(
                    MemoryEntry(
                        id=str(hash(f"ms:{project_memory.project_id}:{m_name}")),
                        content=f"Project milestone '{m_name}' status: {m_status}",
                        category="milestone",
                        importance=6,
                        timestamp=project_memory.updated_at,
                        metadata={"project_id": project_memory.project_id}
                    )
                )

        # 3. Normalize Session Memory history
        if session_memory:
            for i, msg in enumerate(session_memory.messages):
                candidates.append(
                    MemoryEntry(
                        id=str(hash(f"chat:{session_memory.session_id}:{i}:{msg.content}")),
                        content=f"{msg.role}: {msg.content}",
                        category="chat",
                        importance=5,
                        timestamp=msg.timestamp,
                        metadata={"session_id": session_memory.session_id}
                    )
                )

        # Filter out expired candidates
        valid_candidates = [
            c for c in candidates
            if c.expiration is None or c.expiration > now
        ]

        # Score and Sort with affinity context
        scored_entries = [
            (self.calculate_score(entry, query_tokens, now, affinity_context), entry)
            for entry in valid_candidates
        ]

        # Compute semantic scores on the same candidate objects if no pre-computed dict
        if semantic_scores is None and self._semantic_store is not None:
            try:
                semantic_scores = self.compute_semantic_scores(query, valid_candidates)
            except Exception:
                semantic_scores = {}

        # Fuse with semantic scores if provided
        if semantic_scores:
            fused = []
            for kw_score, entry in scored_entries:
                sem_score = semantic_scores.get(entry.id, 0.0)
                fused_score = kw_score * (1.0 - self.semantic_weight) + sem_score * self.semantic_weight
                fused.append((fused_score, entry))
            scored_entries = fused

        # Sort descending by score, stable fallback on newer timestamp
        scored_entries.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)

        return [entry for _, entry in scored_entries[:limit]]
