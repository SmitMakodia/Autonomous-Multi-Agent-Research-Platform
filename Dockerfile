# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y 
    build-essential 
    curl 
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY agentforge/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agentforge/ agentforge/

# Expose ports for Streamlit and FastAPI
EXPOSE 8501 8000

# Default command (can be overridden in docker-compose)
CMD ["streamlit", "run", "agentforge/ui/streamlit_app.py"]
