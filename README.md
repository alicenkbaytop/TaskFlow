# TaskFlow

TaskFlow is a multi-user task manager with a FastAPI backend, Streamlit UI, Supabase Auth, PostgreSQL/pgvector retrieval, and an AI assistant orchestrated with LangGraph. It uses local Ollama models by default, with Gemini available as an optional provider.

## Architecture

- Streamlit signs users in through Supabase Auth and sends the resulting bearer token to FastAPI.
- FastAPI validates each token against Supabase Auth and derives the user ID from the verified response. Request bodies cannot choose an owner.
- SQLAlchemy services scope task, conversation, and retrieval queries by that user ID.
- Supabase PostgreSQL stores tasks, conversations, messages, and 768-dimensional embeddings. Alembic enables pgvector and installs owner RLS policies.
- Ollama tool calls use the existing validated tool schemas and task services. Phoenix/OpenTelemetry remains optional; Ragas evaluation uses a specifically selected account.

## Local setup

Requires Python 3.11+, `uv`, a Supabase project with PostgreSQL and Auth enabled, and [Ollama](https://ollama.com/) running locally.

1. Copy `.env.example` to `.env` and fill in the Supabase project URL, public anon key, and PostgreSQL session-pooler connection URL. The Supabase direct database hostname is IPv6-only unless the project has its IPv4 add-on; use the dashboard's session pooler for IPv4 networks. Never place provider keys or a Supabase service-role key in Streamlit configuration.
2. Install dependencies: `uv sync --all-groups`.
3. Download the local models once: `ollama pull qwen2.5:3b` and `ollama pull nomic-embed-text`. Keep Ollama running while using TaskFlow.
4. Apply the schema: `uv run alembic upgrade head`. The database role used for migrations must be allowed to install/use `vector` and create policies.
5. Start the API: `uv run uvicorn main:app --reload` (health check: `/health`, OpenAPI: `/docs`).
6. The Streamlit app loads frontend settings from the repository-root `.env` (or existing process environment/Streamlit secrets). Set `TASKFLOW_API_URL=http://localhost:8000`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY` there, then run `uv run streamlit run ui/streamlit_app.py` in another terminal.

For isolated API tests and quick local CRUD only, a fresh `taskflow_dev.db` SQLite file is available when `DATABASE_URL` is omitted. It does not support semantic retrieval and is not the production architecture. Hosted environments must set PostgreSQL `DATABASE_URL` and run Alembic. Existing SQLite/Qdrant data is not imported automatically because the old records have no owner identity; assign records to real account IDs before importing them.

## Configuration

Backend variables: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `AI_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL`, optional `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, `PHOENIX_ENDPOINT`, and `CORS_ORIGINS`. Set `AI_PROVIDER=gemini` to use Gemini instead of local Ollama. Frontend variables: `TASKFLOW_API_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY`. The anon key is a public Supabase client key; privileged credentials stay on the backend.

## AI and retrieval

The assistant uses Ollama's OpenAI-compatible local endpoint for tool calling by default (`qwen2.5:3b`). When `AI_PROVIDER=gemini`, chat uses Google's `google-genai` SDK and native function calling with `gemini-3.5-flash-lite`. Local `nomic-embed-text` vectors have 768 dimensions and match `vector(768)`. If you change embedding providers, regenerate stored vectors before semantic search because providers use different embedding spaces. Retrieval always filters by owner, then loads the authoritative task rows.

LangGraph bounds tool rounds. Tools validate their arguments, ignore user IDs from model output, and invoke the same user-scoped service functions as the REST API. Conversation IDs are checked against the current account on each request.

## Migrations and deployment

- Render: deploy the repository Dockerfile, set backend environment variables, and use a Supabase PostgreSQL connection string. The container applies Alembic migrations before starting Uvicorn. Configure the Render health check path as `/health`.
- Streamlit Community Cloud: deploy `ui/streamlit_app.py`; set `TASKFLOW_API_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY` in app secrets/environment. Add the Streamlit origin to backend `CORS_ORIGINS` if browser calls require it.
- GitHub Actions runs Ruff, pytest, and a Docker build. Normal tests do not make live provider calls.
- The API limits clients to 120 requests per minute by IP, with chat limited to 20 per minute. This in-memory limit is per process and is suitable as a basic guard for a single Render instance; use hosting or shared storage limits if scaling across instances.
- Phoenix tracing exports only when `PHOENIX_ENDPOINT` is set. Review telemetry configuration before sending traces externally; application logging does not record access tokens or task content.

Database RLS protects tasks, conversations, embeddings, and messages for Supabase-authenticated database roles. The backend also applies ownership predicates in every service query. Use a least-privilege runtime database role; a PostgreSQL table owner or bypass-RLS role can bypass RLS, so service-level checks remain required.

## Evaluation

The Ragas dataset contains representative examples. To run it, configure an AI provider and PostgreSQL, ensure the selected account has suitable tasks, set `TASKFLOW_EVAL_USER_ID` to that account's Supabase user ID, then run `uv run python run_evaluation.py`. Cloud evaluation may incur provider costs; it is separate from CI.

## Known limitations

- User signup confirmation and email delivery follow the Supabase project settings. The UI currently requires sign-in again after an access token expires; refresh-token renewal is not implemented.
- Supabase's built-in email sender is rate-limited. Configure custom SMTP under Supabase Auth for ongoing account confirmation and recovery email delivery; keep email confirmation enabled.
- Embedding writes are synchronous; if a provider is unavailable, the task is saved and the indexing failure is logged.
- pgvector HNSW/IVFFlat indexing and performance tuning are deferred until data volume justifies them.
- Existing local SQLite and Qdrant data cannot be assigned safely without an explicit account ownership mapping.
- No hosted deployment or live Supabase/provider verification is performed by CI.
