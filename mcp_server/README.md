# Anki Converter MCP Server 🔄

An [MCP](https://modelcontextprotocol.io) server that provides tools to convert Anki `.apkg` decks into clean Markdown files with proper image handling.

## Features

- **Tool:** `convert_anki_deck(apkg_path, output_dir)`
  - Converts an Anki file to a set of Markdown files.
  - Automatically extracts and decompresses images (zstd support).
  - Sanitizes filenames and fixes image links (`![img](...)`).

## Installation

1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage with Claude/Gemini App

Add this configuration to your MCP settings file:

```json
{
  "mcpServers": {
    "anki-converter": {
      "command": "python",
      "args": ["/path/to/anki-converter/server.py"]
    }
  }
}
```

## Structure

- `server.py`: The entry point for the MCP server.
- `anki_logic.py`: Core logic for parsing Anki databases and media.
