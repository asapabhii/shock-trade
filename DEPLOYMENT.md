# Shock Trade Deployment Guide

## Complete Step-by-Step: GitHub → Render → Vercel

---

## Step 1: Push to GitHub

### 1.1 Create GitHub Repository
1. Go to [github.com/new](https://github.com/new)
2. Repository name: `shock-trade` (or whatever you prefer)
3. Set to **Private** (recommended - has API keys config)
4. DON'T initialize with README (we have one)
5. Click **Create repository**

### 1.2 Push Your Code
Open terminal in the `goal-trader` folder and run:

```bash
git init
git add .
git commit -m "Initial commit - Shock Trade multi-sport trading bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/shock-trade.git
git push -u origin main
```

⚠️ **Important**: The `.gitignore` already excludes:
- `kalshi_private_key.pem` (your private key)
- `.env` files
- `venv/` folder
- Database files

---

## Step 2: Deploy Backend to Render

### 2.1 Create Render Account
1. Go to [render.com](https://render.com)
2. Sign up with GitHub (easiest)

### 2.2 Create New Web Service
1. Click **New +** → **Web Service**
2. Connect your GitHub repo (`shock-trade`)
3. Configure:
   - **Name**: `shock-trade-api`
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

### 2.3 Add Environment Variables
In Render dashboard, go to **Environment** tab and add:

```
KALSHI_API_KEY=your_kalshi_api_key
KALSHI_BASE_URL=https://demo-api.kalshi.co
FOOTBALL_DATA_API_KEY=your_football_data_key
BANKROLL=10000
MAX_PER_TRADE_PCT=0.5
DAILY_LOSS_LIMIT=500
```

### 2.4 Add Private Key as Secret File
For `kalshi_private_key.pem`:
1. In Render dashboard → **Environment** → **Secret Files**
2. Filename: `kalshi_private_key.pem`
3. Paste your private key content
4. Add env var: `KALSHI_PRIVATE_KEY_PATH=/etc/secrets/kalshi_private_key.pem`

### 2.5 Deploy
1. Click **Create Web Service**
2. Wait for build to complete (~2-3 minutes)
3. Note your URL: `https://shock-trade-api.onrender.com`

### 2.6 Test Backend
- Health check: `https://shock-trade-api.onrender.com/`
- API docs: `https://shock-trade-api.onrender.com/docs`

---

## Step 3: Deploy Frontend to Vercel

### 3.1 Create Vercel Account
1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub

### 3.2 Import Project
1. Click **Add New...** → **Project**
2. Import your `shock-trade` repo
3. Configure:
   - **Root Directory**: Click **Edit** → select `frontend`
   - **Framework Preset**: Vite (should auto-detect)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

### 3.3 Add Environment Variable
Before deploying, expand **Environment Variables** and add:

```
VITE_API_URL=https://shock-trade-api.onrender.com/api
```

(Use your actual Render URL from Step 2.5)

### 3.4 Deploy
1. Click **Deploy**
2. Wait for build (~1-2 minutes)
3. You'll get a URL like: `https://shock-trade-xxx.vercel.app`

### 3.5 Add Custom Domain
1. Go to **Settings** → **Domains**
2. Add: `shocktrade.asapabhi.me`
3. Vercel will show DNS records to add

### 3.6 Update DNS
In your domain registrar (where you bought asapabhi.me):
1. Add a **CNAME** record:
   - Name: `shocktrade`
   - Value: `cname.vercel-dns.com`
2. Wait for DNS propagation (5 min - 48 hours)

---

## Step 4: Verify Everything Works

1. **Backend**: `https://shock-trade-api.onrender.com/docs`
2. **Frontend**: `https://shocktrade.asapabhi.me`
3. Test the dashboard loads and shows data

---

## Quick Reference

| Service | URL | Purpose |
|---------|-----|---------|
| GitHub | github.com/YOU/shock-trade | Source code |
| Render | shock-trade-api.onrender.com | Backend API |
| Vercel | shocktrade.asapabhi.me | Frontend |

## Environment Variables Summary

### Render (Backend)
```
KALSHI_API_KEY=xxx
KALSHI_PRIVATE_KEY_PATH=/etc/secrets/kalshi_private_key.pem
KALSHI_BASE_URL=https://demo-api.kalshi.co
FOOTBALL_DATA_API_KEY=xxx
BANKROLL=10000
MAX_PER_TRADE_PCT=0.5
DAILY_LOSS_LIMIT=500
```

### Vercel (Frontend)
```
VITE_API_URL=https://shock-trade-api.onrender.com/api
```

---

## Troubleshooting

### CORS Errors
Already configured in `api/main.py` for `shocktrade.asapabhi.me`

### Render Free Tier Sleep
Free tier sleeps after 15 min inactivity. First request takes ~30s to wake up.

### API Not Connecting
1. Check `VITE_API_URL` in Vercel is correct
2. Make sure it ends with `/api`
3. Redeploy frontend after changing env vars

### Build Failures
Check logs in Render/Vercel dashboards for specific errors.
