# Anki to Markdown Converter 🔄

A robust Python tool to extract **Anki decks (.apkg)** into clean **Markdown files**, preserving images and formatting. This tool generates ready-to-use study notes compatible with Obsidian, VSCode, and other Markdown editors.

## Features

- 📦 **Deep Extraction**: Handles Anki v2.1+ compressed databases (zstd) and legacy formats.
- 📦 **Deep Media Parsing**: Uses a prioritized parser that supports standard JSON, ZSTD-compressed JSON, and **ZSTD-compressed Protobuf** media maps, ensuring correct image allocation even for complex Anki exports.
- 📝 **Smart Segmentation**: Splits large decks into manageable Markdown chunks (default: 50 cards per file).
- 🔗 **Format Conversion**: Automatically converts Anki's `<img src="...">` tags to standard Markdown `![alt](path)` blocks.
- 🤖 **MCP Server**: Includes a Model Context Protocol (MCP) server integration for use with AI assistants and IDEs.

## Installation

1. Clone this repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Required libraries: `mcp`, `zstandard`, `pillow`)*

## Usage

### Option A: Standalone Script

Use the provided scripts to convert a deck directly in your terminal.

1. **Prepare your file:** Rename your `.apkg` file to `.zip` and extract it into a folder.
2. **Run the script:**
   ```bash
   python convert_anki.py
   ```
   *Ensure the script is in the same directory as the extracted Anki files (`collection.anki2`, `media`, etc.).*

3. **Output:** 
   - Markdown files: `Anki_Part_1.md`, `Anki_Part_2.md`, ...
   - Images: `Anki_Images/` folder.

### Option B: MCP Server

Integrate this tool directly into your AI workflow using the Model Context Protocol.

**Configuration:**

Add the following to your MCP settings file (e.g., inside Claude Desktop or your IDE configuration):

```json
{
  "mcpServers": {
    "anki-converter": {
      "command": "python",
      "args": ["/absolute/path/to/AnkiExportTool/mcp_server/server.py"]
    }
  }
}
```

**Available Tools:**

- `convert_anki_deck`
  - **Arguments:**
    - `input_dir`: Path to the directory containing the extracted Anki files.
    - `output_dir`: Path where the Markdown files should be saved.
    - `chunk_size` (optional): Number of cards per Markdown file (default: 50).

## Troubleshooting

- **Missing Images:** The tool uses a heuristic scanner to find images in the binary `media` file. If images are still missing, ensure your `.apkg` was exported with media included.
- **Windows Filenames:** The tool automatically renames files with illegal characters (like `?`, `"`, `*`) and updates the Markdown links to match.
