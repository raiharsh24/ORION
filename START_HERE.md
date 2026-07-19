# Welcome to FRIDAY - START HERE

Welcome, AI Developer! You are entering the workspace of the FRIDAY AI agent system. To preserve context, continuity, and architectural integrity across developer handoffs, this project uses the **FRIDAY AI Continuity System (FACS)**.

Please execute the following onboarding routine before writing any code:

---

## 1. Onboarding Checklist

1. **Read the AI Contract**: Read and understand the mandatory guidelines in [AI_CONTRACT.md](file:///home/warlock/Downloads/projects/ORION/docs/AI_CONTRACT.md).
2. **Review Current Project State**: Read [PROJECT_STATE.md](file:///home/warlock/Downloads/projects/ORION/docs/PROJECT_STATE.md) to inspect version, milestones, and active blockers.
3. **Initialize the Session**: Run the FACS startup check command to verify repository health and show objectives:
   ```bash
   python3 scripts/ai_session_manager.py start
   ```
4. **Inspect Current Sprint Goals**: Open [CURRENT_SPRINT.md](file:///home/warlock/Downloads/projects/ORION/docs/CURRENT_SPRINT.md) to locate the prioritized task queue.

---

## 2. Standard Service Operations

To run the local services concurrently, execute:
```bash
npm run dev
```

This starts:
- **Gateway Service**: `http://localhost:5000`
- **FastAPI Backend Core**: `http://localhost:8000`
- **Desktop UI**: `http://localhost:5173`

---

## 3. Offboarding Checklist

Before completing your session and logging off:
1. **Verify Health**: Run test suites using the health check utility:
   ```bash
   python3 scripts/ai_session_manager.py health
   ```
2. **Save Your Session State**: End your session by updating project documents and logging modifications:
   ```bash
   python3 scripts/ai_session_manager.py end --model "<ModelName>" --duration "<Duration>" --tasks "Completed Task A" "Completed Task B" --notes "<OptionalNotes>"
   ```
3. **Commit & Push**: Stage, commit, and push all modifications cleanly to Git.
