# AI Contract

This contract defines the mandatory actions, operational rules, and workflows that every AI developer session entering the repository must follow. Adherence to this contract ensures full handoff continuity and branch preservation.

---

## Operational Rules

### 1. Zero Architectural Disruption
Do not restructure major subsystems or refactor core components of the codebase unless specifically requested in the sprint objective. Keep edits surgical and additive.

### 2. Single Source of Truth
`PROJECT_STATE.md` is the canonical source of truth for repository health and objective state. Always check it first and keep it updated.

---

## Session Workflow

### BEFORE STARTING:
Any AI session entering the codebase MUST sequentially:
1. **Read project state**: Open and read `/docs/PROJECT_STATE.md`.
2. **Read handoff notes**: Open and read `/docs/AI_HANDOFF.md`.
3. **Understand goals**: Read `/docs/CURRENT_SPRINT.md` and `/docs/NEXT_TASKS.md`.
4. **Inspect known issues**: Review `/docs/KNOWN_ISSUES.md`.
5. **Run Startup / Verification Manager**:
   ```bash
   python3 scripts/ai_session_manager.py start
   ```
6. **Verify branch & health**: Ensure you are operating on the correct branch and run the pytest validation suite.

---

### AFTER COMPLETING:
Before finishing the session, the AI MUST:
1. **Run Verification Manager**:
   ```bash
   python3 scripts/ai_session_manager.py end
   ```
2. **Update project state**: Ensure `PROJECT_STATE.md` contains the correct health metrics and last updated timestamp.
3. **Log handoff notes**: Append a record of your session to `AI_HANDOFF.md`, detailing tasks completed, files modified, and recommendations for the next developer.
4. **Update sprint progress**: Update checkboxes in `CURRENT_SPRINT.md` and `NEXT_TASKS.md`.
5. **Record changelog**: Document changes chronologically in `CHANGELOG.md`.
6. **Commit & Push**: Stage and commit all changes cleanly to Git.
