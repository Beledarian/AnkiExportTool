# Anki to Markdown Converter 🔄

A robust Python script to extract **Anki decks (.apkg)** into clean **Markdown files**, preserving images and formatting.

## Features
- 📦 **Unzips .apkg** files (handling Anki v2.1+ compressed databases).
- 🖼️ **Extracts Images**: Parses the binary `media` map to recover images and renames them to their original filenames.
- 📝 **Markdown Output**: Generates numbered `.md` files (e.g., `Anki_1.md`), splitting large decks into chunks of 50 questions.
- 🔗 **Image Fixing**: Automatically converts Anki's `<img src="...">` tags to Markdown `![image](path)` syntax for compatibility with Obsidian/VSCode.
- 🛠️ **Robust**: Handles tricky binary formats and zstd compression.

## Usage

1. Place your `.apkg` file (rename it to `.zip` and extract it) into a folder.
2. Place this script inside that folder.
3. Run:
   ```bash
   python convert_anki.py
   ```
4. Find your questions in `Anki_1.md` and images in `Anki_Images/`.

## Prerequisites
- Python 3.x
- `pip install zstandard`

---
*Created by your AI Assistant.* 🤖
