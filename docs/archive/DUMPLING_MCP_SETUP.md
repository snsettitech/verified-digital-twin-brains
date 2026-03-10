# Dumpling AI MCP Server Setup

## Installation Complete ✅

The Dumpling AI MCP server has been installed globally via npm.

## What is MCP?

MCP (Model Context Protocol) allows AI assistants to use external tools. The Dumpling MCP server provides:

- **YouTube Transcript Extraction** - Get transcripts from any YouTube video
- **Web Scraping** - Extract content from websites
- **Document Conversion** - Convert PDFs, DOCX to text
- **Search APIs** - Google search, news, maps
- **AI Agents** - Automated task execution

## Configuration

### For Cursor IDE

Config file created at: `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "dumplingai": {
      "command": "npx",
      "args": ["-y", "mcp-server-dumplingai"],
      "env": {
        "DUMPLING_API_KEY": "sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
      }
    }
  }
}
```

### For Claude Desktop

Add to `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dumplingai": {
      "command": "npx",
      "args": ["-y", "mcp-server-dumplingai"],
      "env": {
        "DUMPLING_API_KEY": "sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
      }
    }
  }
}
```

### For Other IDEs (VS Code, etc.)

Use the Smithery installer:
```bash
npx -y @smithery/cli install @Dumpling-AI/mcp-server-dumplingai --client vscode
```

## Available Tools

### Data APIs
1. `get-youtube-transcript` - Extract YouTube transcripts
2. `search` - Google web search with result scraping
3. `get-autocomplete` - Google search suggestions
4. `search-maps` - Google Maps search
5. `search-places` - Places search
6. `search-news` - News search
7. `get-google-reviews` - Business reviews

### Web Scraping
8. `scrape` - Extract web page content
9. `crawl` - Recursive website crawling
10. `screenshot` - Capture web page screenshots
11. `extract` - AI-powered structured data extraction

### Document Conversion
12. `doc-to-text` - Convert documents to text (OCR support)
13. `convert-to-pdf` - Convert files to PDF
14. `merge-pdfs` - Combine multiple PDFs
15. `trim-video` - Extract video clips

## Testing the MCP Server

Run directly with environment variable:
```bash
set DUMPLING_API_KEY=sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR && npx -y mcp-server-dumplingai
```

Or test a specific tool:
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | set DUMPLING_API_KEY=sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR && npx -y mcp-server-dumplingai
```

## Integration with Backend

The backend already uses Dumpling AI directly via Python API calls (see `backend/modules/dumplingai_client.py`). The MCP server is for:

1. **Local development** - Use with Cursor/Claude for AI-assisted coding
2. **Testing** - Quick testing of Dumpling AI capabilities
3. **Documentation** - Reference for available endpoints

## Backend Usage (Production)

The production backend uses the Python client directly:

```python
from modules.dumplingai_client import get_youtube_transcript, scrape_webpage

# YouTube transcript
result = await get_youtube_transcript("https://youtube.com/watch?v=...")

# Web scraping
result = await scrape_webpage("https://example.com")
```

## Troubleshooting

**Error: "DUMPLING_API_KEY environment variable not set"**
- Solution: Set the environment variable before running

**Error: "Command not found"**
- Solution: Ensure npm global packages are in PATH: `npm bin -g`

**Error: "Rate limit exceeded"**
- Dumpling AI has rate limits; check your dashboard at dumplingai.com

## Resources

- Dumpling AI Docs: https://docs.dumplingai.com
- MCP Server Repo: https://github.com/dumplingai/mcp-server-dumplingai
- API Endpoints: https://www.dumplingai.com/endpoints
