# 🕉 Śrī Vālmīki Rāmāyaṇa — Deployment Guide

## Option A — Run Locally on Any Laptop

Requirements: Python 3.10+ installed. That is it.

### Windows
1. Copy the entire folder to the laptop
2. Double-click start.bat
3. Wait 30 seconds (installs dependencies first time)
4. Open browser -> http://localhost:5000
5. Login: admin / ramayana2024

### Mac / Linux
1. Copy the folder to the laptop
2. Open Terminal in the folder
3. Run: bash start.sh
4. Open browser -> http://localhost:5000

---

## Option B — Publicly on the Internet via Render.com (Free)

### Step 1 — Create GitHub Account
Go to https://github.com and Sign Up (free)

### Step 2 — Install Git on Windows
Go to https://git-scm.com/download/win and install it

### Step 3 — Upload to GitHub
Open PowerShell in your project folder:

  cd "C:\Users\anura\Downloads\Sri Valmiki Ramayana"
  git init
  git add .
  git commit -m "Initial commit"

Then create a new repo at https://github.com/new named: sri-valmiki-ramayana
Then run the commands GitHub shows you (git remote add origin ... etc)

### Step 4 — Deploy on Render.com
1. Go to https://render.com -> Sign Up with GitHub
2. Click New -> Web Service
3. Connect your sri-valmiki-ramayana repo
4. Render reads render.yaml automatically
5. Click Create Web Service
6. Wait 3-5 minutes

### Step 5 — Set Password on Render
In Render dashboard -> Environment tab:
  RAMAYANA_USERNAME = admin
  RAMAYANA_PASSWORD = your-secret-password

### Step 6 — Share Your URL
Your site will be at: https://sri-valmiki-ramayana.onrender.com
Share this URL with anyone!

---

NOTE: Render free tier sleeps after 15 mins of inactivity.
First visit after sleep takes ~30 seconds to wake up.

NOTE: All verse content is in data/ramayana.db (5.7MB).
No external website fetching is needed ever.
