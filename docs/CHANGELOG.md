# Changelog

All notable changes to the FRIDAY AI project will be documented in this file.

---

## [1.5.0-rc1] - 2026-07-19

### Added
- Milestone 7 Autonomous Development System (`app/autonomous_dev`) recovered from branch history.
- REST endpoints and WebSocket events routing in FastAPI (`app/api/autonomous.py`).
- `/autonomous` and `/api/autonomous` path mapping in Gateway proxy (`proxyMiddleware.js`).
- Event-driven Goal and Task persistence inside `AutonomousDevelopmentManager`.
- Async unit tests for `AutonomousPlanner` utilizing `pytest.mark.anyio`.

### Fixed
- Fixed syntax compile blockers in `planner.py` (importing `Any` from `typing`).
- Fixed missing router imports in `autonomous.py`.
- Resolved `ValueError: AutonomousReflection requires a LearningEngine` by making the learning engine dependency optional, fixing 78 failing tests in mock environments.
- Corrected task result parsing in reflection engine by using `ast.literal_eval` to safely evaluate stringified dictionaries.

---

## [1.5.0-alpha] - 2026-07-18
- Initial Semantic Phase 1 release candidate branch backup.
- Unified Cognitive Core, MCP Runtimes, and Three.js desktop overlays.
