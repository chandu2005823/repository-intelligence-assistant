# Repository Intelligence Assistant - Quick Start Guide

Get up and running in **5 minutes**!

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.10+** (tested on 3.13.2)
- **Node.js 18+** (tested on 26.13.0)
- **npm 9+**
- **5 GB free disk space**
- **API Key** (Gemini or Groq)

Check versions:
```bash
python --version
node --version
npm --version
```

---

## Step 1: Get API Key

### Option A: Google Gemini (Recommended)

1. Visit: https://ai.google.dev/
2. Sign in with Google account
3. Click "Get API Key"
4. Create new project or select existing
5. Generate API key
6. Copy the key (starts with `AIza...`)

**Free Tier:** 15 requests/minute, 1M tokens/day

### Option B: Groq

1. Visit: https://console.groq.com/
2. Sign up for free account
3. Navigate to API Keys section
4. Create new API key
5. Copy the key (starts with `gsk_...`)

**Free Tier:** 30 requests/minute, 14K tokens/minute

---

## Step 2: Backend Setup

### 2.1 Navigate to Backend Directory

```bash
cd repository-intelligence-assistant/backend
```

### 2.2 Create Python Virtual Environment

```bash
python -m venv .venv
```

### 2.3 Activate Virtual Environment

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

You should see `(.venv)` in your terminal prompt.

### 2.4 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI 0.129.0
- ChromaDB 1.5.9
- Sentence Transformers 6.1.0
- Groq 1.5.0
- Google GenAI 3.1.0
- And more...

**Installation time:** ~2-3 minutes

### 2.5 Configure Environment Variables

Create `.env` file from template:

```bash
copy .env.example .env     # Windows
cp .env.example .env       # Linux/macOS
```

Edit `.env` with your preferred text editor:

**For Gemini:**
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...your_key_here
GEMINI_MODEL=gemini-2.5-flash

# Upload Limits (Optional - defaults shown)
MAX_UPLOAD_SIZE_MB=2048
MAX_EXTRACTED_SIZE_MB=2048
MAX_SINGLE_FILE_SIZE_MB=50
MAX_REPOSITORY_FILES=50000
```

**For Groq:**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...your_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Upload Limits (Optional - defaults shown)
MAX_UPLOAD_SIZE_MB=2048
MAX_EXTRACTED_SIZE_MB=2048
MAX_SINGLE_FILE_SIZE_MB=50
MAX_REPOSITORY_FILES=50000
```

**Important:** No quotes around the API key!

### 2.6 Start Backend Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Keep this terminal open!** Backend is now running.

---

## Step 3: Frontend Setup

### 3.1 Open New Terminal

Keep the backend terminal running and open a new terminal window.

### 3.2 Navigate to Frontend Directory

```bash
cd repository-intelligence-assistant/frontend
```

### 3.3 Install Node Dependencies

```bash
npm install
```

This installs:
- React 19.3.1
- TypeScript 7.0.2
- Vite 8.3.5
- React Router DOM 7.18.5
- React Markdown 10.1.0
- And more...

**Installation time:** ~1-2 minutes

### 3.4 Start Frontend Development Server

```bash
npm run dev
```

**Expected Output:**
```
  VITE v8.3.5  ready in 234 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.1.x:5173/
  ➜  press h + enter to show help
```

---

## Step 4: Verify Installation

### 4.1 Check Backend Health

Open browser and visit:
```
http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "repository-intelligence-backend"
}
```

### 4.2 Check API Documentation

Visit:
```
http://localhost:8000/docs
```

You should see interactive API documentation (Swagger UI).

### 4.3 Check Frontend

Visit:
```
http://localhost:5173
```

You should see the Repository Intelligence Assistant UI with upload interface.

---

## Step 5: Upload Your First Repository

### Method 1: Using the Web UI

1. Open http://localhost:5173
2. Click "Upload Repository" button
3. Select a ZIP file (up to 2 GB)
4. Wait for upload and indexing (30-60 seconds for small repos)
5. Repository ID will be displayed

### Method 2: Using curl

```bash
# Upload a test repository
curl -X POST http://localhost:8000/api/repositories/upload \
  -F "file=@your-repo.zip"
```

**Expected Response:**
```json
{
  "repository_id": "d1b4c42256e3489ab1534ac0711df5eb",
  "status": "analyzed",
  "upload_info": {
    "compressed_size_mb": 1.23,
    "extracted_size_mb": 5.45,
    "extracted_files": 42,
    "compression_ratio": 4.43
  },
  "summary": {
    "file_count": 42,
    "languages": {"Python": 30, "JavaScript": 12},
    ...
  },
  "chunking": {
    "chunk_count": 256,
    ...
  },
  "indexing": {
    "indexed_chunks": 256
  }
}
```

**Save the `repository_id` for next steps!**

