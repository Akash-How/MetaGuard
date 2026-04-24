# MetaGuard Architecture Notes

## Goal

Create an action layer on top of OpenMetadata without introducing a separate application database for hackathon scope.

## High-Level Shape

- `backend/` exposes FastAPI endpoints for each feature module.
- `frontend/` renders a dashboard and module workflows.
- `backend/app/clients/openmetadata.py` is the single entry point for OpenMetadata access.
- `backend/app/clients/claude.py` is the single entry point for AI-assisted workflows.
- `shared/contracts/` is reserved for request and response contract alignment.

## Feature Modules

- `dead-data`: identify low-value or unused assets
- `data-passport`: generate human-readable summaries for data assets
- `storm-warning`: surface schema-change risks before they break downstream systems
- `blast-radius`: estimate affected downstream assets for a proposed change
- `chat`: optional lightweight metadata assistant

## Implementation Direction

- Keep service logic isolated from transport logic.
- Keep API routes thin.
- Centralize external integrations behind clients.
- Use typed schemas for all request and response bodies.
- Start with mocked responses, then swap in OpenMetadata-backed implementations incrementally.

