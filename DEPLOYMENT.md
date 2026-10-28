# ClearNum / NumberShield Deployment Guide

This guide walks you through deploying the ClearNum phone privacy scanning application using **FreeDomain** for free domain registration and **Render.com** for free hosting.

## Architecture Overview

- **Frontend**: React 18 + TypeScript + Vite (built as static files)
- **Backend**: FastAPI + Python (serves API + frontend static files)
- **Database**: SQLite (local file, ephemeral on Render free tier)
- **Domain**: FreeDomain (.DPDNS.ORG, .US.KG, .QZZ.IO, .XX.KG, .QD.JE)

The backend already serves the built frontend files (configured in `backend/app/main.py`), so we deploy everything as a single Python web service.

---

## Prerequisites

1. **GitHub account** - for code repository and Render integration
2. **FreeDomain account** - register at [https://dash.domain.digitalplat.org/](https://dash.domain.digitalplat.org/)
3. **Render.com account** - free tier at [https://render.com/](https://render.com/)

---

## Step 1: Push Code to GitHub

```bash
cd /c/Users/user/Downloads/ClearNum

# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Complete ClearNum deployment package with pixelated/doodle theme"

# Create GitHub repository (via web UI or CLI)
# Then add remote and push
git remote add origin https://github.com/YOUR_USERNAME/clearnum.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy to Render.com

### Option A: Using render.yaml (Recommended - Blueprint)

1. Go to [https://dashboard.render.com/](https://dashboard.render.com/)
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub account if not already connected
4. Select your `clearnum` repository
5. Render will detect `render.yaml` and show the service configuration
6. Click **"Apply"** to create the service

The `render.yaml` configures:
- **Service type**: Python web service (free tier)
- **Build**: Installs Python deps + builds frontend
- **Start**: Runs `uvicorn backend.app.main:app`
- **Health check**: `/api/health`
- **Auto-deploy**: Enabled on push to main

### Option B: Manual Service Creation

If Blueprint doesn't work:

1. Go to [https://dashboard.render.com/](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Configure:
   - **Name**: `clearnum`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt && cd frontend && npm install && npm run build`
   - **Start Command**: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
5. Add Environment Variables:
   - `PYTHON_VERSION` = `3.11`
   - `NUMBERSHIELD_HOST` = `0.0.0.0`
   - `LOG_LEVEL` = `INFO`
6. Click **"Create Web Service"**

---

## Step 3: Wait for Deployment

- Render will build and deploy (first deploy takes 5-10 minutes)
- Watch the logs for any errors
- Once deployed, you'll get a URL like: `https://clearnum.onrender.com`
- Test the health endpoint: `https://clearnum.onrender.com/api/health`

**Note on Free Tier**: The free tier spins down after 15 minutes of inactivity. First request after spin-down takes 30-60 seconds to wake up.

---

## Step 4: Register Free Domain

1. Go to [https://dash.domain.digitalplat.org/](https://dash.domain.digitalplat.org/)
2. Sign up / log in
3. Click **"Register Domain"**
4. Choose an available domain (e.g., `clearnum.DPDNS.ORG` or `clearnum.US.KG`)
5. Complete registration

---

## Step 5: Configure DNS

### In FreeDomain Dashboard:

1. Go to your domain details
2. Set **Custom Nameservers** to your DNS provider (Cloudflare recommended for free), OR
3. If using FreeDomain's DNS (limited), add records:
   - **Type**: `CNAME`
   - **Name**: `@` (root) or `www`
   - **Value**: `clearnum.onrender.com` (your Render URL)
   - **TTL**: `300` (5 minutes)

### If using Cloudflare (Recommended):

1. Add domain to Cloudflare (free)
2. Change nameservers at FreeDomain to Cloudflare's nameservers
3. In Cloudflare DNS:
   - **CNAME** `clearnum` → `clearnum.onrender.com` (Proxied: ON)
   - **CNAME** `www` → `clearnum.onrender.com` (Proxied: ON)
4. Enable **"Always Use HTTPS"** in Cloudflare SSL/TLS settings

---

## Step 6: Verify Deployment

1. Wait for DNS propagation (5-60 minutes)
2. Visit your custom domain: `https://clearnum.DPDNS.ORG`
3. Test all features:
   - Phone number parsing
   - Discovery scan
   - Exposures view
   - Remediation hub
   - Prevention/spam log
   - Verification/audit
   - Demo synthetic data loader

---

## Troubleshooting

### Render Build Fails
- Check build logs for missing dependencies
- Ensure `requirements.txt` has all packages
- Verify frontend builds locally: `cd frontend && npm run build`

### Backend Won't Start
- Check start command: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Verify imports work: `backend.app.*` needs root directory in Python path
- Check environment variables are set correctly

### Database Issues
- SQLite file is stored at `data/numbershield.db` (relative to working directory)
- On Render free tier, file system is ephemeral - data resets on each deploy
- For production, add a Render **Persistent Disk** (paid) or use PostgreSQL

### CORS Errors
- Backend CORS configured for localhost:5173 and 8765
- Add your Render URL to `allow_origins` in `backend/app/main.py` if needed

### DNS Not Working
- Use `dig clearnum.DPDNS.ORG` to check propagation
- Ensure CNAME points to correct Render URL
- Check FreeDomain nameserver delegation

---

## FreeDomain Resources

- **Dashboard**: https://dash.domain.digitalplat.org/
- **Tutorial**: https://github.com/DigitalPlatDev/FreeDomain/blob/main/documents/tutorial/index.md
- **Discord**: https://discord.gg/ma4RZzMmVW
- **FAQ**: https://github.com/DigitalPlatDev/FreeDomain/blob/main/documents/domains/faq.md

---

## Render.com Resources

- **Dashboard**: https://dashboard.render.com/
- **Free Tier Limits**: https://render.com/docs/free
- **Blueprint Spec**: https://render.com/docs/blueprint-spec
- **Python Guide**: https://render.com/docs/deploy-python

---

## Expected URLs After Deployment

| Component | URL |
|-----------|-----|
| Render Default | `https://clearnum.onrender.com` |
| FreeDomain Custom | `https://clearnum.DPDNS.ORG` (or your chosen extension) |
| API Health | `https://clearnum.DPDNS.ORG/api/health` |
| API Docs | `https://clearnum.DPDNS.ORG/docs` (FastAPI auto-docs) |

---

## Important Notes

1. **Free Tier Limitations**: Render free tier spins down after inactivity. First request wakes it up (30-60s delay).

2. **Database Persistence**: SQLite on Render free tier is ephemeral. Demo data reloads on each deploy via `/api/demo/synthetic`.

3. **HTTPS**: Render provides HTTPS automatically. Cloudflare adds additional SSL/TLS features.

4. **API Rate Limits**: Discovery providers (DuckDuckGo, Wikimedia, etc.) have their own rate limits. The app handles backoff gracefully.

5. **SearXNG**: For better search results, set `SEARXNG_INSTANCE_URL` environment variable to a public SearXNG instance.

---

## Quick Test Commands

```bash
# Test health
curl https://YOUR_DOMAIN/api/health

# Test phone parse
curl -X POST https://YOUR_DOMAIN/api/identity/parse \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+14155552671", "default_region": "US"}'

# Load demo data
curl -X POST https://YOUR_DOMAIN/api/demo/synthetic
```

---

## Support

If you encounter issues:
1. Check Render build/deploy logs
2. Check FreeDomain DNS configuration
3. Join FreeDomain Discord for domain-specific help
4. Check Render community for hosting issues