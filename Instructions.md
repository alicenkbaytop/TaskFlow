# TaskFlow — Cloud-Ready AI-Powered Task Management Platform

## Project Overview

**TaskFlow** is an AI-powered task management application that combines traditional task management with a conversational AI assistant.

Users can create, update, complete, search, and manage their tasks through a web interface or natural-language interactions. The assistant can use approved application tools to perform task operations and retrieve relevant task information through semantic search and Retrieval-Augmented Generation (RAG).

The project is designed as a **cloud-ready application from the beginning**. It uses FastAPI for the backend, Streamlit for the frontend, Supabase for PostgreSQL and authentication, Gemini for language-model and embedding capabilities, and PostgreSQL `pgvector` for semantic retrieval.

The project should remain straightforward to develop locally while being suitable for deployment as an online portfolio demo. Local development does not mean that every service must run locally: the application can connect to hosted Supabase and Gemini services using environment-based configuration.

The main objective is not to use as many technologies as possible. It is to build a small, integrated system and understand the responsibilities, request flows, security boundaries, and trade-offs of every component.

## 1. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Python and environment management | Python 3.11+, `uv` | Python runtime, dependency and virtual-environment management |
| Backend | FastAPI | REST API for task management, authentication integration, and AI interactions |
| ASGI server | Uvicorn | Runs the FastAPI application |
| Frontend | Streamlit | User interface for task management and AI chat |
| Relational database | Supabase PostgreSQL | Persistent storage for users, tasks, conversations, and related application data |
| Database platform and authentication | Supabase | Managed PostgreSQL database, Supabase Auth, and supporting platform features |
| ORM and migrations | SQLAlchemy, Alembic | Database models, sessions, queries, and schema versioning |
| Vector search | PostgreSQL `pgvector` | Stores embeddings and performs semantic similarity search in PostgreSQL |
| LLM and embeddings | Google Gemini API | Language-model responses, tool/function calling, and embedding generation |
| Agent orchestration | LangGraph | Manages agent state, tool execution, and conditional workflow transitions |
| Observability | OpenTelemetry, Arize Phoenix | Tracing, execution monitoring, and latency analysis |
| AI evaluation | Ragas | Evaluation of retrieval relevance, context recall, and answer faithfulness |
| Testing and code quality | Pytest, HTTPX, Ruff | Automated tests, API validation, linting, and formatting |
| Containerization | Docker | Reproducible application environment |
| CI/CD | GitHub Actions | Automated code-quality checks, tests, and build validation |
| Backend hosting | Render | Hosts the FastAPI service |
| Frontend hosting | Streamlit Community Cloud | Hosts the Streamlit application |

### Technology choices and boundaries

- **Supabase PostgreSQL is the source of truth.** Tasks, users, conversations, and other structured application records are stored in PostgreSQL.
- **`pgvector` is the initial vector-search solution.** It avoids introducing a separate vector database while the application is small. A dedicated vector database can be considered later if there is a demonstrated need.
- **Gemini is the initial model provider.** Use it for language-model interactions and a compatible embedding model. Keep the LLM and embedding integrations behind small service interfaces so another provider can be added without rewriting business logic.
- **Supabase Auth handles user identity.** FastAPI validates the user's access token and enforces authorization in the application/service layer. PostgreSQL Row Level Security (RLS) can provide an additional database-level protection layer.
- **LangGraph is introduced after basic tool calling is understood.** Do not start with a complex agent workflow.
- **Render and Streamlit Community Cloud are the initial hosting targets.** Deployment details and free-tier limits should be checked when deployment begins because hosting plans can change.

Do not add Kubernetes, Kafka, Redis, microservices, or a separate API gateway to the initial project. Add infrastructure only when a concrete requirement justifies it.

## 2. Architectural Approach

TaskFlow uses a layered architecture with clear responsibilities:

