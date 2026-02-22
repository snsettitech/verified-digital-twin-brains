# Dumpling AI MCP Server - VS Code Setup

## Installation Status: ✅ COMPLETE

The Dumpling AI MCP server has been installed and tested successfully in VS Code.

---

## What is MCP?

MCP (Model Context Protocol) is a standard for AI assistants to connect with external tools and data sources. The Dumpling AI MCP server provides 27 tools for:

- **YouTube** - Transcript extraction
- **Web Scraping** - Page content extraction, crawling, screenshots
- **Search** - Google search, news, maps, places, reviews
- **Documents** - PDF conversion, OCR, merging
- **AI** - Image generation, code execution, knowledge bases

---

## Configuration

### VS Code MCP Config Location
```
%APPDATA%\Code\User\mcp.json
```

### Current Configuration
```json
{
    "servers": {
        "dumplingai": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-server-dumplingai@latest"],
            "env": {
                "DUMPLING_API_KEY": "sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
            },
            "version": "1.0.0"
        }
    }
}
```

---

## Available Tools (27 Total)

### YouTube & Video
| Tool | Description |
|------|-------------|
| `get-youtube-transcript` | Extract transcripts from YouTube videos |
| `trim-video` | Trim videos to specific duration |
| `extract-video` | Extract data from videos using AI |

### Web Scraping
| Tool | Description |
|------|-------------|
| `scrape` | Extract content from any web page |
| `crawl` | Recursively crawl websites |
| `screenshot` | Capture webpage screenshots |
| `extract` | AI-powered structured data extraction |

### Search
| Tool | Description |
|------|-------------|
| `search` | Google web search |
| `search-news` | News article search |
| `search-maps` | Google Maps search |
| `search-places` | Places & business search |
| `get-google-reviews` | Business reviews |
| `get-autocomplete` | Search suggestions |

### Documents
| Tool | Description |
|------|-------------|
| `doc-to-text` | Convert documents to text (with OCR) |
| `convert-to-pdf` | Convert files to PDF |
| `merge-pdfs` | Combine multiple PDFs |
| `extract-document` | AI extraction from documents |
| `read-pdf-metadata` | Extract PDF metadata |
| `write-pdf-metadata` | Write PDF metadata |

### AI & Code
| Tool | Description |
|------|-------------|
| `generate-agent-completion` | AI text completions |
| `generate-ai-image` | AI image generation |
| `run-js-code` | Execute JavaScript in sandbox |
| `run-python-code` | Execute Python in sandbox |

### Knowledge Base
| Tool | Description |
|------|-------------|
| `search-knowledge-base` | Search knowledge base |
| `add-to-knowledge-base` | Add resources to knowledge base |

### Media
| Tool | Description |
|------|-------------|
| `extract-image` | Extract data from images |
| `extract-audio` | Extract data from audio |

---

## Test Results

```
======================================================================
Testing Dumpling AI MCP Server
======================================================================

1. Listing available tools...
[OK] Found 27 tools

2. Testing YouTube transcript extraction...
   Video: https://www.youtube.com/watch?v=6iilze3aDkU
[OK] Successfully extracted transcript (42296 characters)

3. Testing web scraping...
   URL: https://example.com
[OK] Successfully scraped webpage (337 characters)

======================================================================
All tests passed! [OK]
======================================================================
```

---

## Usage in VS Code

### Method 1: Via Command Palette
1. Press `Ctrl+Shift+P` (Windows) or `Cmd+Shift+P` (Mac)
2. Type "MCP" to see available MCP commands
3. Select a tool and provide parameters

### Method 2: Via AI Assistant
When using GitHub Copilot or other AI assistants in VS Code:

```
"Get the transcript from this YouTube video: https://youtube.com/watch?v=..."
```

```
"Scrape the content from https://example.com"
```

```
"Search Google for 'latest AI news'"
```

### Method 3: Direct MCP Calls
Create a task in VS Code:
```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Get YouTube Transcript",
            "type": "shell",
            "command": "echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"get-youtube-transcript\",\"arguments\":{\"videoUrl\":\"https://youtube.com/watch?v=...\"}}}' | npx -y mcp-server-dumplingai@latest"
        }
    ]
}
```

---

## Testing Commands

### List all tools
```powershell
$env:DUMPLING_API_KEY="sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | npx -y mcp-server-dumplingai@latest
```

### Get YouTube transcript
```powershell
$env:DUMPLING_API_KEY="sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get-youtube-transcript","arguments":{"videoUrl":"https://youtube.com/watch?v=6iilze3aDkU","includeTimestamps":false}}}' | npx -y mcp-server-dumplingai@latest
```

### Scrape webpage
```powershell
$env:DUMPLING_API_KEY="sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"scrape","arguments":{"url":"https://example.com","format":"markdown"}}}' | npx -y mcp-server-dumplingai@latest
```

---

## Troubleshooting

### MCP Server not appearing in VS Code
1. Restart VS Code
2. Check MCP panel: `Ctrl+Shift+P` → "MCP: List Servers"
3. Verify mcp.json path: `%APPDATA%\Code\User\mcp.json`

### API Key errors
```
Error: DUMPLING_API_KEY environment variable not set
```
- Solution: Ensure API key is in the mcp.json env section

### Connection errors
- Check internet connection
- Verify Dumpling AI API key is valid
- Check Dumpling AI dashboard for quota/credits

### Tool call failures
- Check video URL is valid and public (for YouTube)
- Ensure website allows scraping (for web tools)
- Verify document URL is accessible (for document tools)

---

## Backend Integration

The backend uses Dumpling AI directly via Python (not MCP):

```python
from modules.dumplingai_client import get_youtube_transcript, scrape_webpage

# YouTube transcript
result = await get_youtube_transcript("https://youtube.com/watch?v=...")

# Web scraping  
result = await scrape_webpage("https://example.com")
```

The MCP server is for:
1. **Development** - Quick testing in VS Code
2. **AI-assisted coding** - GitHub Copilot integration
3. **Exploration** - Discovering available tools

---

## Resources

- Dumpling AI Docs: https://docs.dumplingai.com
- MCP Server Repo: https://github.com/dumplingai/mcp-server-dumplingai
- MCP Spec: https://modelcontextprotocol.io