---

## Step 6: Try Core Features

### 6.1 Search Code

```bash
curl -X POST http://localhost:8000/api/repositories/search \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "YOUR_REPO_ID",
    "query": "authentication function",
    "top_k": 5
  }'
```

### 6.2 Ask Questions

```bash
curl -X POST http://localhost:8000/api/repositories/ask \
  -H "Content-Type: application/json" \
  -d '{
    "repository_id": "YOUR_REPO_ID",
    "question": "How does the main function work?",
    "top_k": 5
  }'
```

### 6.3 Get Dependency Graph

```bash
curl http://localhost:8000/api/repositories/YOUR_REPO_ID/dependencies
```

### 6.4 Get Code Intelligence

```bash
curl "http://localhost:8000/api/repositories/YOUR_REPO_ID/intelligence?query=login"
```

### 6.5 Run Code Review

```bash
curl -X POST http://localhost:8000/api/repositories/YOUR_REPO_ID/review
```

---

## Common Commands Reference

### Backend Commands

```bash
# Start backend
cd backend
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Stop backend
# Press CTRL+C in the terminal

# Restart backend after .env changes
# Press CTRL+C, then run uvicorn command again

# View logs
# Logs appear in the terminal where backend is running

# Update dependencies
pip install --upgrade -r requirements.txt
```

### Frontend Commands

```bash
# Start frontend
cd frontend
npm run dev

# Stop frontend
# Press CTRL+C in the terminal

# Build for production
npm run build

# Preview production build
npm run preview

# Update dependencies
npm install
```

### API Health Checks

```bash
# Check backend health
curl http://localhost:8000/health

# Check root endpoint
curl http://localhost:8000/

# List all repositories
curl http://localhost:8000/api/repositories

# Get specific repository
curl http://localhost:8000/api/repositories/YOUR_REPO_ID
```

---

## Troubleshooting

### Backend Issues

#### ❌ "Module not found" error

**Solution:**
```bash
# Ensure virtual environment is activated
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Reinstall dependencies
pip install -r requirements.txt
```

#### ❌ "Port 8000 already in use"

**Solution:**
```bash
# Use different port
uvicorn main:app --reload --port 8001

# Or kill process using port 8000
# Windows: netstat -ano | findstr :8000
# Linux/macOS: lsof -ti:8000 | xargs kill -9
```

#### ❌ "API key not configured" error

**Solution:**
```bash
# Verify .env file exists
cat .env  # Linux/macOS
type .env  # Windows

# Check API key format (no quotes!)
# WRONG: GEMINI_API_KEY="AIza..."
# RIGHT: GEMINI_API_KEY=AIza...

# Restart backend after editing .env
```

#### ❌ ChromaDB initialization error

**Solution:**
```bash
# Delete ChromaDB directory
rm -rf data/chroma_db  # Linux/macOS
rmdir /s data\chroma_db  # Windows

# Restart backend (will recreate database)
```

### Frontend Issues

#### ❌ "Cannot find module" error

**Solution:**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json  # Linux/macOS
rmdir /s node_modules & del package-lock.json  # Windows

npm install
```

#### ❌ "Port 5173 already in use"

**Solution:**
```bash
# Kill process
# Windows: netstat -ano | findstr :5173
# Linux/macOS: lsof -ti:5173 | xargs kill -9

# Or change port in vite.config.ts
```

#### ❌ CORS error in browser console

**Solution:**
- Ensure backend is running on port 8000
- Check `main.py` CORS configuration includes your frontend URL
- Clear browser cache

### Upload Issues

#### ❌ "Upload limit exceeded"

**Solution:**
```bash
# Increase limits in .env
MAX_UPLOAD_SIZE_MB=4096
MAX_EXTRACTED_SIZE_MB=4096

# Restart backend
```

#### ❌ "Archive contains unsafe path"

**Solution:**
- Ensure ZIP doesn't contain:
  - Absolute paths (`/home/user/...`, `C:\...`)
  - Parent directory references (`../../../`)
  - Symlinks
- Create ZIP from project root

#### ❌ "Invalid ZIP archive"

**Solution:**
- Verify file is actually a ZIP (not RAR, 7z, etc.)
- Try recreating ZIP with standard tools
- Ensure ZIP is not corrupted

### API Issues

#### ❌ Rate limit exceeded (429 error)

**Solution:**
- **Gemini:** Wait 1 minute (15 requests/minute limit)
- **Groq:** Wait 1 minute (30 requests/minute limit)
- Consider using different provider
- Upgrade to paid tier for higher limits

#### ❌ "Repository not found" (404 error)

**Solution:**
```bash
# List all repositories
curl http://localhost:8000/api/repositories