1. **Frontend:** Streamlit displays the application and sends HTTP requests to FastAPI.
2. **Backend/API:** FastAPI receives requests, validates input, authenticates users, and calls application services.
3. **Application services:** Services contain reusable business logic for tasks, conversations, retrieval, and model-provider access.
4. **Database:** Supabase PostgreSQL stores authoritative application records.
5. **Vector retrieval:** `pgvector` stores embeddings and metadata associated with source records.
6. **AI workflow:** The assistant uses Gemini and approved tools. LangGraph coordinates the workflow when the basic tool-calling implementation is understood.
7. **Observability and evaluation:** OpenTelemetry/Phoenix provide traces, while Ragas and representative datasets help evaluate retrieval and answer quality.

### Core architectural principles

- **FastAPI owns the HTTP interface.** The frontend communicates with backend endpoints rather than accessing the database directly.
- **The backend owns authorization.** Never trust a user ID supplied only in a request body or URL. Derive the authenticated user identity from a validated token.
- **Business logic belongs in services.** API routes and agent tools should reuse the same application/service functions rather than duplicating CRUD logic.
- **The agent uses controlled tools.** It must not execute arbitrary SQL or directly manipulate database records outside approved application functions.
- **PostgreSQL is authoritative.** Vector records support retrieval; they do not replace the source task or conversation records.
- **Validate model-generated arguments.** Treat all model-generated tool arguments as untrusted input and validate them before execution.
- **Keep provider integrations replaceable.** Model-provider-specific code should be isolated from task-management and agent business logic.
- **Start with a modular monolith.** Keep one backend application with clear modules. Do not split it into microservices without a real need.

## 3. Architecture

### High-level request flow

```text
Streamlit frontend
       |
       | HTTPS requests + access token
       v
FastAPI backend (Render)
       |
       +------ Authentication / authorization
       |
       +------ Task endpoints ------> Task service ---------> Supabase PostgreSQL
       |                                                        |
       |                                                        +-- tasks
       |                                                        +-- users / ownership
       |                                                        +-- conversations
       |                                                        +-- embeddings (pgvector)
       |
       +------ Chat endpoint -------> AI / agent workflow
                                      |
                                      +---- Gemini API
                                      |
                                      +---- Approved application tools
                                      |       |
                                      |       +---- Task service
                                      |       +---- Retrieval service
                                      |
                                      +---- Supabase PostgreSQL / pgvector

OpenTelemetry instrumentation
       |
       v
Phoenix (development/evaluation environment)
```

### Authentication and authorization flow

1. A user signs in through Supabase Auth.
2. Supabase Auth issues an access token.
3. The frontend sends the token with requests to FastAPI, normally in the `Authorization: Bearer ...` header.
4. FastAPI validates the token and identifies the authenticated user.
5. Backend services apply ownership filters to database operations.
6. Database RLS policies provide an additional protection layer where configured.

The backend must not rely on the frontend to enforce access restrictions. Every task, conversation, and retrieval operation must be scoped to the authenticated user.

### Database and vector-search design

Use PostgreSQL for both relational records and vector data in the initial version.

- A task row is the authoritative task record.
- An embedding row stores a vector representation and a reference to its source task.
- The embedding record must include enough ownership/source metadata to enforce access restrictions during retrieval.
- Retrieval queries must be scoped to the authenticated user before returning task context.
- Updating or deleting source text must update or remove its associated embedding record.

For the initial implementation, synchronous embedding updates are acceptable if they keep the design understandable. Later, consider retries, background jobs, or an outbox pattern if reliability requirements justify them.

### Architectural principles

1. **FastAPI owns the HTTP interface.** Streamlit calls backend endpoints.
2. **Supabase Auth establishes identity.** FastAPI validates access tokens before protected operations.
3. **Authorization is enforced by the backend.** Services scope database access to the authenticated user.
4. **RLS is defense in depth.** Configure and test database policies; do not assume enabling Supabase Auth automatically secures every query made through a privileged backend connection.
5. **PostgreSQL is the source of truth.** `pgvector` is an extension used for retrieval, not a separate authority for task state.
6. **The agent uses controlled tools.** It cannot run arbitrary SQL or bypass application services.
7. **Provider-specific code stays isolated.** Gemini calls and embedding generation should be behind service functions/interfaces.
8. **Keep the first implementation simple.** Add abstractions only when they solve a concrete problem.

