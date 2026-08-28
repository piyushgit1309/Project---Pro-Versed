# PRO-VERSED
### National Student Innovation Platform, AI Assistant & IP Marketplace

**PRO-VERSED** is a complete, unified national platform connecting student creators, faculty mentors, institutional campus coordinators, and industry enterprise sponsors across Bharat.

---

## 🌟 Key Features & Complete Functional Capabilities

1. **24/7 AI Innovation Assistant Chatbot**:
   - Floating interactive AI widget (`/api/ai/chat`) providing instant guidance on industry grants, originality checks, BOM pricing, and 4-step escrow protection.
   - Domain-specific advice across AI & Robotics, Green Tech, MedTech, IoT, FinTech, and Aerospace.

2. **Virtual Meeting & Video Collaboration Rooms**:
   - Built-in video conferencing rooms (`/api/meetings`) powered by WebRTC / Jitsi Meet for milestone reviews, team collaboration, and industry investor pitches.
   - Camera/Mic toggles, screen sharing, encrypted rooms, and 1-click review calls directly from the Task Board.

3. **Decentralized IPFS Storage & Code Vault**:
   - Content-Addressed Storage (CAS) engine (`/api/ipfs/...`) with cryptographic SHA-256 Content Identifiers (CIDs e.g. `QmXoyp...`).
   - Immutable, tamper-proof proof-of-work timestamps for prior art patent documentation.

4. **Industry Grants, Commercial Licensing & Funding Portal**:
   - Corporate sponsors submit formal funding proposals across 4 modalities: Research Grants, Commercial IP Licenses, Pre-Placement Hiring Funds, and Seed Equity.
   - Interactive proposal negotiation with 1-click Acceptance, Decline, and Counter-Offers.

5. **Project Portfolio & 5-Stage Lifecycle Tracking**:
   - Comprehensive tracking across 5 development stages: `1. Idea Phase` ➔ `2. In Development` ➔ `3. Working Prototype Ready` ➔ `4. Completed` ➔ `5. Research Published / Commercialized`.
   - Granular Hardware & Component List (BOM) breakdown, unit prices, code repositories, and live demo links.

6. **Task & Milestone Progress Board**:
   - 4-column workflow (**1. To Do** ➔ **2. In Progress** ➔ **3. Under Review** ➔ **4. Completed**).
   - Dedicated Faculty Mentor Gatekeeper for 1-click milestone verification & digital sign-off.

7. **Smart Originality & Similarity Scanner**:
   - Mathematical TF-IDF and N-Gram similarity engine checking project summaries against the nationwide student repository.
   - Delivers real-time Originality Scores (e.g. 96% Unique) with matching keywords and similarity breakdown.

8. **Project Marketplace with 4-Step Safe Buyer Protection**:
   - Monetization platform for assembled hardware prototypes, trained AI models, and spare lab parts with a transparent 4-step escrow workflow (Order ➔ Verify ➔ Deliver ➔ Pay).

9. **National Innovation Analytics Dashboard**:
   - Real-time visual metrics powered by Chart.js covering tech stack popularity, lifecycle progression, domain distributions, and quality scores.

10. **1-Click Multi-Role Demo Mode**:
    - Instant persona switching between **Student Creator** (Aarav Sharma), **Faculty Mentor** (Dr. Sunita Verma), **Campus Coordinator** (Prof. Rajesh Iyer), **Industry Partner** (Vikramaditya Singhania), and **Platform Admin**.

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.9+ installed
- Web Browser

### Option 1: One-Click Shell Script (Linux / macOS)
```bash
chmod +x run.sh
./run.sh
```

### Option 2: Windows Batch Run
```cmd
run.bat
```

### Option 3: Direct Python Launch (From Root Directory)
```bash
pip install -r requirements.txt
python main.py
```
Open your browser at **`http://localhost:8000`**.

### Option 4: Docker & Docker Compose
```bash
docker-compose up --build -d
```
Open your browser at **`http://localhost:8000`**.

---

## 🏛️ Project Directory Structure
```
Pro-Versed/
├── backend/
│   ├── main.py            # FastAPI Application & API Endpoints
│   ├── ai_chat.py         # 24/7 AI Innovation Assistant Engine
│   ├── meetings.py        # Video Conference & WebRTC Meeting Service
│   ├── ipfs.py            # Decentralized IPFS Storage Engine & CID Generator
│   ├── database.py        # SQLite Database Layer & Seed Data
│   ├── models.py          # Data Models & Row Serializers
│   ├── schemas.py         # Pydantic Request/Response Schemas
│   ├── plagiarism.py      # TF-IDF & N-Gram Text Similarity Engine
│   └── requirements.txt   # Python Dependencies
├── frontend/
│   ├── index.html         # Modern Glassmorphic Single-Page Application
│   ├── styles.css         # Custom Design System, Cinematic Lighting & Animations
│   └── app.js             # Interactive Controller, AI Chat, Meetings & IPFS
├── Dockerfile             # Production Container Definition with Dynamic $PORT
├── docker-compose.yml     # Multi-Container Orchestration
├── Procfile               # Heroku / Render / Dokku Deployment Entrypoint
├── render.yaml            # Render 1-Click Web Service Blueprint
├── railway.json           # Railway 1-Click Cloud Blueprint
├── fly.toml               # Fly.io Production Configuration
├── vercel.json            # Vercel Serverless Routing
├── DEPLOYMENT.md          # Multi-Cloud Hosting Manual
├── main.py                # Root Entrypoint
├── requirements.txt       # Root Python Dependencies
├── run.sh                 # Fast Launch Script (Linux/macOS)
├── run.bat                # Fast Launch Script (Windows)
└── README.md              # Complete Project Documentation
```

---

## 🇮🇳 Bharat Student Innovation Platform
