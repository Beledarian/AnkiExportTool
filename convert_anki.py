
import sqlite3
import json
import os
import shutil
import re

import zstandard

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Output to the same directory
OUTPUT_DIR = BASE_DIR
IMAGES_DIR = os.path.join(OUTPUT_DIR, "Anki_Images")

# Ensure images directory exists
os.makedirs(IMAGES_DIR, exist_ok=True)

def sanitize_filename(name):
    # Keep only alphanumeric, dot, dash, underscore
    # Replace spaces with underscore
    name = name.replace(" ", "_")
    return re.sub(r'[^a-zA-Z0-9_.-]', '', name)

# 1. Handle Media
media_file = os.path.join(BASE_DIR, "media")
media_map = {} # Key -> Sanitized Filename

if os.path.exists(media_file):
    try:
        data = b""
        with open(media_file, "rb") as f:
            dctx = zstandard.ZstdDecompressor()
            with dctx.stream_reader(f) as reader:
                data = reader.read()
        
        # Robust Backward-Scan Parsing
        # 1. Find all common image extensions
        # 2. Backtrack to find length byte and start of filename
        # 3. Backtrack further to find potential Keys (Strings that match files on disk)
         
        # Make a set of existing files for quick lookup
        existing_files = set(os.listdir(BASE_DIR))
        
        # Regex for extensions
        ext_pattern = re.compile(b'\.(png|jpg|jpeg|gif|svg)', re.IGNORECASE)
        
        for m in ext_pattern.finditer(data):
            ext_end = m.end()
            # This is the potential end of a filename
            # But regex matches the *first* occurrence? No, finditer finds all.
            # We need to find the START of this string.
            # We trust the length byte?
            
            # The length byte should be at position (Start - 1).
            # We don't know Start yet.
            # But we can try reasonable lengths (e.g. 1 to 100)
            
            # Optimization: Look for the \n before the length byte?
            # Pattern: \n <Meta> \n <Len> <Filename>
            # OR: \n <Key> \n <Len> <Filename>
            
            # Let's scan backwards from ext_start to find a \n <Len> pattern?
            # Or simpler: Assume filename ends at ext_end.
            # The byte before the filename is Len.
            # So search backwards for a byte `L` such that `(CurrentPos - L_Pos - 1) == L`.
            
            found = False
            # Check backwards 5 to 255 bytes
            for dist in range(5, 255):
                pos_len_byte = ext_end - dist - 1
                if pos_len_byte < 0: break
                
                potential_len = data[pos_len_byte]
                if potential_len == dist:
                    # Candidate found!
                    fn_start = pos_len_byte + 1
                    fn_end = ext_end
                    
                    try:
                        filename = data[fn_start:fn_end].decode('utf-8')
                        
                        # Now look for KEY before pos_len_byte (which should be preceded by \n)
                        # Expectation: ... \n <Key> \n <Len> ...
                        # So data[pos_len_byte - 1] should be \n (10)
                        
                        valid_key = None
                        if data[pos_len_byte - 1] == 10:
                            # Scan backwards for next \n (Key1)
                            key1_end = pos_len_byte - 1
                            key1_start = key1_end - 1
                            
                            while key1_start >= 0 and data[key1_start] != 10 and (key1_end - key1_start) < 20:
                                key1_start -= 1
                            
                            key1_start += 1 
                            
                            # Candidate Key 1
                            try:
                                key1 = data[key1_start:key1_end].decode('ascii')
                                if key1 in existing_files:
                                    valid_key = key1
                            except:
                                pass
                                
                            # If Key1 not found, check Key2 (Grandparent)
                            # Expectation: ... \n <Key2> \n <Key1> \n <Len> ...
                            if not valid_key and data[key1_start - 1] == 10:
                                key2_end = key1_start - 1
                                key2_start = key2_end - 1
                                
                                while key2_start >= 0 and data[key2_start] != 10 and (key2_end - key2_start) < 20:
                                    key2_start -= 1
                                
                                key2_start += 1
                                
                                try:
                                    key2 = data[key2_start:key2_end].decode('ascii')
                                    if key2 in existing_files:
                                        valid_key = key2
                                except:
                                    pass

                        if valid_key:
                            # Sanitize output filename
                            clean_name = sanitize_filename(filename)
                            media_map[valid_key] = clean_name
                            
                            # We need to copy/rename valid_key -> clean_name
                            src = os.path.join(BASE_DIR, valid_key)
                            dst = os.path.join(IMAGES_DIR, clean_name)
                            if os.path.exists(src):
                                # 1. Try Zstd Decompression
                                is_zstd = False
                                try:
                                    with open(src, "rb") as f_chk:
                                        header = f_chk.read(4)
                                        if header == b'\x28\xb5\x2f\xfd':
                                            is_zstd = True
                                except: pass
                                
                                # Decompress to temp dict or directly
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
                                
                                # 2. Standardize with Pillow (Fix Windows issues)
                                try:
                                    # Need to import PIL here or at top
                                    # Assuming standard imports at top, but for safety in this snippet:
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
                                            # Just move if unknown ext
                                            shutil.move(temp_dst, dst)
                                    if os.path.exists(temp_dst):
                                        os.remove(temp_dst)
                                except ImportError:
                                    # Fallback if Pillow missing
                                    shutil.move(temp_dst, dst)
                                    print("Warning: Pillow not installed, images might be incompatible.")
                                except Exception as e:
                                    print(f"Image fix failed: {e}")
                                    if os.path.exists(temp_dst):
                                        shutil.move(temp_dst, dst)

                                print(f"Recovered: {clean_name} (from {valid_key})")
                            found = True
                    except:
                        pass
                
                if found: break
                
    except Exception as e:
        print(f"Error extracting media: {e}")

    print(f"Found {len(media_map)} media files.")
    

