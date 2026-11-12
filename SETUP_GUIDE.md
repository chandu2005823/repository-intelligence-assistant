# Setup Guide for Repository Intelligence Assistant

This guide explains how to set up and run the Repository Intelligence Assistant on a new machine.

## Important: About Repository Data

⚠️ **Repository IDs from one machine won't work on another machine**

The application stores:
- Indexed repositories in `backend/data/repositories/`
- Vector embeddings in `backend/data/chroma_db/`
- Conversations in `backend/data/conversations.db`

These are **local files** and are **not shared** between machines. Each machine will have its own set of repositories and data.

## Prerequisites

- Python 3.10+
- Node.js 16+
- npm or yarn
- Git

## Step 1: Clone the Repository

```bash
git clone https://github.com/chandu2005823/repository-intelligence-assistant.git
cd repository-intelligence-assistant
```

## Step 2: Backend Setup

### Install Python Dependencies

```bash
cd repository-intelligence-assistant/backend
pip install -r requirements.txt
```

### Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```
LLM_PROVIDER=groq
GROQ_API_KEY=your_actual_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

Get API keys from:
- **Groq**: https://console.groq.com
- **Gemini**: https://ai.google.dev

### Start Backend Server

```bash
python main.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## Step 3: Frontend Setup

Open a **new terminal** and run:

```bash
cd repository-intelligence-assistant/frontend
npm install
npm run dev
```

You should see:
```
VITE v5.x.x ready in XXX ms
➜  Local:   http://127.0.0.1:5173/
```

## Step 4: Access the Application

Open your browser and go to:
```
http://127.0.0.1:5173
```

## Using the Application

### 1. Upload a Repository

- Click "Choose ZIP archive"
- Select a ZIP file containing your code
- Click "Upload repository"
- Wait for indexing to complete

### 2. Search Code

- Go to "Repository Search" tab
- Select the repository you just uploaded
- Enter a search query (e.g., "function", "class")
- Click "Search"

### 3. Ask AI Questions

- Go to "AI Assistant" tab
- Ask a question about your code
- Get AI-powered responses with source citations

### 4. Explore Features

- **Dependency Explorer**: View module relationships
- **Code Intelligence**: Analyze function relationships
- **Code Review**: Get AI-powered code analysis

## Troubleshooting

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
pip install -r requirements.txt
```

### Frontend Won't Start

**Error**: `npm: command not found`

**Solution**: Install Node.js from https://nodejs.org/

### "Repository ID not found"

**This is expected!** Repository IDs are local to each machine.

**Solution**: Upload a new repository ZIP file to generate a new ID.

### Port Already in Use

**Error**: `Address already in use`

**Solution**: 
```bash
# Kill process on port 8000 (backend)
netstat -ano | findstr :8000

# Kill process on port 5173 (frontend)
netstat -ano | findstr :5173
```

### API Key Invalid

**Error**: `Unauthorized` or `Invalid API key`

**Solution**: 
1. Check your `.env` file has correct API key
2. Verify API key is valid on provider's website
3. Make sure LLM_PROVIDER matches your API key

## Database Files

The following files are created automatically on first run:

- `backend/data/conversations.db` - Conversation history
- `backend/data/chroma_db/` - Vector embeddings
- `backend/data/repositories/` - Indexed code files

These are **local only** and won't sync between machines.

## Development

### Run Tests

```bash
cd backend
pytest tests/ -v
```

### Build Frontend for Production

```bash
cd frontend
npm run build
```

Output will be in `dist/` folder.

## Project Structure

```
repository-intelligence-assistant/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── services/      # Business logic
│   │   └── core/          # Core utilities
│   ├── main.py           # FastAPI entry point
│   ├── requirements.txt   # Python dependencies
│   ├── .env.example      # Environment template
│   └── tests/            # Test suite
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API client
│   │   └── types/        # TypeScript types
│   ├── package.json      # npm dependencies
│   └── vite.config.ts    # Build config
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/repositories` | List repositories on this machine |
| POST | `/api/repositories/upload` | Upload new repository |
| POST | `/api/repositories/search` | Search code |
| POST | `/api/repositories/{id}/conversations/{id}/messages` | Send message |

## Performance Tips

1. **Smaller ZIP files**: Upload repositories <100MB for faster processing
2. **Use specific queries**: More specific searches return better results
3. **Give AI time**: First response may take 5-15 seconds

## Getting Help

1. Check error messages in terminal
2. Verify API keys are correct
3. Try uploading a different repository
4. Check GitHub issues: https://github.com/chandu2005823/repository-intelligence-assistant/issues

## Next Steps

- Explore the different features
- Upload various repositories
- Try different search queries
- Ask the AI different questions

---

**Note**: Each machine is independent. Repository IDs, data, and conversations are not shared between machines.

Happy coding! 🚀
