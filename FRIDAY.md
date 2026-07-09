# FRIDAY AI Operating System Manifest

Welcome to the live workspace coordinates control for **FRIDAY**. This file serves as the root index anchor for the ATLAS Knowledge Graph Visualizer.

---

## Workspace Subsystems

*   **[Desktop Client](file:///home/warlock/ORION/apps/desktop)**: React 19 + TypeScript + Zustand desktop UI client. Exposes interactive control maps, health widgets, voice logs, and knowledge canvases.
*   **[API Server](file:///home/warlock/ORION/services/friday-api)**: FastAPI backend routing prompt streams, tool databases, Chroma vector storage, and episodic memory engines.
*   **[Gateway Proxy](file:///home/warlock/ORION/services/gateway)**: Express proxy orchestrating path communications between the UI and backend sockets.

---

## Active Agent Layers

*   **Episodic Memory**: Tracks session variables, logs, and facts in SQLite KV stores.
*   **Workflow Automations**: Deploys multi-step sequential tasks and execution loops.
*   **Desktop Integrations**: Captures screenshots, notifications, clipboard streams, and terminal execution hooks.
