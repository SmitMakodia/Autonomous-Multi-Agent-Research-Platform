TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Searches the web for the given query to find relevant information. Use this tool to answer questions requiring up-to-date internet knowledge, news, or external facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute on the web."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_scrape_url",
            "description": "Scrapes a given URL and returns the content as markdown. Use this tool specifically when the user provides a direct URL and asks you to read, summarize, or extract information from it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The explicit URL of the webpage to scrape."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ocr_image",
            "description": "Extracts text from an image or a PDF using OCR. Use this tool when the user provides an image file or a scanned PDF that needs text extraction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The local file path or URL to the image or PDF."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_local_file",
            "description": "Reads text content from a local file. Use this tool when the user explicitly references a local file (e.g., .txt, .md, .csv, .json) and needs you to analyze its contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The exact local file path to read."
                    }
                },
                "required": ["file_path"]
            }
        }
    }
]