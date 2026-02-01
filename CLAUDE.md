# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (Python)
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Start Qdrant (required for memory/knowledge)
docker-compose up -d qdrant
```

### Frontend (React/TypeScript)
```bash
cd web
npm install
npm run dev      # Development server
npm run build    # Production build
```

### Full Stack with Docker
```bash
docker-compose up -d          # Start all services
docker-compose up -d qdrant   # Start only Qdrant
```

## Architecture Overview

This is a personal AI assistant with a web interface, originally designed for Telegram but now primarily web-based. It integrates with Microsoft 365 and Harvest for data access.

### Core Components

**Agent System** (`src/agents/`):
- `BaseAgent` - Abstract base class providing lifecycle management, inter-agent communication via MessageBus, recommendation creation, and access to knowledge/memory layers
- Specialized agents: `ChatAgent`, `BriefingAgent`, `ActionItemAgent`, `MemoryAgent`, `AnomalyAgent`
- Agents run on cron schedules via `AgentScheduler` using APScheduler
- Agent communication happens through `MessageBus` with publish/subscribe pattern

**Two-Tier Knowledge System**:
- **Fixed Knowledge** (`src/knowledge/`) - Curated facts stored in Qdrant with category tags (strategy, team, processes, clients, projects). Managed by `KnowledgeManager`.
- **Dynamic Memory** (`src/memory/`) - Conversation-derived facts via Mem0 + Qdrant. `MemoryClient` handles long-term storage, `ConversationHistory` handles short-term context in SQLite.

**Legacy Orchestrator** (`src/agent/orchestrator.py`):
- `AgentOrchestrator` - Original message processing with agentic tool loop (max 5 rounds)
- Still used by web API for chat threads
- Coordinates LLM calls, memory search, tool execution

**LLM Integration** (`src/llm/azure_openai.py`):
- Uses Azure OpenAI (GPT-4) for chat completions
- Supports tool/function calling with responses API
- Embedding generation for vector search

**External Integrations**:
- Microsoft Graph API (`src/microsoft/`) - Calendar, email, Teams, OneDrive, meeting transcripts
- Harvest API (`src/harvest/`) - Time tracking data
- OAuth tokens stored in SQLite (`tokens.db`)

**API Layer** (`src/api/`):
- FastAPI routers: threads, memories, microsoft, harvest, agents, knowledge, recommendations
- Health check at `/api/health`
- OAuth callback at `/auth/callback`

**Database** (`src/db.py`):
- SQLite for structured data: agent_runs, recommendations, knowledge metadata
- Location controlled by `DATA_DIR` env var

### Data Flow

1. User message → API → AgentOrchestrator
2. Orchestrator searches Mem0 for relevant memories
3. Retrieves conversation history from SQLite
4. Builds system prompt with context + connected integrations
5. Sends to Azure OpenAI with available tools
6. Executes tool calls in agentic loop if needed
7. Stores exchange in both conversation history and Mem0

### Configuration

All settings in `src/config.py` via Pydantic Settings, loaded from `.env`:
- `AZURE_OPENAI_*` - LLM configuration
- `AZURE_CLIENT_*` - Microsoft Graph OAuth
- `QDRANT_*` - Vector database connection
- `HARVEST_*` - Harvest integration (optional)
- `SCHEDULER_*` - Agent schedule cron expressions
- `DATA_DIR` - SQLite database location

### Key Patterns

- Single-user mode: Uses `DEFAULT_USER_ID = "default"` throughout
- Tools defined in `src/agent/tools.py` with `TOOLS` and `HARVEST_TOOLS` lists
- Agent schedules configured in settings: briefing (7am), action_item (2h), memory (1h), anomaly (4h)
- Recommendations are created by agents via `create_recommendation()` and surfaced to users
