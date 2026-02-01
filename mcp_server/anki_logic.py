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
        data = b""
        with open(media_file, "rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                data = reader.read()
        
        existing_files = set(os.listdir(base_dir))
        ext_pattern = re.compile(b'\.(png|jpg|jpeg|gif|svg)', re.IGNORECASE)
        
        for m in ext_pattern.finditer(data):
            ext_end = m.end()
            found = False
            for dist in range(5, 255):
                pos_len_byte = ext_end - dist - 1
                if pos_len_byte < 0: break
                
                potential_len = data[pos_len_byte]
                if potential_len == dist:
                    fn_start = pos_len_byte + 1
                    fn_end = ext_end
                    
                    try:
                        filename = data[fn_start:fn_end].decode('utf-8')
                        valid_key = None
                        
                        # Check immediate key
                        if data[pos_len_byte - 1] == 10:
                            key_end = pos_len_byte - 1
                            key_start = key_end - 1
                            while key_start >= 0 and data[key_start] != 10 and (key_end - key_start) < 20:
                                key_start -= 1
                            key_start += 1 
                            try:
                                key1 = data[key_start:key_end].decode('ascii')
                                if key1 in existing_files:
                                    valid_key = key1
                            except: pass
                            
                            # Check grandparent key
                            if not valid_key and data[key_start - 1] == 10:
                                key2_end = key_start - 1
                                key2_start = key2_end - 1
                                while key2_start >= 0 and data[key2_start] != 10 and (key2_end - key2_start) < 20:
                                    key2_start -= 1
                                key2_start += 1
                                try:
                                    key2 = data[key2_start:key2_end].decode('ascii')
                                    if key2 in existing_files:
                                        valid_key = key2
                                except: pass

                        if valid_key:
                            clean_name = sanitize_filename(filename)
                            media_map[valid_key] = clean_name
                            
                            src = os.path.join(base_dir, valid_key)
                            dst = os.path.join(images_dir, clean_name)
                            if os.path.exists(src):
                                # 1. Try Zstd Decompression
                                is_zstd = False
                                try:
                                    with open(src, "rb") as f_chk:
                                        header = f_chk.read(4)
                                        if header == b'\x28\xb5\x2f\xfd':
                                            is_zstd = True
                                except: pass
                                
                                temp_dst = dst + ".tmp"
                                if is_zstd:
                                    try:
                                        with open(src, "rb") as f_in, open(temp_dst, "wb") as f_out:
                                            dctx = zstandard.ZstdDecompressor()
                                            dctx.copy_stream(f_in, f_out)
                                    except:
                                        shutil.copy2(src, temp_dst)
                                else:
                                    shutil.copy2(src, temp_dst)
                                
                                # 2. Standardize with Pillow
                                try:
                                    from PIL import Image
                                    with Image.open(temp_dst) as img:
                                        img.load()
                                        fmt = None
                                        if clean_name.lower().endswith((".png")): fmt = "PNG"
                                        elif clean_name.lower().endswith((".jpg", ".jpeg")): fmt = "JPEG"
                                        
                                        if fmt:
                                            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                                                img = img.convert("RGB")
                                            img.save(dst, format=fmt)
                                        else:
                                            shutil.move(temp_dst, dst)
                                    if os.path.exists(temp_dst):
                                        os.remove(temp_dst)
                                except:
                                    if os.path.exists(temp_dst):
                                        shutil.move(temp_dst, dst)
                                
                            found = True
                    except: pass
                if found: break
    except Exception as e:
        return media_map, f"Error extracting media: {str(e)}"

    return media_map, f"Found {len(media_map)} media files."

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
