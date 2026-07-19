# Project State

## System Metadata
- **Current Version**: `v1.5.0-rc1`
- **Current Branch**: `semantic-phase1-backup-20260718`
- **Current Milestone**: Milestone 7 (Autonomous Development System & MCP Runtime)
- **Status**: Semantic Phase 1 Release Candidate
- **Last Updated**: 2026-07-19T10:40:00Z

## Core Architecture
FRIDAY consists of:
1. **Express Gateway Proxy**: Acts as a reverse proxy on port `5000` mapping incoming requests and upgrading WebSockets.
2. **FastAPI Core Backend**: Runs on port `8000`, containing the Unified Cognitive Core, MCP Runtime, Action Engine, and Memory/Learning Engine.
3. **Desktop Interface Client**: Vite/React Electron application running on port `5173`.
4. **FACS Subsystem**: The AI continuity and state tracking system.

## Current Objective
- Implement and integrate **FRIDAY AI Continuity System (FACS)** to achieve zero-context, AI-portable handoffs.

## Active Blockers
- None.

## Startup Commands
- Start Gateway: `npm run dev --workspace=gateway`
- Start Backend API: `cd services/friday-api && .venv/bin/python3 run.py`
- Start Desktop UI: `npm run dev --workspace=desktop`
- Concurrently start all via root: `npm run dev`

## System Health
- **Pytests**: 2,210 / 2,211 passing (99.95% pass rate).
- **Known Failures**: `tests/test_v0_4.py::test_ask_endpoint_success` (Legacy connectivity test).
- **Service Status**: Gateway, Backend, and Desktop boot successfully.