## 4. Suggested Repository Structure

The repository should grow with the implementation. Do not create empty modules for future phases before they are needed.

```text
taskflow/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   ├── database.py
│   │   └── models.py
│   ├── schemas/
│   │   └── tasks.py
│   ├── api/
│   │   ├── tasks.py
│   │   └── auth.py
│   └── services/
│       └── task_service.py
├── ui/
│   └── streamlit_app.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── migrations/
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── README.md
└── Instructions.md
```

As later phases are implemented, the structure can grow to include:

```text
app/
├── agent/
│   ├── prompts.py
│   ├── tools.py
│   ├── state.py
│   └── workflow.py
├── services/
│   ├── llm_service.py
│   ├── embedding_service.py
│   ├── retrieval_service.py
│   └── conversation_service.py
├── db/
│   └── vector.py
└── core/
    ├── security.py
    └── telemetry.py
```

The exact structure is not mandatory. Prefer clear responsibilities and understandable imports over creating many folders prematurely.

## 5. Implementation Roadmap

Complete the phases in order. Each phase should produce a small, understandable increment of the application.

### Phase 1 — Backend Fundamentals and PostgreSQL

**Goal:** Build a working task-management API backed by Supabase PostgreSQL before adding AI.

Learn and implement:

- Project setup with `uv`.
- Python project structure and configuration.
- FastAPI application and route structure.
- HTTP methods, request/response flow, and status codes.
- Pydantic request and response schemas.
- PostgreSQL fundamentals: tables, primary keys, foreign keys, constraints, and indexes.
- Supabase project setup and database connection.
- SQLAlchemy models and sessions.
- Environment-based database configuration.
- Alembic migrations.
- Task CRUD operations.
- Basic filtering, sorting, and pagination.
- Error handling and input validation.

Suggested task fields:

- `id`
- `user_id` (ownership relationship)
- `title`
- `description` (optional)
- `status`
- `priority`
- `due_date` (optional)
- `created_at`
- `updated_at`

**Deliverable:** A working FastAPI task API connected to Supabase PostgreSQL. During this phase, use a development-only user context if needed; implement real authentication in Phase 2 rather than adding a temporary security design that will be discarded.

### Phase 2 — Frontend Integration and Authentication

**Goal:** Connect the frontend to the API and introduce real user identity and data isolation.

Learn and implement:

- Streamlit fundamentals.
- HTTP requests from Streamlit to FastAPI.
- Displaying, creating, editing, completing, and deleting tasks.
- Showing API validation and error messages.
- Authentication concepts: identity, access tokens, and bearer-token headers.
- Supabase Auth sign-up, sign-in, and sign-out.
- Sending the access token from Streamlit to FastAPI.
- Validating Supabase-issued access tokens in FastAPI.
- Deriving the current user from the validated token.
- User-scoped database queries in service functions.
- PostgreSQL RLS policies where appropriate.
- Tests proving that one user cannot access another user's tasks.

**Deliverable:** A usable multi-user task-management application with backend-enforced authentication and authorization.

### Phase 3 — Gemini Integration and Tool Calling

**Goal:** Let the assistant understand natural-language requests and perform approved task operations.

Learn and implement:

- Calling the Gemini API from Python.
- API keys and environment-variable configuration.
- System instructions and prompt structure.
- Model responses and function/tool calling.
- Tool definitions and argument schemas.
- A simple Python tool-calling loop:
  1. Send the user's message and relevant context to Gemini.
  2. Inspect whether the model requested a tool.
  3. Validate the tool name and arguments.
  4. Execute the corresponding application/service function.
  5. Return the tool result to the model.
  6. Produce a user-facing response.
