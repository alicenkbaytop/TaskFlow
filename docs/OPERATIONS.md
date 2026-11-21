# Operations and deployment

## Supabase database

Create a PostgreSQL project with the `vector` extension available. Configure
`DATABASE_URL` with the Supabase session pooler and `sslmode=require`. Set the
same database URL in the backend's Alembic environment. For a new database run:

```powershell
uv run alembic upgrade head
```

The current migration chain creates the base task/conversation/message/vector
schema and RLS policies, removes only the retired transient Google OAuth state
table, then adds chronological-message and HNSW cosine indexes, followed by an
activity timestamp/index for conversations. Migration 0004 builds an HNSW index
over existing 768-dimensional embeddings; large datasets may require a planned
maintenance window. Existing task, conversation,
message, and embedding rows are preserved.

Email/password registration and login are handled by Supabase Auth from
Streamlit. FastAPI validates each bearer token against `/auth/v1/user` and
derives the identity. CRUD and retrieval queries filter by that identity.

## Model providers and routing

Set model API keys on the backend only. Gemini is the primary chat and embedding
provider. OpenRouter and Groq are fallback chat providers. The preferred
alternative IDs are `google/gemma-4-31b-it:free` and `qwen/qwen3.8-27b`.

Model IDs and listed capabilities checked against current vendor catalogues:

- OpenRouter lists Gemma 4 31B free with native function calling, JSON mode,
  and a 262,144-token context. Its free endpoint is rate-limited and has one
  serving provider at the time of this check. [OpenRouter model page](https://openrouter.ai/google/gemma-4-31b-it:free)
- Groq lists Qwen 3.8 27B with tool use, JSON mode, a 131,072-token context,
  and 16,384 max completion tokens. The model is marked Preview. [Groq model
  catalogue](https://console.groq.com/docs/models), [Groq tool-use matrix](https://console.groq.com/docs/tool-use/overview)
- Gemini remains configured as `gemini-3.5-flash-lite`; the Google API docs
  list function calling and the configured model. [Gemini function calling](https://ai.google.dev/gemini-api/docs/get-started), [Gemini model pricing/catalogue](https://ai.google.dev/gemini-api/docs/pricing)

These catalogue checks establish identifier and documented capability support,
not live API availability, account access, or successful credentials. The
application never silently changes a configured model ID.

The router picks Gemini by default. Optional task importance classification
uses explicit provider preferences only when `AI_COMPLEX_PROVIDER` or
`AI_IMPORTANT_PROVIDER` is set. Otherwise task type does not assert that a
provider is higher quality. The provider must be configured and support the
required tool-calling operation. Retryable timeouts, network errors, 429, and
selected 5xx responses get bounded retries and then candidate fallback. Auth
and model errors skip retries and can move to another configured provider.
Repeated retryable provider failures trigger an in-process cooldown. Cooldown
state is local to each backend process; see Future work before horizontally
scaling.

Embedding generation is pinned to Gemini and 768 dimensions. The router does
not fall back to a different embedding space, so stored vectors cannot become
mixed. If Gemini embeddings are unavailable, task CRUD remains available and
semantic indexing/search may be unavailable until the provider recovers.

## Render API

The repository includes a manual-deploy Render blueprint in `render.yaml`.
Review service settings, then provide:

- `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY`.
- `GEMINI_API_KEY`; optionally `OPENROUTER_API_KEY` and `GROQ_API_KEY`.
- `CORS_ORIGINS` with the exact Streamlit Community Cloud origin.
- Optional `PHOENIX_ENDPOINT` and `PHOENIX_API_KEY`.
- Model routing, retry, pool, and timeout variables as needed.

The Docker entrypoint executes `alembic upgrade head` before Uvicorn starts.
Render supplies the port; Uvicorn binds `0.0.0.0`. `/health` performs a simple
database query. Production rejects SQLite. Read migration SQL and confirm
`DATABASE_URL` points at the intended project before deploying. The migration
will remove only the unused `oauth_states` table, add indexes, and add a
conversation timestamp; it does not
reset Supabase or drop user application data. No production migration was run
in this workspace.

## Streamlit Community Cloud

Deploy the repository entry point `ui/streamlit_app.py`. The root
`requirements.txt` installs only the frontend runtime dependencies. Add these
values in the Community Cloud app's Settings → Secrets, using TOML format:

For local development, copy `.env.frontend.example` to `.env.frontend`. The UI
loads only those frontend settings and does not read backend `.env` values.

```toml
TASKFLOW_API_URL = "https://<your-render-service>.onrender.com"
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_ANON_KEY = "<public-anon-key>"
```

Add that app's origin to Render `CORS_ORIGINS` and to Supabase Auth's allowed
redirect/site URL configuration. Use the anon/publishable key only. Never add
model API keys, a database URL, or Supabase service-role key to Streamlit.

## Phoenix hosted receiver

Deploy Phoenix separately (for example, on an existing managed container host)
or use a hosted Phoenix project that accepts OTLP/HTTP. Do not set the backend
to `localhost:6006` in Render: that points back to the Render container.

Configure the receiver's OTLP/HTTP endpoint, HTTPS ingress, and auth token in
its host. On Render set `PHOENIX_ENDPOINT` to the receiver base URL, such as
`https://<phoenix-host>/v1/traces`, and `PHOENIX_API_KEY` if required. The
backend's OTLP exporter uses that endpoint and bearer authorization. Open the
Phoenix dashboard URL provided by the host, select the `taskflow` project, and
inspect spans named `agent.llm_request`, `ai.routing_attempt`,
`ai.routing_decision`, `agent.tool_execution`, `ai.embedding`, retrieval, and
FastAPI request spans. Provider, model, fallback, status, and latency attributes
are intended for operations. Prompt content and credentials are not attached.

TaskFlow treats tracing as optional and exporter errors do not stop API startup.
Delivery is unverified until the hosted receiver and access credentials are
available; there is no configured production Phoenix URL in this repository.

## Local checks

```powershell
uv run alembic upgrade head
uv run uvicorn main:app --reload
uv run streamlit run ui/streamlit_app.py
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

For local development Phoenix, use an independently installed Phoenix service
or container and set its OTLP endpoint. The application image does not bundle
the Phoenix server. Ragas evaluation is a development-only workflow that needs
a configured provider and a development dataset.