# 2. Extract Cards from DB
# Check for v2 database
db_path_v1 = os.path.join(BASE_DIR, "collection.anki2")
db_path_v2_compressed = os.path.join(BASE_DIR, "collection.anki21b")
db_path_real = db_path_v1

if os.path.exists(db_path_v2_compressed):
    print("Found v2 compressed database. Decompressing...")
    db_path_v2_out = os.path.join(BASE_DIR, "collection.anki2_extracted")
    if not os.path.exists(db_path_v2_out):
        try:
            with open(db_path_v2_compressed, "rb") as f_in, open(db_path_v2_out, "wb") as f_out:
                dctx = zstandard.ZstdDecompressor()
                dctx.copy_stream(f_in, f_out)
            print("Decompression successful.")
        except Exception as e:
            print(f"Failed to decompress v2 DB: {e}. Falling back to v1.")
    db_path_real = db_path_v2_out

conn = sqlite3.connect(db_path_real)
cursor = conn.cursor()

# Get all notes
cursor.execute("SELECT flds FROM notes")
notes = cursor.fetchall()
print(f"Found {len(notes)} notes.")
if len(notes) > 0:
    print(f"Sample Note (truncated): {notes[0][0][:100]}")

# Helper to look for img tags and fix paths
def fix_image_paths(text):
    # Anki uses <img src="filename.jpg">
    # We want ![image](Anki_Images/filename_clean.jpg)
    
    def repl(match):
        src = match.group(1)
        # We must assume the src in the Note is the ORIGINAL filename
        # We need to sanitize it to match common disk file
        clean_src = sanitize_filename(src)
        return f'![image](Anki_Images/{clean_src})'
    
    return re.sub(r'<img src="([^"]+)">', repl, text)


chunks = [notes[i:i + 50] for i in range(0, len(notes), 50)]

for idx, chunk in enumerate(chunks, 1):
    filename = f"Anki_Part_{idx}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    md_content = f"# Anki Export Part {idx}\n\n"
    
    for q_idx, note in enumerate(chunk, 1):
        fields = note[0].split('\x1f')
        
        # Checking how many fields we have. Usually 0=Front, 1=Back
        if len(fields) >= 2:
            front = fix_image_paths(fields[0])
            back = fix_image_paths(fields[1])
        else:
            front = fix_image_paths(fields[0])
            back = "*Keine Rückseite*"
            
        md_content += f"## Frage {q_idx}\n\n"
        md_content += f"{front}\n\n"

        md_content += f"<details><summary>🔽 Antwort anzeigen</summary>\n\n"
        md_content += f"{back}\n\n"
        md_content += f"</details>\n\n---\n\n"
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Created {filename}")

conn.close()
print("Done.")
