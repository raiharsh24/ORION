# Project State

## Current Status

- Version: v1.5.0-rc1
- Branch: semantic-phase1-backup-20260718
- Tests: 2213/2213 Passed
- Active Sprint: Phase 2
- Blockers: None

### Completed Milestones
- Semantic Phase 1
- Autonomous Development System
- FRIDAY AI Continuity System (FACS)

### Next Objectives
1. Voice Output (TTS)
2. Semantic Memory Integration
3. Tool Registry Population
4. Production Security Layer
5. FRIDAY v1.6.0

## Core Architecture
FRIDAY consists of:
1. **Express Gateway Proxy**: Acts as a reverse proxy on port `5000` mapping incoming requests and upgrading WebSockets.
2. **FastAPI Core Backend**: Runs on port `8000`, containing the Unified Cognitive Core, MCP Runtime, Action Engine, and Memory/Learning Engine.
3. **Desktop Interface Client**: Vite/React Electron application running on port `5173`.
4. **FACS Subsystem**: The AI continuity and state tracking system.

## Startup Commands
- Start Gateway: `npm run dev --workspace=gateway`
- Start Backend API: `cd services/friday-api && .venv/bin/python3 run.py`
- Start Desktop UI: `npm run dev --workspace=desktop`
- Concurrently start all via root: `npm run dev`
