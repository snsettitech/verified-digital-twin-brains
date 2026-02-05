# Deployment Context (Project Defaults)

This file records the agreed deployment defaults so we do not re‑ask setup questions.

## Defaults (Confirmed)
- Deployment flow: `git push` triggers auto‑deploy to Render (backend) and Vercel (frontend).
- Datastores: use existing Supabase + Pinecone (no Render‑provisioned databases).
- Frontend hosting: Vercel.

## Notes
- Backend Render configuration is tracked in `render.yaml` (Blueprint format).