- Tool execution errors and limits.
- Authorization checks inside tools: a tool must operate only on the authenticated user's records.

Initial tools could include:

- `create_task`
- `list_tasks`
- `get_task`
- `update_task`
- `complete_task`
- `delete_task`

The tools must call the same application/service functions used by the REST API. Do not duplicate CRUD logic or allow the model to supply an arbitrary `user_id` to bypass authorization.

**Deliverable:** An AI assistant that can manage the authenticated user's tasks through approved tools.

### Phase 4 — Embeddings, pgvector, Semantic Search, and RAG

**Goal:** Allow the assistant to find relevant task information by meaning, not only exact keywords.

Learn and implement:

- What embeddings represent and how vector similarity works.
- Gemini embedding API and embedding dimensions.
- PostgreSQL `pgvector` extension and vector columns.
- Storing embeddings with source task IDs and ownership metadata.
- Indexing task descriptions and selected notes.
- Semantic similarity queries.
- User-scoped retrieval and access control.
- Returning relevant task references and context to the assistant.
- Updating and deleting embeddings when source task text changes.
- Retrieval quality checks.

The retrieval service must filter by authenticated user. Never retrieve another user's task context and rely on the LLM to hide it.

**Deliverable:** The assistant can answer questions using semantically retrieved information from the authenticated user's tasks.

### Phase 5 — Agent Orchestration and Conversation Memory

**Goal:** Improve the assistant's workflow after the basic tool-calling loop is understood.

Learn and implement:

- Conversation state.
- Persisted conversation messages in PostgreSQL.
- Conversation ownership and user-scoped history.
- Context-window management.
- LangGraph state, nodes, edges, and conditional transitions.
- Tool execution and conditional workflow transitions.
- Handling failed tools and ambiguous requests.
- Separating conversation history from retrieved task context.
- Basic limits for tool calls and workflow execution.

Start with the simple Python tool-calling loop from Phase 3. Introduce LangGraph when its state and workflow features solve a real problem. Do not use an agent framework merely to make the project look more advanced.

**Deliverable:** A stateful assistant with a clear, testable workflow and user-isolated conversation history.

### Phase 6 — Observability and Evaluation

**Goal:** Understand how the AI application behaves and measure its quality.

Learn and implement:

- Structured application logging.
- Request, database, model, retrieval, and tool execution timing.
- OpenTelemetry tracing.
- Arize Phoenix integration.
- RAG evaluation with Ragas where appropriate.
- Representative evaluation datasets.
- Retrieval quality and answer-quality checks.
- Latency and failure analysis.
- Safe handling of sensitive data in logs and traces.

Do not record access tokens, API keys, or unnecessary private task content in logs or traces. Review what telemetry is sent to any external service before enabling it.

**Deliverable:** An observable application with repeatable evaluation and documented limitations.

### Phase 7 — Deployment, Containerization, and CI/CD

**Goal:** Publish an online demo and make the application reproducible.

Learn and implement:

- Environment-based configuration for local and hosted environments.
- Secrets management in hosting platforms.
- Docker images and container fundamentals.
- Health checks and service readiness.
- Git branching, pull requests, and review workflow.
- GitHub Actions for Ruff and automated tests.
- Docker build validation.
- Deploying FastAPI to Render.
- Deploying Streamlit to Streamlit Community Cloud.
- Connecting the deployed services securely.
- CORS configuration for the frontend origin.
- Production database connection settings and migrations.
- Basic API rate limiting and sensible request/tool limits.
- Deployment logs and basic monitoring.

The application should not depend on a developer's local machine or local database. Use hosted Supabase PostgreSQL and environment variables for hosted configuration.

Ordinary CI tests should not require live Gemini calls. Mock model responses in normal automated tests; keep any live-provider checks separate and intentional.

**Deliverable:** A working online demo with a deployed frontend, deployed API, hosted database, and automated CI checks.

