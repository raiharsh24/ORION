# 5. Data Flow Diagrams

## 5.1 End-to-end: user query → response (with Cognitive Core)

```mermaid
sequenceDiagram
    participant U as User
    participant GW as Gateway
    participant ORCH as FridayOrchestrator
    participant CC as CognitiveCore
    participant MEM as MemoryService
    participant RET as RetrievalService
    participant PLAN as UnifiedPlanner
    participant TOOLS as ToolRegistry/Exec
    participant CTX as ContextBuilder
    participant LLM as Gemini

    U->>GW: POST /ask "do X"
    GW->>ORCH: ask(prompt, session_id)
    ORCH->>CC: perceive(prompt, session_id)
    CC->>MEM: load SessionMemory + WorkingMemory
    CC->>RET: retrieve(query, working)  %% hybrid: keyword+vector+graph
    RET-->>CC: ranked context blocks
    CC->>PLAN: plan(query, intent, working)
    PLAN->>TOOLS: select + execute (if tool needed)
    TOOLS-->>PLAN: tool output (or clarification)
    PLAN-->>CC: UnifiedPlan + result
    CC->>CTX: build prompt(context blocks + plan + result)
    CTX->>LLM: generate(prompt)
    LLM-->>CC: response
    CC->>MEM: remember(event)  %% write LTM/episodic/graph + embed
    CC-->>ORCH: result
    ORCH-->>GW: AskResponse
    GW-->>U: response
```

## 5.2 Memory write lifecycle

```mermaid
flowchart TD
    E[Event: ConversationCompleted / ToolCompleted / MissionCompleted] --> MM[MemoryManager]
    MM --> CLASS{Classify type}
    CLASS -->|fact/pref| LTM[LongTerm: user:/project:]
    CLASS -->|mission/tool| EPI[EpisodicMemory]
    CLASS -->|entity/rel| KG[CognitiveGraph]
    LTM --> EMB[EmbeddingProvider.embed]
    EPI --> EMB
    KG --> EMB
    EMB --> CHROMA[(Chroma friday_memory)]
    LTM --> SQL[(friday_memory.db)]
    EPI --> SQL
    KG --> ATLAS[(atlas_graph.db)]
    CONS[MemoryConsolidator 3600s] -->|summarize/extract| LTM
    FORGET[ForgettingPolicy] -->|decay| ARCH[(archive table)]
```

## 5.3 Tool execution + recovery

```mermaid
flowchart TD
    P[UnifiedPlanner.execute] --> SEL[ToolSelectionEngine.select] --> REG[UniversalToolRegistry]
    SEL --> SCHED[ExecutionScheduler.order_tools]
    SCHED --> EXEC[ToolExecutionEngine._execute_single]
    EXEC --> VAL[Schema validate args]
    VAL --> SANDBOX[SandboxService + ConfirmationService]
    SANDBOX --> RUN[BaseTool.execute]
    RUN -->|success| HIST[ExecutionHistory + Health update]
    RUN -->|failure| REC{RecoveryPolicies}
    REC -->|retry| EXEC
    REC -->|alt tool| SEL
    REC -->|abort/ask| FAIL[return clarification/error]
    HIST --> LEARN[LearningEngine + AdaptiveLearning]
```

## 5.4 Planner decomposition + monitoring

```mermaid
flowchart LR
    Q[Objective] --> DEC[GoalPlanner.decompose]
    DEC --> SG[Sub-goals / Actions]
    SG --> SIM[PlanningEngine.simulate]
    SIM --> CONF[ConfidenceEngine.evaluate]
    CONF -->|proceed| EXEC[MissionExecutor / ToolExecutionEngine]
    CONF -->|hold| CLAR[ClarificationManager]
    EXEC --> MON[ExecutionMonitor]
    MON --> RECOVER[Supervisor + RecoveryPolicies]
    RECOVER --> EXEC
    EXEC --> REFLECT[ReflectionV2.analyze]
    REFLECT --> LEARN[AdaptiveLearning]
    LEARN --> CONF
```

## 5.5 Context assembly (reused IntelligencePipeline)

```mermaid
flowchart TD
    Q[user_query] --> IA[IntentAnalyzer]
    IA --> STR[StrategyManager.get_strategy]
    STR --> EXT[ExtractorRegistry.extract_for_strategy]
    EXT --> RANK[ContextRanker.rank]
    RANK --> BUD[AdaptiveTokenBudgetAllocator.allocate]
    BUD --> VAL2[ContextValidator.validate]
    VAL2 --> COMP[ContextCompressor.compress]
    COMP --> ASM[PromptAssembler.assemble]
    ASM --> LLM[Gemini]
```

(Note: `IntelligencePipeline` already implements this 8-stage flow in `intelligence/pipeline.py`; it is wired into `CognitiveCore` as the `ContextService` and fed retrieval results from §5.1.)
