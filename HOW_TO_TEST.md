# How to Test AgentForge: A Comprehensive Guide

This document provides a step-by-step guide to testing every feature of the AgentForge platform. It explains how to verify the functionality of individual agents, the RAG pipeline, and the overall system workflow using the Streamlit dashboard.

---

## 1. 🧪 Pre-Test Verification

Before starting detailed tests, ensure the core infrastructure is ready.

### Check Models
Run the following in your terminal to ensure Ollama is responding:
```powershell
ollama list
# Output should show:
# qwen2.5:3b
# nomic-embed-text
```

### Check Logs
Open the Streamlit app (`.\venv\Scripts\streamlit run agentforge/ui/streamlit_app.py`) and navigate to the **"Live Logs"** tab. It should be empty or show a few initialization lines. Keep this tab open or check it frequently to verify agent actions.

---

## 2. 🕵️‍♂️ Testing the Agent Squad

We will test the system by giving it tasks that specifically require the unique skills of each agent.

### Scenario A: Testing the **Research Agent** (External Web Search)
**Goal**: Verify the agent can go out to the internet and find *recent* information that is NOT in its training data.

1.  **Input Topic**: *"What were the key announcements at the latest NVIDIA GTC conference in 2024 (or 2025 if applicable)?"*
2.  **Expected Behavior**:
    *   **Planner**: Should create a step to "Search the web for NVIDIA GTC announcements".
    *   **Researcher**: You should see logs like `tool_called: Web Search` or `tool_called: DuckDuckGo`. It should NOT hallucinate vague answers.
    *   **Output**: The final report should contain specific dates, product names (e.g., Blackwell GPU), and citations to news sites or blogs.
3.  **How to Verify**:
    *   Go to **"Live Logs"** tab.
    *   Look for `[Researcher Agent] ... Action: Web Search`.
    *   Check the **Final Report** for URLs in the "References" section.

### Scenario B: Testing the **Knowledge Agent** (Internal RAG)
**Goal**: Verify the agent can retrieve specific "proprietary" information that exists ONLY in your local `knowledge_base` folder.

1.  **Setup**:
    *   Ensure `agentforge/data/knowledge_base/testfile.md` exists. This file contains the fictional story of "Aurum Analytics".
    *   Run ingestion: `.\venv\Scripts\python agentforge/scripts/ingest_documents.py`.
2.  **Input Topic**: *"Summarize the history of Aurum Analytics and the 'Model Collapse Incident' of 2021."*
3.  **Expected Behavior**:
    *   **Planner**: Should delegate a step to the **Knowledge Agent**.
    *   **Knowledge Agent**: Should query the vector database. Logs will show `Action: Search Knowledge Base`.
    *   **Output**: The report must mention specific details like "Raghav Mehta", "₹18 lakhs", "Project Helios", and the "warehouse staffing" failure. **Note**: No LLM knows this information; it MUST come from your file.
4.  **How to Verify**:
    *   Go to **"Live Logs"**. Look for `[Knowledge Agent]`.
    *   Confirm the details match the content in `testfile.md`.

### Scenario C: Testing the **Critic Agent** (Synthesis & Citations)
**Goal**: Ensure the final output is not just a copy-paste but a well-structured, critical report.

1.  **Input Topic**: *"Compare the rise of Aurum Analytics (internal data) with the real-world rise of OpenAI (external data)."*
2.  **Expected Behavior**:
    *   This forces **Both** agents to work.
    *   **Critic**: Should merge the two streams.
    *   **Output**: A report with sections like "Aurum Analytics History" (sourced internally) and "OpenAI History" (sourced from web), followed by a "Comparison" section.
3.  **How to Verify**:
    *   Check if the report has a clear structure (Executive Summary, Detailed Analysis, Conclusion).
    *   Check if the "References" section lists *both* local documents (e.g., `testfile.md`) and external URLs (e.g., `wikipedia.org`).

---

## 3. 🔍 Understanding the UI & Logs

### The Dashboard Interface
*   **Left Sidebar**:
    *   **Verbose Logging**: Keep this **ON** to see the "Thinking..." process in the main chat window.
    *   **Enable Episodic Memory**: Keep **ON** to save your run to history.
*   **Main Window**:
    *   **"Research & Analysis" Tab**: Where you input queries.
    *   **"Research History" Tab**: Shows past queries. After running Scenario A, go here to see if it was saved.
    *   **"Knowledge Base" Tab**: Shows a list of files. Verify `testfile.md` is listed here.
    *   **"Live Logs" Tab**: The "Matrix" view. This is the source of truth for what is happening under the hood.

### Interpreting Logs (How to tell where the answer came from)

1.  **Web Source**:
    ```json
    {
      "agent": "Researcher Agent",
      "tool": "Web Search",
      "input": "NVIDIA GTC 2024 announcements",
      "output": "...Blackwell platform..."
    }
    ```
    *   If you see this, the info came from the **Internet**.

2.  **Internal Source**:
    ```json
    {
      "agent": "Knowledge Agent",
      "tool": "Search Knowledge Base",
      "input": "Aurum Analytics history",
      "output": "...founded in late 2016 in Pune..."
    }
    ```
    *   If you see this, the info came from your **Local Files**.

---

## 4. 🧪 Automated Evaluation

For a quick "health check" of the system without manual review, use the evaluation script.

1.  **Command**:
    ```powershell
    .\venv\Scripts\python agentforge/scripts/run_evaluation.py --runs 1
    ```
2.  **What it does**:
    *   It picks a standard topic (e.g., "Quantum Computing").
    *   Runs the full agent workflow.
    *   Scores the output based on **Structure**, **Citations**, and **Completeness**.
3.  **Success Criteria**:
    *   A score > 70/100 indicates a healthy system.

---

## 5. 🚑 Troubleshooting Common Issues

*   **Issue**: "Ollama Disconnected" in Sidebar.
    *   **Fix**: Ensure you ran `ollama serve` in a terminal window.
*   **Issue**: Agents seem stuck or "Thinking..." forever.
    *   **Fix**: Local LLMs can be slow. A complex query on an RTX 3060 might take 2-5 minutes. Check the "Live Logs" tab; if logs are updating, it's working.
*   **Issue**: Knowledge Agent says "No relevant information found".
    *   **Fix**: Did you run `ingest_documents.py`? Check the "Knowledge Base" tab to ensure files are detected.
