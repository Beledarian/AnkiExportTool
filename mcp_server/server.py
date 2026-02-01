import asyncio
import os
import shutil
import zipfile
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource
from mcp.server.stdio import stdio_server
from .anki_logic import convert_deck

app = Server("anki-converter")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="convert_anki_deck",
            description="Converts an Anki .apkg file to Markdown with images.",
            inputSchema={
                "type": "object",
                "properties": {
                    "apkg_path": {
                        "type": "string",
                        "description": "Absolute path to the .apkg file"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Optional output directory. Default: next to apkg."
                    }
                },
                "required": ["apkg_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent | EmbeddedResource]:
    if name == "convert_anki_deck":
        apkg_path = arguments["apkg_path"]
        output_dir = arguments.get("output_dir")

        if not os.path.exists(apkg_path):
            return [TextContent(type="text", text=f"Error: File not found at {apkg_path}")]

        # Determine output directory
        if output_dir is None:
            base_name = os.path.splitext(os.path.basename(apkg_path))[0]
            output_dir = os.path.join(os.path.dirname(apkg_path), f"{base_name}_extracted")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract .apkg (it is a zip)
        extract_temp = os.path.join(output_dir, "temp_extract")
        os.makedirs(extract_temp, exist_ok=True)
        
        try:
            with zipfile.ZipFile(apkg_path, 'r') as zip_ref:
                zip_ref.extractall(extract_temp)
        except zipfile.BadZipFile:
            return [TextContent(type="text", text="Error: Invalid .apkg file (not a valid zip).")]

        # Run conversion
        results = convert_deck(extract_temp, output_dir)
        
        # Cleanup temp
        try:
            shutil.rmtree(extract_temp)
        except:
            pass
        
        result_text = "\n".join(results) + f"\n\nOutput saved to: {output_dir}"
        return [TextContent(type="text", text=result_text)]

    raise ValueError(f"Tool {name} not found")

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
