import os
import sqlite3
import json
import shutil
import re
import zstandard
from urllib.parse import quote

def sanitize_filename(name):
    """Sanitizes filenames to be safe for disk/markdown."""
    name = name.replace(" ", "_")
    return re.sub(r'[^a-zA-Z0-9_.-]', '', name)

def fix_image_paths(text):
    """Converts Anki <img src> to Markdown ![image] with sanitized paths."""
    def repl(match):
        src = match.group(1)
        clean_src = sanitize_filename(src)
        return f'![image](Anki_Images/{clean_src})'
    return re.sub(r'<img src="([^"]+)">', repl, text)

def extract_media(base_dir, images_dir):
    """Extracts media from the Anki 'media' file."""
    media_file = os.path.join(base_dir, "media")
    media_map = {} # Key -> Sanitized Filename

    if not os.path.exists(media_file):
        return media_map, "No media file found."

    try:
        data = None
        # Try pure json load first (standard v2)
        try:
            with open(media_file, "r", encoding="utf-8") as f:
                media_map = json.load(f)
            # Check if keys exist
            return media_map, f"Loaded {len(media_map)} from JSON."
        except: pass

        # Binary/Compressed handling
        with open(media_file, "rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                data = reader.read()
        
        # Manual scan for \n KEY \n LEN FILENAME
        i = 0
        n = len(data)
        
        existing_files = set(os.listdir(base_dir))
        
        # Shift-Map for Windows/US keyboards (heuristic)
        # ! -> 1, " -> 2, etc.
        shift_map = {
            '!': '1', '"': '2', '§': '3', '$': '4', '%': '5', '&': '6', '/': '7', '(': '8', ')': '9', '=': '0',
            '+': '*',  # + might map to *? Or vice/versa. 
            # In Anki sometimes keys are just indices.
            # If we see symbol keys, we check for digit files.
        }
        
        while i < n - 5:
            if data[i] == 10: # \n
                j = i + 1
                while j < n and j < i + 50 and data[j] != 10:
                    j += 1
                
                if j < n and data[j] == 10:
                    key_bytes = data[i+1:j]
                    try:
                        key = key_bytes.decode('utf-8')
                        
                        # LEN
                        if j + 1 < n:
                            length = data[j+1]
                            start_fn = j + 2
                            end_fn = start_fn + length
                            
                            if end_fn <= n:
                                fn_bytes = data[start_fn:end_fn]
                                filename = fn_bytes.decode('utf-8')
                                
                                if "." in filename:
                                    clean_name = sanitize_filename(filename)
                                    media_map[key] = clean_name
                                    
                                    # Copy logic
                                    # Try Key
                                    src_key = key
                                    if src_key not in existing_files:
                                        # Try Fallback
                                        if key in shift_map and shift_map[key] in existing_files:
                                            src_key = shift_map[key]
                                        # Try ASCII code? e.g. " -> 34
                                        elif len(key) == 1 and str(ord(key[0])) in existing_files:
                                            src_key = str(ord(key[0]))
                                    
                                    src = os.path.join(base_dir, src_key)
                                    dst = os.path.join(images_dir, clean_name)
                                    
                                    if os.path.exists(src):
                                        # Decompress/Fix
                                        is_zstd = False
                                        try:
                                            with open(src, "rb") as f_chk:
                                                if f_chk.read(4) == b'\x28\xb5\x2f\xfd': is_zstd = True
                                        except: pass
                                        
                                        temp_dst = dst + ".tmp"
                                        if is_zstd:
                                            try:
                                                with open(src, "rb") as f_in, open(temp_dst, "wb") as f_out:
                                                    zstandard.ZstdDecompressor().copy_stream(f_in, f_out)
                                            except: shutil.copy2(src, temp_dst)
                                        else:
                                            shutil.copy2(src, temp_dst)
                                        
                                        # Pillow
                                        valid_img = False
                                        try:
                                            from PIL import Image
                                            with Image.open(temp_dst) as img:
                                                img.load()
                                                valid_img = True
                                                fmt = None
                                                if clean_name.lower().endswith(".png"): fmt = "PNG"
                                                elif clean_name.lower().endswith((".jpg", ".jpeg")): fmt = "JPEG"
                                                if fmt:
                                                    if fmt == "JPEG" and img.mode in ("RGBA", "P"): img = img.convert("RGB")
                                                    img.save(dst, format=fmt)
                                                else: shutil.move(temp_dst, dst)
                                                if os.path.exists(temp_dst): os.remove(temp_dst)
                                        except:
                                            if os.path.exists(temp_dst): shutil.move(temp_dst, dst)
                                            
                                        # found = True # This variable was not used, removed.
                    except: pass
            i += 1
            
        return media_map, f"Extracted {len(media_map)} images using manual scan."
    except Exception as e:
        return media_map, f"Error extracting media: {str(e)}"

def convert_deck(input_dir, output_dir, chunk_size=50):
    """Main function to convert Anki deck in input_dir to MD in output_dir."""
    
    images_dir = os.path.join(output_dir, "Anki_Images")
    os.makedirs(images_dir, exist_ok=True)
    
    log = []

    # 1. Extract Media
    media_map, msg = extract_media(input_dir, images_dir)
    log.append(msg)

    # 2. Extract database
    db_path_v1 = os.path.join(input_dir, "collection.anki2")
    db_path_v2_compressed = os.path.join(input_dir, "collection.anki21b")
    db_path_real = db_path_v1

    if os.path.exists(db_path_v2_compressed):
        db_path_v2_out = os.path.join(input_dir, "collection.anki2_extracted")
        if not os.path.exists(db_path_v2_out):
            try:
                with open(db_path_v2_compressed, "rb") as f_in, open(db_path_v2_out, "wb") as f_out:
                    dctx = zstandard.ZstdDecompressor()
                    dctx.copy_stream(f_in, f_out)
                log.append("Decompressed v2 database.")
            except Exception as e:
                log.append(f"Failed to decompress v2 DB: {e}")
        db_path_real = db_path_v2_out
    
    if not os.path.exists(db_path_real):
        return ["Error: No collection.anki2 or collection.anki21b found."]

    try:
        conn = sqlite3.connect(db_path_real)
        cursor = conn.cursor()
        cursor.execute("SELECT flds FROM notes")
        notes = cursor.fetchall()
        log.append(f"Found {len(notes)} notes.")
        
        chunks = [notes[i:i + chunk_size] for i in range(0, len(notes), chunk_size)]
        created_files = []

        for idx, chunk in enumerate(chunks, 1):
            filename = f"Anki_Part_{idx}.md"
            filepath = os.path.join(output_dir, filename)
            
            md_content = f"# Anki Export Part {idx}\n\n"
            
            for q_idx, note in enumerate(chunk, 1):
                fields = note[0].split('\x1f')
                if len(fields) >= 2:
                    front = fix_image_paths(fields[0])
                    back = fix_image_paths(fields[1])
                else:
                    front = fix_image_paths(fields[0])
                    back = "*No Back*"
                    
                md_content += f"## Question {q_idx}\n\n"
                md_content += f"{front}\n\n"
                md_content += f"<details><summary>🔽 Show Answer</summary>\n\n"
                md_content += f"{back}\n\n"
                md_content += f"</details>\n\n---\n\n"
                
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            created_files.append(filename)
            
        conn.close()
        log.append(f"Created {len(created_files)} MD files.")
        return log
    except Exception as e:
        return log + [f"Database error: {str(e)}"]
