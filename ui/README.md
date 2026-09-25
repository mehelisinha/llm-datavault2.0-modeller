# DWA UI

Reviewer UI for the DWA Metadata Generator.

## Stack

React 18 · Vite 6 · TypeScript (strict) · TanStack Router & Query · Tailwind v4 · zod · Vitest.

## Quick start

```bash
pnpm install
cp .env.example .env.local
pnpm dev               # http://localhost:5173, proxies /api → :8000
pnpm typecheck
pnpm test
pnpm build             # outputs to dist/, mounted by FastAPI in prod
```

Run the FastAPI backend in another shell:

```bash
& "$PWD\.venv\Scripts\python.exe" -m uvicorn dbt_builder.api:app --reload
```

After the API is up, regenerate the typed client:

```bash
pnpm gen:api
```

## Layout

| Path | Purpose |
|---|---|
| `src/main.tsx` | Boot: query client, router, theme |
| `src/env.ts` | zod-validated env access |
| `src/constants/` | Route paths + DV domain constants (mirror of backend) |
| `src/api/` | `openapi-fetch` client, generated schema, query hooks |
| `src/routes/` | File-based routes (TanStack Router) |
| `src/components/` | Reusable UI primitives |
| `src/lib/` | Pure helpers (`cn`, `actor`, …) |
| `tests/` | Vitest suites |
