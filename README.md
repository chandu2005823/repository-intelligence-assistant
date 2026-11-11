# Repository Intelligence Assistant

A full-stack web application for analyzing and querying code repositories using AI-powered semantic search and code intelligence features.

## Quick Start

### Backend Setup
```bash
cd repository-intelligence-assistant/backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Frontend Setup
```bash
cd repository-intelligence-assistant/frontend
npm install
npm run dev
```

## Features

1. **Repository Search** - Hybrid keyword and semantic search across indexed code
2. **AI Assistant** - Ask questions about your repository with AI-powered responses
3. **Dependency Explorer** - Visualize repository dependency graphs
4. **Code Intelligence** - Analyze function relationships and code impact
5. **Code Review** - Get AI-powered code analysis and suggestions

## Architecture

- **Backend**: FastAPI with ChromaDB (vector store) and SQLite (conversations)
- **Frontend**: React + TypeScript + Vite
- **Data**: SQLite databases, ChromaDB embeddings, indexed repositories

## Project Structure

```
repository-intelligence-assistant/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   ├── services/         # Business logic
│   │   └── core/             # Core utilities
│   ├── data/                 # Databases and storage
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── services/         # API client
│   │   ├── types/           # TypeScript types
│   │   └── index.css        # Styling
│   ├── package.json
│   └── vite.config.ts
└── testing/                 # Testing resources
```

## API Documentation

See `repository-intelligence-assistant/DOCUMENTATION.md` for complete API reference.

## Testing

See `testing/README.md` for testing procedures and guidelines.

## License

MIT
