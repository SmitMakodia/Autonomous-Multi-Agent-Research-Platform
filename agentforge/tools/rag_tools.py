from crewai.tools import tool
from agentforge.memory.vector_store import VectorStore
import json

class RAGTools:
    
    @tool("Search Knowledge Base")
    def search_knowledge_base(query: str) -> str:
        """
        Search the internal knowledge base for relevant documents and context.
        Useful for retrieving specific information stored in the vector database.
        Returns a JSON string of relevant document chunks.
        """
        try:
            vector_store = VectorStore()
            results = vector_store.query(query, n_results=5)
            
            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    formatted_results.append({
                        "content": doc,
                        "source": metadata.get("source", "Unknown"),
                        "page": metadata.get("page", "N/A")
                    })
            
            if not formatted_results:
                return "No relevant information found in knowledge base."
                
            return json.dumps(formatted_results, indent=2)
        except Exception as e:
            return f"Error searching knowledge base: {str(e)}"
