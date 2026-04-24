# MetaGuard

MetaGuard is a lean hackathon project built on top of OpenMetadata. It turns metadata into action across four core modules:

- Dead Data Finder
- Data Passport
- Storm Warning
- Blast Radius

The PRD also references a lightweight chat experience for metadata exploration, so this repository includes a place for that as well.

## Current Status

This repository now contains a functional backend-first hackathon implementation with an in-memory metadata source, plus a lightweight frontend scaffold. It is structured so the mock backend logic can later be swapped to real OpenMetadata and Claude integrations.

## Completed

- Monorepo-style folder structure for backend, frontend, shared contracts, and docs
- FastAPI backend with PRD-aligned routes for Dead Data, Passport, Storm Warning, Blast Radius, and Chat
- In-memory OpenMetadata client implementing the shared methods described in the PRD
- Working backend logic for asset classification, trust scoring, schema alert simulation, blast-radius scoring, and context-aware chat
- React + TypeScript frontend scaffold with feature-oriented modules
- Root documentation that explains scope, structure, and what is still pending
- Initial architecture note in `docs/architecture.md`
- Backend test coverage for the main module flows

## Pending

### Backend

- Replace the in-memory OpenMetadata client with the real OpenMetadata SDK integration
- Replace the deterministic Claude stub with the live Claude API integration
- Add richer error handling, logging, async concurrency, and production-grade validation
- Expand test coverage for edge cases and failure scenarios

### Frontend

- Install and configure the actual React toolchain dependencies
- Build the dashboard layout and navigation visuals from the chosen design system
- Implement interactive feature screens for each module
- Connect API client calls to the backend endpoints and render real responses
- Add charts, loading states, empty states, and error states
- Add component tests and end-to-end flows

### Product Features

- Dead Data Finder scoring logic using usage, freshness, lineage, and ownership signals
- Data Passport narrative generation using metadata and AI summaries
- Storm Warning polling or webhook workflow for schema-change alerts
- Blast Radius impact analysis using lineage and schema dependency traversal
- Chat experience that can synthesize metadata context safely

### DevOps and Delivery

- Add `.env.example` files for backend and frontend
- Add local run scripts and a single-command developer workflow
- Add CI for linting, tests, and builds
- Add deployment configs for Railway and Vercel

## Suggested Build Order

1. Implement backend config and health/auth plumbing.
2. Implement the shared OpenMetadata client.
3. Build one end-to-end feature first, preferably Dead Data Finder.
4. Add Data Passport with Claude integration.
5. Add Storm Warning and Blast Radius.
6. Finish frontend polish, tests, and deployment.

## Repository Layout

```text
.
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- clients/
|   |   |-- core/
|   |   |-- schemas/
|   |   `-- services/
|   `-- tests/
|-- frontend/
|   |-- public/
|   `-- src/
|       |-- app/
|       |-- components/
|       |-- features/
|       |-- lib/
|       `-- types/
|-- shared/
|   |-- contracts/
|   `-- examples/
`-- docs/
```

## Notes

- The scaffold follows the PRD's separation of concerns: OpenMetadata as source of truth, FastAPI for orchestration, and React for the operator-facing UI.
- The backend can now run in `mock` mode for demos and is prepared for `live` OpenMetadata mode via environment variables.
- Local setup steps are documented in `docs/local-setup.md`.
