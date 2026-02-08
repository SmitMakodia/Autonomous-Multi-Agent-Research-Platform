import streamlit as st
import sys
import os
import asyncio
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OPENAI_API_KEY"] = "NA"
os.environ["EMBEDDINGS_OLLAMA_MODEL_NAME"] = "nomic-embed-text"

from agentforge.workflows.research_workflow import ResearchWorkflow
from agentforge.memory.episodic_memory import EpisodicMemory
from agentforge.monitoring.logger import configure_logger

configure_logger()

st.set_page_config(
    page_title="AgentForge: Autonomous Research",
    layout="wide"
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "research_result" not in st.session_state:
    st.session_state.research_result = None
if "research_history" not in st.session_state:
    st.session_state.research_history = []
if "logs" not in st.session_state:
    st.session_state.logs = ""

with st.sidebar:
    st.title("AgentForge")
    st.markdown("---")
    st.header("System Status")
    
    try:
        st.success("Ollama Connected (Local)")
        st.caption("Model: qwen2.5:3b")
        st.caption("Embeddings: nomic-embed-text")
    except:
        st.error("Ollama Disconnected")
    
    st.markdown("---")
    st.header("Settings")
    verbose_mode = st.toggle("Verbose Logging", value=True)
    memory_enabled = st.toggle("Enable Episodic Memory", value=True)
    reset_memory = st.toggle("Reset Agent Memory", value=False, help="Clears all long-term memory and vector stores before starting. Use this if agents are confusing past topics.")
    
    st.markdown("---")
    st.markdown("### About")
    st.info(
        "AgentForge is an autonomous multi-agent research platform "
        "running entirely locally on your RTX 3060."
    )

st.title("Autonomous Multi-Agent Research Platform")
st.markdown("#### Orchestrating AI Agents for Deep Research")

tab_research, tab_history, tab_knowledge, tab_logs = st.tabs(["Research & Analysis", "Research History", "Knowledge Base", "Live Logs"])

with tab_research:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        topic = st.text_area("Enter Research Goal / Topic:", height=100, placeholder="e.g., Analyze the impact of transformer architectures on NLP...")
        
    with col2:
        st.write("") 
        st.write("")
        use_kb = st.toggle("Use Internal Knowledge Base", value=True, help="If enabled, agents will search uploaded documents in addition to the web.")
        start_btn = st.button("Start Research Mission", type="primary")

    if start_btn and topic:
        st.session_state.research_result = None
        
        st.markdown("---")
        st.subheader("Live Agent Execution")
        
        status_container = st.container()
        
        with status_container:
            with st.status("Initializing Agents...", expanded=True) as status:
                st.write("Planner Agent: Decomposing task...")
                st.write("Researcher Agent: Scanning external sources...")
                if use_kb:
                    st.write("Knowledge Agent: Querying internal vector DB...")
                st.write("Critic Agent: Synthesizing and reviewing...")
                
                try:
                    workflow = ResearchWorkflow()
                    result = workflow.run(topic, use_knowledge_base=use_kb, reset_memory=reset_memory)
                    
                    st.session_state.research_result = str(result)
                    
                    if memory_enabled:
                        memory = EpisodicMemory()
                        memory.add_task(topic, str(result))
                        st.session_state.research_history.append({"topic": topic, "result": str(result)})
                    
                    status.update(label="Research Mission Complete!", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"Error during execution: {str(e)}")
                    status.update(label="Execution Failed", state="error")
    
    if st.session_state.research_result:
        st.markdown("---")
        st.subheader("Final Research Report")
        st.markdown(st.session_state.research_result)
        
        st.download_button(
            label="Download Report",
            data=st.session_state.research_result,
            file_name="research_report.md",
            mime="text/markdown"
        )

with tab_history:
    st.subheader("Past Research Missions")
    memory = EpisodicMemory()
    if st.button("Refresh History"):
        try:
            tasks = memory.get_similar_tasks("%", limit=10)
            st.session_state.research_history = tasks
        except Exception as e:
            st.warning("Could not retrieve history.")

    if not st.session_state.research_history:
        try:
            tasks = memory.get_similar_tasks("%", limit=10)
            st.session_state.research_history = tasks
        except:
             pass

    if not st.session_state.research_history:
        st.info("No research history found.")
    else:
        for task in reversed(st.session_state.research_history):
            timestamp = task.get('timestamp', 'Unknown Date')
            topic_str = task.get('topic', 'Unknown Topic')
            result_str = task.get('result', '')
            
            with st.expander(f"{timestamp} - {topic_str[:50]}..."):
                st.markdown(result_str)

with tab_knowledge:
    st.subheader("Internal Knowledge Base")
    st.markdown("Documents ingested into ChromaDB:")
    
    kb_dir = os.path.join(os.path.dirname(__file__), "../data/knowledge_base")
    if os.path.exists(kb_dir):
        files = os.listdir(kb_dir)
        if files:
            for f in files:
                st.text(f"{f}")
        else:
            st.info("No documents found in `agentforge/data/knowledge_base`.")
    else:
        st.error("Knowledge base directory not found.")
        
    st.markdown("---")
    st.info("To add documents, place PDF/MD/TXT files in the folder and run the ingestion script.")

with tab_logs:
    st.subheader("System Logs")
    st.info("Logs allow you to verify which agent is acting and what tools they are using.")
    
    if st.button("Refresh Logs"):
        log_file = "agentforge.log"
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                st.session_state.logs = f.read()
    
    log_file = "agentforge.log"
    if not st.session_state.logs and os.path.exists(log_file):
         with open(log_file, "r") as f:
            st.session_state.logs = f.read()

    if st.session_state.logs:
        st.code(st.session_state.logs, language="json")
    else:
        st.warning("No logs found yet. Start a research mission to generate logs.")
