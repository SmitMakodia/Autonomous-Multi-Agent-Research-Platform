<div align="center">

# 🌌 AgentForge
### The Autonomous, Zero-Bloat, Multi-Agent RAG Platform

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org/)
[![Llama.cpp](https://img.shields.io/badge/Llama.cpp-black?style=for-the-badge&logo=c%2B%2B)](https://github.com/ggerganov/llama.cpp)
[![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=Playwright&logoColor=white)](https://playwright.dev/)

*A completely local, fully offline AI research assistant featuring intelligent VRAM swapping, deep web scraping, and a breathtaking Perplexity-style UI.*

</div>

---

## ⚡ Overview

**AgentForge** is not just another wrapper. It is a highly optimized, completely autonomous multi-agent research platform designed to run on consumer hardware (e.g., RTX 3060 6GB). It orchestrates a swarm of specialized agents that can browse the live internet, scrape JavaScript-heavy websites, parse complex PDF documents, and perform high-fidelity Vision OCR—all while managing its own memory and VRAM dynamically.

No API keys. No cloud dependencies. No bloated vector databases. Just pure, unadulterated local AI power.

---

## ✨ Key Features

### 🧠 Intelligent VRAM Management (Hot-Swapping)
Running a large language model and a massive vision model simultaneously on a 6GB GPU will instantly crash your system. AgentForge solves this elegantly:
- The system runs the fast **Qwen3.5-4B** model as the core brain via `llama.cpp`.
- When you upload an image, AgentForge **suspends Qwen**, flushing 100% of it from VRAM.
- It dynamically loads the official **GLM-OCR** (Safetensors) model directly onto the GPU, processes the image at lightning speed, wipes the GPU memory cleanly via PyTorch garbage collection, and resumes Qwen seamlessly.

### 🕸️ Deep Web Search & Crawl (Hybrid Engine)
AgentForge bypasses standard API rate-limits by employing a robust, anti-bot fallback chain:
1. **Search:** Uses `DuckDuckGo` (`ddgs`) to securely find the top URLs.
2. **Primary Scrape:** Bootstraps **Crawl4AI** using a headless Chromium browser to execute JavaScript, bypass Cloudflare/bot-protections, and extract clean semantic Markdown.
3. **Fallback:** If a website blocks headless browsers, it instantly falls back to a custom `BeautifulSoup` + `markdownify` Python scraper to guarantee context injection.

### 💾 Zero-Bloat SQLite RAG
We stripped out heavy memory hogs like ChromaDB. AgentForge uses a hyper-optimized, pure **SQLite** memory architecture:
- Context chunks and CPU-generated embeddings are serialized directly into an `agentforge.db` file.
- **Session Isolation:** Each chat is strictly isolated. Vector cosine-similarity is computed via NumPy instantly in RAM, ensuring zero memory leak across different sessions.

### 🎨 Perplexity-Style UI
A gorgeous, modern, zero-scrollbars frontend built with Vanilla JS and CSS (No React/Node.js bloat):
- **Glassmorphism Design:** Dark mode, translucent overlays, and an interactive particle physics background canvas.
- **Live "Thinking" Stream:** Watch the AI's internal reasoning stream live into a collapsible UI block (styled with a sleek Lightbulb icon) before it generates the final answer.
- **Source Cards & Context Modals:** View exactly what websites and files the AI read through beautiful, clickable Source Cards and an expandable raw context modal.

---

## ⚙️ Architecture Flow

```mermaid
graph TD;
    User((User)) -->|Prompt + Files| UI[Glassmorphism UI]
    UI -->|FastAPI| API[Main Endpoint]
    
    API --> Routing{File Attached?}
    Routing -->|Yes: Image| VRAM[VRAM Swap: Pause Qwen -> Run GLM-OCR -> Resume Qwen]
    Routing -->|Yes: PDF/Doc| FILE[File Read Agent]
    Routing -->|No| ORCH[Orchestrator]
    
    VRAM --> SQL[(SQLite RAG Memory)]
    FILE --> SQL
    
    ORCH --> SEARCH[Web Search Agent]
    SEARCH --> DDG[DuckDuckGo]
    DDG --> CRAWL[Crawl4AI Headless Chromium]
    CRAWL --> SQL
    
    SQL --> |Top 10 Chunks| LLM[Llama.cpp Qwen3.5]
    LLM --> |Streaming Markdown| UI
```

---

## 🚀 Installation & Setup

### 1. Prerequisites
- **OS:** Windows 10/11
- **Python:** 3.12+
- **GPU:** NVIDIA GPU with CUDA support (Minimum 6GB VRAM recommended)

### 2. Clone the Repository
```bash
git clone https://github.com/yourusername/AgentForge.git
cd AgentForge
```

### 3. Automatic Setup
AgentForge comes with a fully automated setup script that creates your virtual environment, installs all pip dependencies, and downloads the required AI models.

Simply open PowerShell as Administrator and run:
```powershell
.\setup_infrastructure.ps1
```

*Note: The script will download several gigabytes of models (Qwen3.5-4B GGUF and GLM-OCR Safetensors). Please be patient!*

### 4. GPU Acceleration (Crucial)
To ensure the Vision OCR model runs on your GPU and not your CPU, you must install the CUDA-enabled version of PyTorch.
Open your activated virtual environment and run:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

---

## 🕹️ Usage

AgentForge features absolute one-click operation via Windows Batch files.

### Starting the Platform
Simply double-click:
📄 `start_agentforge.bat`

**What it does:**
1. Cleans any ghost processes on port `8081`.
2. Activates the Python virtual environment.
3. Launches the FastAPI backend and natively clones pristine `[filename:line]` terminal logs into `logs/log.log`.
4. Automatically opens `http://localhost:8081` in your default web browser.

### Stopping the Platform
Simply double-click:
📄 `stop_agentforge.bat`

**What it does:**
1. Gracefully shuts down the FastAPI server.
2. Force-kills the `llama.cpp` process, instantly freeing 100% of your VRAM.
3. Closes the terminal windows.

---

## 📂 Project Structure

```text
AgentForge/
├── backend/
│   ├── agents/               # Swarm logic (Search, Scrape, OCR, File Read)
│   ├── llm/                  # Llama.cpp streaming client & SQLite Memory Manager
│   ├── mcp_layer/            # Tool Routing and Execution
│   ├── rag/                  # Embeddings, Retriever, Vector Store
│   ├── config.py             # Global constants
│   ├── logger_setup.py       # Custom stdout/stderr OS-level interceptor
│   └── main.py               # FastAPI Endpoints
├── frontend/
│   ├── static/               # Highlight.js & Marked.js
│   ├── app.js                # SSE streaming, UI logic, Particle Physics
│   ├── index.html            # Main UI Layout
│   └── style.css             # Glassmorphism & Perplexity styling
├── logs/                     # Single unified log.log file
├── models/                   # Local weights (Qwen GGUF, GLM-OCR)
├── uploads/                  # User uploaded documents
├── start_agentforge.bat      # One-click startup
└── stop_agentforge.bat       # One-click graceful teardown
```

---



# AgentForge Comprehensive System Architecture

This diagram provides a high-level, easy-to-understand overview of the AgentForge platform. It focuses on the logical flow, agent interactions, tools, and the hardware management process without getting bogged down in specific filenames.

```mermaid
---
config:
  layout: elk
---
flowchart TB

    subgraph User_Interface ["User Interface"]
        User(("User"))
        UI["Glassmorphism UI<br>(Chat & File Uploads)"]
    end

    subgraph API_Gateway ["API Gateway"]
        Endpoints["API Endpoints<br>(Query, Stream, History)"]
    end

    subgraph Orchestration ["Core Orchestration"]
        Orchestrator["Main Orchestrator"]
        PromptBuilder["System Prompt Builder"]
    end

    subgraph Swarm_Agents ["Agent Swarm"]
        Router["Tool Router (MCP)"]
        WebSearch["Web Search Agent"]
        WebScrape["Web Scrape Agent"]
        FileRead["File Read Agent"]
        OCR["Vision OCR Agent"]
    end

    subgraph External_Tools ["Web & Scraping Engine"]
        DDG["DuckDuckGo Search"]
        Crawl4AI["Crawl4AI (Headless Browser)"]
        BS4["BeautifulSoup (Fallback)"]
    end

    subgraph Memory_RAG ["RAG & Memory (SQLite)"]
        VectorStore["Vector Store (Chunks & Embeddings)"]
        Retriever["Retriever (Cosine Sim & BM25)"]
        History["Chat History Manager"]
    end

    subgraph Hardware_LLM ["VRAM Management & AI Models"]
        VRAM_Manager["VRAM Controller"]
        Qwen["Qwen3.5 (LLM)"]
        GLM_OCR["GLM-OCR (Vision Model)"]
        XMLParser["XML Output Parser"]
    end

    %% Interaction Flow
    User -- Prompts & Files --> UI
    UI -- Sends Data --> Endpoints
    Endpoints -- Triggers --> Orchestrator
    
    %% Agent Routing
    Orchestrator -- Evaluates Request --> Router
    Orchestrator -- Direct File Intercept --> FileRead
    Orchestrator -- Direct Image Intercept --> OCR
    
    Router -- Dispatches --> WebSearch & WebScrape
    
    %% Scraping Flow
    WebSearch -- Queries --> DDG
    DDG -- Top URLs --> Crawl4AI
    WebScrape -- Scrapes URL --> Crawl4AI
    Crawl4AI -- If Blocked/Timeout --> BS4
    
    %% VRAM Swapping Flow (The Hardware Dance)
    OCR -- 1. Request Swap --> VRAM_Manager
    VRAM_Manager -- 2. Unloads --> Qwen
    VRAM_Manager -- 3. Loads --> GLM_OCR
    GLM_OCR -- 4. Extracts Text --> OCR
    VRAM_Manager -- 5. Reloads --> Qwen
    
    %% RAG Flow
    WebSearch & WebScrape & FileRead & OCR -- Saves Extracted Data --> VectorStore
    Orchestrator -- Searches Knowledge --> Retriever
    Retriever -- Fetches Context --> VectorStore
    Retriever -- Assembles Context --> PromptBuilder
    
    %% LLM Execution & Output
    PromptBuilder -- Feeds Strict Prompt --> Qwen
    Qwen -- Streams Raw Tokens --> XMLParser
    XMLParser -- Separates Reasoning & Answer --> Orchestrator
    
    %% Final Output
    Orchestrator -- Streams Markdown Live --> UI
    Orchestrator -- Saves Conversation --> History
    History -- Loads Past Sessions --> UI

    %% Styling
    classDef ui fill:#1e1e20,stroke:#00d2ff,stroke-width:2px,color:#fff
    classDef core fill:#28282a,stroke:#3a7bd5,stroke-width:2px,color:#fff
    classDef agent fill:#1a365d,stroke:#00e676,stroke-width:2px,color:#fff
    classDef memory fill:#3e2723,stroke:#ffb300,stroke-width:2px,color:#fff
    classDef hardware fill:#311b92,stroke:#ff3d00,stroke-width:2px,color:#fff
    
    class UI,User ui
    class Endpoints,Orchestrator,PromptBuilder,Router core
    class WebSearch,WebScrape,FileRead,OCR,DDG,Crawl4AI,BS4 agent
    class VectorStore,Retriever,History memory
    class VRAM_Manager,Qwen,GLM_OCR,XMLParser hardware

```





<div align="center">
  <i>Built with absolute precision. Engineered for autonomy.</i><br>
  <b>Welcome to AgentForge.</b>
</div>