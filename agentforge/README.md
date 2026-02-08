# AgentForge

Autonomous Multi-Agent Research & Analysis Platform.

## Prerequisites

1.  **Ollama**: Install and run Ollama.
    *   `ollama pull qwen2.5:3b`
    *   `ollama pull nomic-embed-text`
2.  **Python 3.10+**

## Setup

1.  Run the setup script to create a virtual environment and install dependencies:
    *   **Windows**: `.\setup.ps1`

## Usage

### Ingest Documents (Optional)
Place your PDF/TXT/MD files in `agentforge/data/knowledge_base` and run:
```powershell
.\venv\Scripts\python agentforge/scripts/ingest_documents.py
```

### Run UI
```powershell
.\venv\Scripts\streamlit run agentforge/ui/streamlit_app.py
```

### Run API
```powershell
.\venv\Scripts\python agentforge/api/main.py
```
