# Repository Intelligence Assistant

An AI-powered full-stack web application for analyzing code repositories, providing semantic search, AI-driven insights, and comprehensive code intelligence.

## Features

### 🔍 Repository Search
Hybrid semantic and keyword search across your codebase with source citations and line numbers.

### 🤖 AI Assistant
Multi-turn conversations grounded in repository code with context-aware responses and source tracking.

### 📦 Dependency Explorer
Visualize and analyze repository dependencies and module relationships.

### 🧠 Code Intelligence
Map function relationships, analyze code impact, and understand dependency chains.

### 📋 Code Review
AI-powered code analysis with severity levels, findings, and actionable suggestions.

## Tech Stack

- **Backend**: FastAPI, ChromaDB (vector embeddings), SQLite
- **Frontend**: React 19, TypeScript, Vite
- **AI**: BERT embeddings, LLM integration (Groq/Gemini)
- **Styling**: Warm Beige + Charcoal theme

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+
- npm or yarn

### Backend Setup

```bash
cd repository-intelligence-assistant/backend
pip install -r requirements.txt
cp .env.example .env  # Configure with your API keys
python main.py
```

Backend will run on `http://127.0.0.1:8000`

### Frontend Setup

```bash
cd repository-intelligence-assistant/frontend
npm install
npm run dev
```

Frontend will run on `http://127.0.0.1:5173`

### Environment Variables

Create `.env` in `backend/`:
```
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
LLM_PROVIDER=groq
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/repositories` | List all repositories |
| GET | `/api/repositories/{id}` | Get repository details |
| POST | `/api/repositories/upload` | Upload and index repository (ZIP) |
| POST | `/api/repositories/search` | Search repository code |
| GET | `/api/repositories/{id}/conversations` | List conversations |
| POST | `/api/repositories/{id}/conversations` | Create conversation |
| POST | `/api/repositories/{id}/conversations/{id}/messages` | Send message |

## Project Structure

```
repository-intelligence-assistant/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   ├── services/         # Business logic
│   │   └── core/             # Core utilities
│   ├── main.py              # FastAPI entry point
│   ├── requirements.txt      # Python dependencies
│   └── tests/               # Test suite
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API client
│   │   ├── types/          # TypeScript types
│   │   └── index.css       # Styling
│   ├── package.json         # npm dependencies
│   └── vite.config.ts      # Vite configuration
```

## Usage

1. **Start both servers** (backend on 8000, frontend on 5173)
2. **Open** http://127.0.0.1:5173 in your browser
3. **Upload** a repository as a ZIP file
4. **Search** or **ask** questions about the code
5. **Explore** dependencies and code intelligence

## Database

- **SQLite**: Stores conversations and repository metadata (`backend/data/conversations.db`)
- **ChromaDB**: Vector store for embeddings (`backend/data/chroma_db/`)
- **Repositories**: Indexed code files (`backend/data/repositories/`)

## Build & Deployment

### Production Build

```bash
cd frontend
npm run build
# Deploy contents of dist/ folder
```

### Backend Deployment

Use a production ASGI server:
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

## Security

- API keys are kept in `.env` (never committed to git)
- ZIP file uploads are validated for security
- Database files are local only
- CORS is configured for localhost development

## Performance

- **Search**: 2-5 seconds
- **AI Response**: 5-15 seconds
- **Upload**: 5-30 seconds (depends on repo size)
- **API Response**: <100ms

## Development

### Backend
- Framework: FastAPI
- Database: SQLite, ChromaDB
- Testing: pytest
- Language: Python 3.10+

### Frontend
- Framework: React 19
- Language: TypeScript
- Build: Vite
- Styling: CSS with theme variables

## License

MIT License

## Support

For issues or questions:
1. Check existing GitHub issues
2. Create a new issue with details
3. Include error messages and steps to reproduce

---

**Status**: Production Ready ✅

Built with ❤️ for code analysis and intelligence
