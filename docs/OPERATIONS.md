# TaskFlow operations

## Local database and migrations

Use a development PostgreSQL database with pgvector available. Configure
`DATABASE_URL` for that database before running:

```powershell
uv run alembic upgrade head
```

The current migration history creates the base task/conversation/vector schema
and short-lived state storage used by Supabase Google sign-in. Review generated
SQL before applying migrations to a hosted database.

## Phoenix

Start Phoenix locally:

```powershell
uv run phoenix serve
```

Set `PHOENIX_ENDPOINT=http://localhost:6006` in the FastAPI environment, then
restart the backend. Open `http://localhost:6006`; OTLP traces are received at
`http://localhost:6006/v1/traces`. TaskFlow exports spans for API requests,
model calls, embeddings, retrieval, and tool execution. The local exporter and a
SQLite-backed API request were verified. Phoenix is optional; FastAPI starts
when no endpoint is configured.

## Model routing and reliability

`AI_PROVIDER` sets the default provider. `AI_CHAT_PROVIDER` and
`AI_EMBEDDING_PROVIDER` can select providers per operation. `AI_FALLBACK_PROVIDER`
is tried after retryable primary-provider failures. `AI_TIMEOUT_SECONDS`,
`AI_RETRY_ATTEMPTS`, and `AI_RETRY_BASE_SECONDS` control bounded calls and
backoff. Gemini uses `google-genai`; Ollama uses its OpenAI-compatible endpoint.

Embedding vectors are cached in process memory with a user/provider/model/text
hash key, bounded capacity, expiration, hit/miss counters, and invalidation when
task source text changes or is deleted. The cache clears on process restart.

## Google sign-in

Google sign-in is optional and uses Supabase Auth. Enable Google under Supabase
Auth providers, configure the Google OAuth client callback shown by Supabase,
allow the local Streamlit callback URL in Supabase Auth, then set
`SUPABASE_GOOGLE_SIGNIN_ENABLED=true` and `GOOGLE_SIGNIN_REDIRECT_URI` in the
backend environment. Email/password authentication remains available through
Supabase Auth. See the [Supabase Google sign-in guide](https://supabase.com/docs/guides/auth/social-sign-in/auth-google)
for provider setup details.

## Evaluation

Ragas evaluation uses configured task retrieval and a selected development
account. Set `TASKFLOW_EVAL_USER_ID` and run `uv run python run_evaluation.py`.
Do not point evaluation at production data; evaluation invokes a model provider
and is intentionally separate from CI tests.
