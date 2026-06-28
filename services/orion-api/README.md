# ORION Backend API (v1.2)

The backend service acts as the decoupled "brain" for the ORION AI Operating System, incorporating the official Google Gemini SDK, prompt construction tools, customizable model config templates, memory log systems, and a semantic project knowledge search engine.

## Directory Structure

```
services/orion-api/
├── app/
│   ├── api/          # Route handlers (health, ask, chat, sessions, knowledge)
│   ├── core/         # Logger formatters, env configurations, dependencies singletons
│   ├── llm/          # BaseLLM adapters & LLMRouter decouplers
│   ├── models/       # Pydantic schemas (AskResponse, ChatRequest, KnowledgeIndex)
│   ├── memory/       # Conversational memory context stores & embeddings managers
│   ├── orion/        # Intent enums, orchestrator pipelines, prompt templates, vector databases, workspace manager, document chunkers
│   ├── main.py       # App factory & lifecycle hook triggers
│   └── __init__.py
├── tests/            # Automated test suites (test_action_engine.py, test_knowledge_engine.py)
├── .env              # Environment configurations (loaded in app)
├── requirements.txt  # Project package list
├── run.py            # Main server runner script
└── README.md
```

## Environment Configuration

Configure variables in `.env` or set system env flags:

```env
# Application Parameters
APP_NAME="ORION API"
APP_VERSION="1.2"
DEBUG=true

# AI Provider Keys
GEMINI_API_KEY="AQ.Ab8RN6KmygMdQIrb60V6soJe5SchgwtMBUxBufQOro2imYdyrQ"
OPENAI_API_KEY=""

# Generative Config Parameters
MODEL_NAME="gemini-1.5-flash"
TEMPERATURE=0.7
MAX_TOKENS=2048
TOP_P=0.95
```

## Running the Server

Initialize python virtual environment and install packages:

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (Optional) Install PDF & Vector DB dependencies
pip install pypdf chromadb

# Start Server
python run.py
```

The server will start by default at `http://localhost:8000`.

- **Swagger API Docs**: `http://localhost:8000/docs`
- **Health Check Status**: `http://localhost:8000/health`

## Core API Endpoints

### GET `/health`
Check core system health parameters.

### POST `/ask`
Submit prompts to ORION. Handles confirmation verification loops for destructive tasks.

### POST `/chat`
Exposes dynamic conversational links. Supports normal JSON responses or SSE streaming content.

### GET `/sessions` / GET `/sessions/{id}`
Retrieve session states, metadata contexts, and tool run history records.

### POST `/knowledge/index`
Triggers scanning, chunking, and embedding of files under a specific folder path.
- **Request Body**:
  ```json
  {
    "path": "/home/warlock/ORION/packages/utils",
    "project_name": "utils-library"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "indexed_chunks": 18,
    "message": "Successfully indexed workspace path '/home/warlock/ORION/packages/utils' (Project: utils-library). Generated 18 chunks."
  }
  ```

### POST `/knowledge/search`
Queries the vector database (ChromaDB / SimpleVectorDB fallback) semantic embeddings.
- **Request Body**:
  ```json
  {
    "query": "orchestrator tool confirmations",
    "n_results": 3
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "results": [
      {
        "id": "/home/warlock/ORION/services/orion-api/app/orion/orchestrator.py#chunk2",
        "document": "class OrionOrchestrator:\n    # ...",
        "metadata": {
          "file_path": "/home/warlock/ORION/services/orion-api/app/orion/orchestrator.py",
          "project_name": "orion-api",
          "file_type": "py",
          "chunk_index": 2
        },
        "score": 0.895
      }
    ]
  }
  ```

### GET `/workspace/projects`
Recursively walks the workspace root and lists detected projects and Git branch info.

## Running Tests

Execute all tests using pytest (requires setting `PYTHONPATH`):

```bash
PYTHONPATH=. pytest tests/
```
