# Local Setup

## 1. Frontend

From [frontend](c:\Users\amohanra\OneDrive - The Estée Lauder Companies Inc\Desktop\OpenMeta\frontend):

```powershell
npm install
npm run dev
```

Create `frontend/.env` from `frontend/.env.example` if you need a custom backend URL.

## 2. Backend

Create `backend/.env` from `backend/.env.example`.

Important variables:

- `APP_MODE=mock` uses the in-memory demo dataset
- `APP_MODE=live` switches the metadata client to OpenMetadata REST calls
- `OPENMETADATA_URL` should point to your OpenMetadata host
- `OPENMETADATA_JWT` should be your OpenMetadata access token
- `ANTHROPIC_API_KEY` enables real Claude calls once the client is upgraded from stub mode

Recommended backend run command once Python 3.11 is available:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

## 3. OpenMetadata

Use the official Docker quickstart from OpenMetadata:

- https://docs.open-metadata.org/latest/quick-start/local-docker-deployment

The REST API shape used by this repo follows the official OpenMetadata metadata APIs:

- `GET /v1/tables`
- `GET /v1/tables/name/{fqn}`

Reference:

- https://docs.open-metadata.org/latest/main-concepts/metadata-standard/apis
- https://docs.open-metadata.org/latest/api-reference/data-assets/tables

## 4. Suggested Startup Order

1. Start OpenMetadata.
2. Fill `backend/.env`.
3. Start the FastAPI backend.
4. Start the frontend.
5. Confirm the frontend health indicator shows the backend is reachable.

## Current Limitation

This machine currently has Node and Docker available, but Python is not installed as an executable yet. Backend startup and pytest verification need a real Python installation, not just the Windows Store alias.

