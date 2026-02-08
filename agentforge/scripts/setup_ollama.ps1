Write-Host "Setting up Ollama for AgentForge..."

# Check if Ollama is installed
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "✅ Ollama is installed."
} else {
    Write-Error "❌ Ollama is NOT installed. Please download it from https://ollama.com/"
    exit 1
}

# Pull Models
Write-Host "Pulling Qwen 2.5 3B (LLM)..."
ollama pull qwen2.5:3b

Write-Host "Pulling Nomic Embed Text (Embeddings)..."
ollama pull nomic-embed-text

Write-Host "✅ Model setup complete."
Write-Host "Run 'ollama serve' in a separate terminal if it's not running."