### Phase 8 — Hardening and Optional Extensions

**Goal:** Improve reliability and demonstrate thoughtful engineering beyond the initial working demo.

Possible additions, only when justified:

- More comprehensive authorization and RLS policy tests.
- API rate limiting and abuse protection.
- Background jobs for slow or retryable operations.
- Retry and timeout policies for external model calls.
- Model-provider fallback or provider switching.
- Caching where measurements show a benefit.
- More advanced evaluation datasets and regression checks.
- A dedicated vector database if PostgreSQL vector search no longer meets requirements.
- Additional UI and accessibility improvements.
- Deployment and operational documentation.

Do not add these features all at once. Select extensions based on a real limitation or a clear learning objective.

## 6. Configuration and Secrets

Use environment variables for configuration that differs between local development and deployment.

The `.env.example` file should document variable names without containing real secrets. For example:

```env
DATABASE_URL=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=
GEMINI_API_KEY=
GEMINI_MODEL=
GEMINI_EMBEDDING_MODEL=
PHOENIX_ENDPOINT=
```

Only include variables that the implementation actually needs. The exact Supabase token-validation approach must be selected and documented during Phase 2; do not assume that every Supabase key or secret is interchangeable.

Rules:

- Never commit `.env` files, API keys, access tokens, or service-role credentials.
- Never expose a Supabase service-role key in Streamlit or browser-visible code.
- Keep privileged credentials on the backend only.
- Use the least-privileged credentials and database access patterns appropriate to the operation.
- Keep `.env.example` updated when configuration changes.

## 7. Development and Learning Rules

These rules are important to the project:

1. **Work incrementally.** Implement one small feature at a time.
2. **Understand before moving on.** Explain what each important file, function, dependency, and request flow does.
3. **Avoid large code dumps.** Prefer small, focused code examples with comments where useful.
4. **Do not skip fundamentals.** Explain unfamiliar Python, HTTP, database, authentication, and framework concepts before depending on them.
5. **Follow the roadmap.** Do not jump to agents, RAG, observability, or deployment before the preceding foundations are understood.
6. **Separate development from validation.** Complete the planned development phases before starting the dedicated testing, debugging, fixing, and optimization period. Do not run commands, scripts, or tests unless explicitly authorized by the user.
7. **Never claim something was tested unless it was actually run.** Clearly distinguish code that has been written from code that has been executed and verified.
8. **Keep the MVP focused.** Do not add infrastructure or abstractions without a concrete reason.
9. **Use AI as a learning aid, not a substitute for understanding.** The developer should be able to explain and modify the code independently.
10. **Record architectural decisions.** Briefly document why a technology or design was selected when the choice matters.
11. **Prefer working software over an impressive folder structure.**
12. **Keep secrets and private data out of Git.** Use `.env.example` for variable names and ignore `.env`, credentials, local data, and generated artifacts.
13. **Do not assume changes have been applied.** Treat code supplied by the user as the current version, and wait for confirmation before treating proposed edits as implemented.
14. **Ask before changing scope.** Do not introduce optional refactoring or extra features that are not part of the agreed roadmap.
15. **Teach one step at a time.** After explaining or proposing a focused step, pause for the user's confirmation before moving to the next step.

## 8. Definition of a Successful Project

The project is successful when it demonstrates a working progression:

1. A FastAPI task API backed by Supabase PostgreSQL.
2. A Streamlit frontend connected to the API.
3. Supabase Auth integration with backend-enforced user authorization.
4. An AI assistant using Gemini to perform controlled task operations.
5. Semantic retrieval using embeddings and PostgreSQL `pgvector`.
6. A stateful assistant workflow with conversation memory.
7. Tests, observability, and measurable AI evaluation.
8. A reproducible deployment with a public online demo and CI checks.

The priority is to build a working, secure, understandable system. The developer should be able to explain the architecture, follow a request through each layer, justify the technology choices, identify limitations, and discuss the trade-offs in an engineering interview.