# Verify repository_id is correct
# IDs are 32-character hex strings
```

---

## Next Steps

Now that your system is running:

1. ✅ **Upload a Repository** - Try with a small project first
2. 🔍 **Search for Code** - Test the hybrid search
3. 💬 **Ask Questions** - Try the AI assistant
4. 📊 **Explore Dependencies** - Visualize import relationships
5. 🔬 **Run Code Review** - Check for security issues
6. 📈 **Review Intelligence** - Analyze call graphs

---

## Project Structure Quick Reference

```
repository-intelligence-assistant/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── .env                 # Your configuration (create this!)
│   ├── .env.example         # Template
│   ├── requirements.txt     # Python dependencies
│   ├── app/
│   │   ├── api/            # REST endpoints
│   │   └── services/       # Business logic
│   └── data/               # Storage (auto-created)
│       ├── repositories/   # Uploaded repos
│       ├── chroma_db/     # Vector database
│       └── *.db           # SQLite databases
│
└── frontend/
    ├── package.json        # Node dependencies
    ├── vite.config.ts     # Build configuration
    └── src/
        ├── main.tsx       # Entry point
        ├── App.tsx        # Root component
        ├── components/    # UI components
        └── services/      # API client
```

---

## Environment Variables Explained

```env
# Which LLM provider to use
LLM_PROVIDER=gemini          # or "groq"

# Gemini settings
GEMINI_API_KEY=AIza...       # Get from https://ai.google.dev/
GEMINI_MODEL=gemini-2.5-flash  # Model name

# Groq settings (alternative)
GROQ_API_KEY=gsk_...         # Get from https://console.groq.com/
GROQ_MODEL=openai/gpt-oss-120b  # Model name

# Upload Limits (Optional - defaults work for most cases)
MAX_UPLOAD_SIZE_MB=2048      # Max compressed ZIP size
MAX_EXTRACTED_SIZE_MB=2048   # Max extracted repository size
MAX_SINGLE_FILE_SIZE_MB=50   # Max individual file size
MAX_REPOSITORY_FILES=50000   # Max file count
```

**Tips:**
- Start with default limits
- Increase only if you hit errors
- Large limits = longer indexing time
- Each repository is isolated

---

## Supported File Types

**Fully Analyzed (AST):**
- Python (.py)

**Partially Analyzed (Regex):**
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)

**Indexed (Text-only):**
- Java, C, C++, C#, Go, Rust, PHP, Ruby
- JSON, YAML, TOML, XML
- Markdown, HTML, CSS, SQL

**Automatically Excluded:**
- Binary files
- `.git/` directories
- `node_modules/`, `.venv/`, `__pycache__/`
- Build artifacts (`dist/`, `build/`)
- IDE configs (`.vscode/`, `.idea/`)
- Environment files (`.env*`)

---

## Performance Tips

1. **Small Repos First** - Test with <50 MB repos
2. **Clean Before Upload** - Remove `node_modules/`, `.venv/` before zipping
3. **Exclude Build Artifacts** - Don't include `dist/`, `build/` directories
4. **Use .gitignore** - If using Git, respect .gitignore patterns
5. **Monitor Logs** - Check backend terminal for errors

---

## Getting Help

- **Documentation:** See `DOCUMENTATION.md` for complete technical details
- **API Docs:** http://localhost:8000/docs (when backend is running)
- **GitHub Issues:** Report bugs or request features
- **Logs:** Check backend terminal output for detailed error messages

---

## Quick Test Script

Create `test-upload.sh` (Linux/macOS) or `test-upload.bat` (Windows):

```bash
#!/bin/bash
# Save as test-upload.sh

echo "Testing Repository Intelligence Assistant..."

# Check backend health
echo "1. Checking backend health..."
curl -s http://localhost:8000/health | python -m json.tool

# List repositories
echo -e "\n2. Listing repositories..."
curl -s http://localhost:8000/api/repositories | python -m json.tool

echo -e "\n✅ Backend is running and healthy!"
echo "Ready to upload repositories."
```

Run with:
```bash
chmod +x test-upload.sh  # Linux/macOS
./test-upload.sh
```

---

## Summary Checklist

- [ ] Python 3.10+ installed
- [ ] Node.js 18+ installed
- [ ] API key obtained (Gemini or Groq)
- [ ] Backend virtual environment created
- [ ] Backend dependencies installed
- [ ] `.env` file configured with API key
- [ ] Backend running on port 8000
- [ ] Frontend dependencies installed
- [ ] Frontend running on port 5173
- [ ] Health check passed
- [ ] Test repository uploaded
- [ ] Search and QA working

**If all checkboxes are checked:** 🎉 **You're ready to use the Repository Intelligence Assistant!**

---

**Quick Start Version:** 1.0  
**Last Updated:** November 11, 2024  
**Estimated Setup Time:** 5-10 minutes

For detailed information, see `DOCUMENTATION.md`.
