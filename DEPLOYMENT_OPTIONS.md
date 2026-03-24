# NextMinds Nexus — Deployment Options

**Date:** 2026-03-24

This document outlines deployment options for the NextMinds Nexus project, considering the stack (FastAPI backend, React/Vite frontend, Supabase PostgreSQL, Google Gemini API) and the goal of keeping things affordable and manageable for a student team.

---

## Prerequisites (All Options)

Before deploying to any platform, address these items from the [code review](CODE_REVIEW_2026-03-24.md):

1. **Add authentication to `/api/admin/ingest`** — this endpoint will be publicly accessible once deployed
2. **Add rate limiting on `/api/chat`** — protects the Gemini API quota from abuse
3. **Fix the connection pooling bug** in `update_health_status()` — Supabase free tier has connection limits

You will also need:
- `GEMINI_API_KEY` — Google Gemini API key
- Supabase database credentials (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)

---

## Option 1: Railway (Recommended — Simplest)

**Cost:** Free tier available, then ~$5/month
**Complexity:** Low

- Deploy both the FastAPI backend and React frontend as separate services from the same GitHub repo
- Connects to the existing Supabase database (no migration needed)
- Auto-deploys on every git push
- Environment variables configured in the Railway dashboard
- HTTPS handled automatically

**Setup:**
1. Connect the GitHub repo to Railway
2. Create two services: one for `src/` (Python), one for `frontend/` (Node)
3. Set environment variables in the dashboard
4. Railway auto-detects the stack and builds

**Tradeoffs:** Free tier is limited to 500 hours/month. Scales well for demos but would hit limits under sustained real traffic.

---

## Option 2: Render

**Cost:** Free tier for web services (spins down after inactivity)
**Complexity:** Low

- Connect the GitHub repo, set environment variables, deploy
- Free tier has cold starts (~30 seconds after inactivity), which is acceptable for demos
- Static site hosting for the React frontend (free, no cold starts)
- Backend runs as a Web Service

**Setup:**
1. Create a Web Service for the backend (point to `src/`, set start command to `uvicorn`)
2. Create a Static Site for the frontend (point to `frontend/`, build command: `npm run build`)
3. Set environment variables for the backend service

**Tradeoffs:** Cold starts on the free tier can be confusing during live demos. Paid tier ($7/month) eliminates them.

---

## Option 3: Vercel (Frontend) + Railway or Render (Backend)

**Cost:** Free for frontend, ~$5–7/month for backend
**Complexity:** Medium

- Vercel is purpose-built for React/Vite — fast builds, global CDN, instant deploys
- Backend stays on Railway or Render
- Frontend calls the backend via the `VITE_API_URL` environment variable

**Setup:**
1. Deploy the frontend to Vercel (connect repo, set root to `frontend/`)
2. Deploy the backend to Railway or Render (as described above)
3. Set `VITE_API_URL` in Vercel to point to the backend URL

**Tradeoffs:** Two platforms to manage, but each is optimized for its role. This is the most production-like setup.

---

## Option 4: Google Cloud Run

**Cost:** Generous free tier (2 million requests/month)
**Complexity:** Medium–High

- Containerize both services with Dockerfiles
- Scale-to-zero means you only pay for actual usage
- Natural fit since the project already uses Google Gemini
- Students would need to learn Docker basics

**Setup:**
1. Write Dockerfiles for the backend and frontend
2. Build and push container images to Google Artifact Registry
3. Deploy as two Cloud Run services
4. Set environment variables via the `gcloud` CLI or Cloud Console

**Tradeoffs:** More setup (Dockerfiles, `gcloud` CLI, IAM permissions). Good learning experience but higher initial friction.

---

## Option 5: Single VPS (DigitalOcean / Hetzner)

**Cost:** ~$4–6/month
**Complexity:** High

- Full control — run both services on one machine with nginx as a reverse proxy
- No cold starts, no platform limits
- Students learn real operations: systemd services, nginx configuration, SSL with certbot

**Setup:**
1. Provision a VPS (Ubuntu recommended)
2. Install Python, Node, nginx
3. Clone the repo, install dependencies
4. Configure systemd units for uvicorn and the Vite build
5. Set up nginx as a reverse proxy with SSL via certbot

**Tradeoffs:** You own everything — updates, security patches, uptime monitoring. Most educational but most operational work.

---

## Comparison

| Option | Cost | Complexity | Cold Starts | Auto-Deploy | Best For |
|--------|------|------------|-------------|-------------|----------|
| Railway | Free–$5/mo | Low | No | Yes | Quick demos, MVPs |
| Render | Free–$7/mo | Low | Yes (free tier) | Yes | Budget-friendly demos |
| Vercel + Render | Free–$7/mo | Medium | Backend only | Yes | Production-like setup |
| Cloud Run | Free tier | Medium–High | Yes | With CI/CD | Google ecosystem, learning containers |
| Single VPS | $4–6/mo | High | No | Manual | Learning ops, full control |

---

## Recommendation

For this project, **Railway** or **Render** is the best starting point — minimal configuration, automatic deploys from GitHub, and free or near-free pricing.

If the team wants a more polished, production-like architecture, **Vercel (frontend) + Render (backend)** splits the workload onto platforms optimized for each role.
