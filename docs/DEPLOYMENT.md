# Deployment Guide

This guide deploys FinResearch to a public URL suitable for job applications.

**Stack:**
- **Database**: Neon (serverless PostgreSQL + pgvector, free tier)
- **API**: Railway (Docker, always-on)
- **Frontend**: Streamlit Community Cloud (free, GitHub-connected)

Estimated cost: **$0/month** on free tiers for a demo corpus.
Estimated time: **~30 minutes**.

---

## Step 1 — Push to GitHub

```bash
cd finresearch-agent
git remote add origin https://github.com/Adit-Vakil/finresearch-agent.git
git push -u origin main
```

Make sure `.env` is in `.gitignore` (it is). Never push API keys.

---

## Step 2 — Set up the database (Neon)

1. Go to [neon.tech](https://neon.tech) → **Sign up** (free)
2. **New project** → name it `finresearch` → region closest to you
3. Once created, go to **Connection Details** → copy the connection string

   It looks like:
   ```
   postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/finresearch?sslmode=require
   ```

4. Add the psycopg2 driver prefix:
   ```
   postgresql+psycopg2://user:password@ep-xxx.us-east-2.aws.neon.tech/finresearch?sslmode=require
   ```
   Save this — you'll need it in Step 3.

5. In the Neon SQL editor, enable pgvector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

> Tables are created automatically on first API startup via `init_db()`.

---

## Step 3 — Deploy the API (Railway)

1. Go to [railway.app](https://railway.app) → **Sign up with GitHub**
2. **New Project** → **Deploy from GitHub repo** → select `finresearch-agent`
3. Railway detects the `Dockerfile` automatically
4. Go to **Variables** → add all required environment variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string (from Step 2) |
   | `GOOGLE_API_KEY` | Your Google AI Studio key |
   | `ANTHROPIC_API_KEY` | *(optional)* |
   | `OPENAI_API_KEY` | *(optional)* |
   | `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` |
   | `CHUNK_SIZE` | `512` |
   | `CHUNK_OVERLAP` | `64` |
   | `VECTOR_SEARCH_LIMIT` | `20` |
   | `RERANK_ENABLED` | `false` |
   | `LOG_LEVEL` | `INFO` |
   | `SEC_USER_AGENT` | `FinResearch vakil.ad@northeastern.edu` |
   | `APP_ENV` | `production` |
   | `ALLOWED_ORIGINS` | `*` *(update to your Streamlit URL after Step 4)* |

5. Railway auto-deploys. Check **Deployments** tab for logs.
6. Go to **Settings** → **Networking** → **Generate Domain** → copy the URL.

   Verify: `curl https://your-app.railway.app/health`

---

## Step 4 — Deploy the frontend (Streamlit Community Cloud)

1. Go to [share.streamlit.io](https://share.streamlit.io) → **Sign in with GitHub**
2. **New app** → select `Adit-Vakil/finresearch-agent`
3. **Branch**: `main`
4. **Main file path**: `frontend/streamlit_app.py`
5. **Advanced settings** → **Secrets** → add:
   ```toml
   FINRESEARCH_API_URL = "https://your-app.railway.app"
   ```
6. Click **Deploy**. You'll get a URL like `https://adit-vakil-finresearch-agent.streamlit.app`

---

## Step 5 — Ingest demo data

Once the API is running, ingest a small corpus via Railway's shell:

1. In Railway → your service → **Shell**:
   ```bash
   python scripts/ingest_company.py --ticker AAPL --filing-type 10-K --limit 2
   python scripts/ingest_company.py --ticker MSFT --filing-type 10-K --limit 2
   python scripts/ingest_company.py --ticker NVDA --filing-type 10-K --limit 1
   ```

   Or run the sample script:
   ```bash
   python scripts/ingest_sample.py
   ```

2. Verify: `GET https://your-app.railway.app/companies`

---

## Step 6 — Update CORS (optional)

Once you have both URLs, restrict CORS to your frontend only:

In Railway environment variables, update:
```
ALLOWED_ORIGINS=https://adit-vakil-finresearch-agent.streamlit.app
```

Redeploy (Railway does this automatically when env vars change).

---

## Verifying the deployment

```bash
# Health
curl https://your-app.railway.app/health

# List companies
curl https://your-app.railway.app/companies

# Search
curl -X POST https://your-app.railway.app/search \
  -H "Content-Type: application/json" \
  -d '{"query": "supply chain risks", "ticker": "AAPL"}'

# Ask
curl -X POST https://your-app.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What supply chain risks did Apple identify?", "ticker": "AAPL"}'
```

---

## URLs to share

Once deployed, you'll have:
- **API docs**: `https://your-app.railway.app/docs`
- **Frontend**: `https://adit-vakil-finresearch-agent.streamlit.app`
- **Health**: `https://your-app.railway.app/health`

Add the frontend URL to your resume/LinkedIn. Add the GitHub repo URL for the code.

---

## Troubleshooting

**API won't start:**
- Check Railway logs → most likely `DATABASE_URL` is wrong or Neon is unreachable
- Verify the connection string has `postgresql+psycopg2://` prefix and `?sslmode=require`

**pgvector extension missing:**
- Run `CREATE EXTENSION IF NOT EXISTS vector;` in the Neon SQL editor

**Embeddings slow on first search:**
- The sentence-transformer model downloads on first use (~90MB). Railway caches this after the first deploy. Subsequent cold starts use the cached model.

**Streamlit can't reach API:**
- Check that `FINRESEARCH_API_URL` secret is set correctly (no trailing slash)
- Check that Railway service is running and domain is generated

**Ingestion fails:**
- Check `SEC_USER_AGENT` is set to a valid email
- SEC rate limits: if you're running multiple ingest commands quickly, add a few seconds between them

---

## Cost summary

| Service | Free tier | Notes |
|---|---|---|
| Neon | 0.5 GB storage, 10 GB transfer/month | More than enough for demo |
| Railway | $5 credit on signup, then ~$5/month | Hobby plan for always-on API |
| Streamlit Cloud | Free for public repos | No cost |

Total: **~$0 for the first month** (Railway credit), **~$5/month** after.

For a portfolio demo running a few hundred chunks, Railway's cheapest tier (~$5/month) is sufficient.
