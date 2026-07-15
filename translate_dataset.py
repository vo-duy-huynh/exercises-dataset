import os
import json
import urllib.request
import urllib.parse
import time
import shutil
import re

DATA_DIR = "data"
EXERCISES_JSON = os.path.join(DATA_DIR, "exercises.json")
PROGRESS_JSON = os.path.join(DATA_DIR, "exercises_translated.json")
INDEX_HTML = "index.html"
README_MD = "README.md"

def translate_text(text, retries=5, delay=2):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "en",
        "tl": "vi",
        "dt": "t",
        "q": text
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                full_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                translated_segments = []
                for segment in data[0]:
                    if segment[0]:
                        translated_segments.append(segment[0])
                return "".join(translated_segments)
        except Exception as e:
            print(f"\n[Warning] Translation failed on attempt {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                sleep_time = delay * (2 ** attempt)
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print("All retries exhausted.")
                return None

def translate_batch(exercises_batch):
    all_steps = []
    sizes = []
    for ex in exercises_batch:
        steps = ex["instruction_steps"]["en"]
        all_steps.extend(steps)
        sizes.append(len(steps))
        
    joined_text = "\n".join(all_steps)
    translated_joined = translate_text(joined_text)
    
    if not translated_joined:
        return None
        
    translated_lines = [line.strip() for line in translated_joined.split("\n") if line.strip()]
    
    if len(translated_lines) != len(all_steps):
        print(f"\n[Warning] Batch translation count mismatch (expected {len(all_steps)}, got {len(translated_lines)}). Falling back...")
        return None
        
    # Unpack
    idx = 0
    results = []
    for i, ex in enumerate(exercises_batch):
        size = sizes[i]
        ex_steps_vi = translated_lines[idx : idx + size]
        idx += size
        
        new_ex = dict(ex)
        new_ex["instruction_steps"] = {
            "en": ex["instruction_steps"]["en"],
            "vi": ex_steps_vi
        }
        new_ex["instructions"] = {
            "en": ex["instructions"]["en"],
            "vi": " ".join(ex_steps_vi)
        }
        results.append(new_ex)
    return results

def translate_exercise_individually(ex):
    steps_en = ex["instruction_steps"]["en"]
    joined_text = "\n".join(steps_en)
    translated_joined = translate_text(joined_text)
    
    steps_vi = []
    if translated_joined:
        steps_vi = [line.strip() for line in translated_joined.split("\n") if line.strip()]
        
    if len(steps_vi) != len(steps_en):
        # Fallback to translating step-by-step
        steps_vi = []
        for step in steps_en:
            t_step = translate_text(step)
            steps_vi.append(t_step.strip() if t_step else "")
            time.sleep(0.2)
            
    new_ex = dict(ex)
    new_ex["instruction_steps"] = {
        "en": steps_en,
        "vi": steps_vi
    }
    new_ex["instructions"] = {
        "en": ex["instructions"]["en"],
        "vi": " ".join(steps_vi)
    }
    return new_ex

def update_index_html(exercises_data):
    if not os.path.exists(INDEX_HTML):
        print(f"File {INDEX_HTML} not found, skipping UI update.")
        return
        
    print("Updating index.html with new translations and layouts...")
    shutil.copy(INDEX_HTML, INDEX_HTML + ".bak")
    
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # 1. Replace the EXERCISES array line
    # The line is: const EXERCISES = [{...}];
    exercises_js = "  const EXERCISES = " + json.dumps(exercises_data, ensure_ascii=False) + ";"
    pattern = r"^\s*const\s+EXERCISES\s*=.*$;"
    html_content_updated, count = re.subn(pattern, exercises_js, html_content, flags=re.MULTILINE)
    if count > 0:
        print("Successfully updated EXERCISES array in index.html.")
    else:
        # Fallback if regex is too slow or doesn't match multi-line or long line
        print("Regex match failed for EXERCISES line, trying string splitting...")
        prefix = "  const EXERCISES = ["
        idx = html_content.find(prefix)
        if idx != -1:
            end_idx = html_content.find("\n", idx)
            if end_idx != -1:
                html_content_updated = html_content[:idx] + exercises_js + html_content[end_idx:]
                print("Successfully updated EXERCISES array in index.html via string splitting.")
            else:
                html_content_updated = html_content
        else:
            html_content_updated = html_content
            print("[Error] Could not find EXERCISES array start in index.html.")

    # Normalize newlines
    html_content_updated = html_content_updated.replace("\r\n", "\n")

    # 2. Replace LANG_LABELS
    lang_labels_pattern = r"const\s+LANG_LABELS\s*=\s*\{[^}]*\};"
    new_labels = "const LANG_LABELS = { en: 'English', vi: 'Tiếng Việt' };"
    html_content_updated = re.sub(lang_labels_pattern, new_labels, html_content_updated)

    # 3. Replace langs array
    langs_pattern = r"const\s+langs\s*=\s*\[\s*'en'\s*,\s*'es'[^]]*\]"
    new_langs = "const langs = ['en', 'vi']"
    html_content_updated = re.sub(langs_pattern, new_langs, html_content_updated)

    # 4. Replace MSSQL schema columns
    sql_mssql_old = """  instructions_en   NVARCHAR(MAX),
  instructions_es   NVARCHAR(MAX),
  instructions_it   NVARCHAR(MAX),
  instructions_tr   NVARCHAR(MAX),
  instructions_ru   NVARCHAR(MAX),
  instructions_zh   NVARCHAR(MAX),
  instructions_hi   NVARCHAR(MAX),
  instructions_pl   NVARCHAR(MAX),
  instructions_ko   NVARCHAR(MAX),"""
  
    sql_mssql_new = """  instructions_en   NVARCHAR(MAX),
  instructions_vi   NVARCHAR(MAX),"""
    html_content_updated = html_content_updated.replace(sql_mssql_old.replace("\r\n", "\n"), sql_mssql_new)

    # 5. Replace Other SQL schema columns
    sql_other_old = """  instructions_en   TEXT,
  instructions_es   TEXT,
  instructions_it   TEXT,
  instructions_tr   TEXT,
  instructions_ru   TEXT,
  instructions_zh   TEXT,
  instructions_hi   TEXT,
  instructions_pl   TEXT,
  instructions_ko   TEXT,"""
  
    sql_other_new = """  instructions_en   TEXT,
  instructions_vi   TEXT,"""
    html_content_updated = html_content_updated.replace(sql_other_old.replace("\r\n", "\n"), sql_other_new)

    # 6. Replace INSERT statement generation logic
    insert_old = """      const instrEn = ex.instructions && ex.instructions.en
        ? ex.instructions.en
        : (Array.isArray(ex.instruction_steps) ? ex.instruction_steps.join(' ') : (ex.instructions || ''));
      const instrEs = ex.instructions && ex.instructions.es ? ex.instructions.es : '';
      const instrIt = ex.instructions && ex.instructions.it ? ex.instructions.it : '';
      const instrTr = ex.instructions && ex.instructions.tr ? ex.instructions.tr : '';
      const instrRu = ex.instructions && ex.instructions.ru ? ex.instructions.ru : '';
      const instrZh = ex.instructions && ex.instructions.zh ? ex.instructions.zh : '';
      const instrHi = ex.instructions && ex.instructions.hi ? ex.instructions.hi : '';
      const instrPl = ex.instructions && ex.instructions.pl ? ex.instructions.pl : '';
      const instrKo = ex.instructions && ex.instructions.ko ? ex.instructions.ko : '';

      const vals = [
        escStr(ex.id, db),
        escStr(ex.name, db),
        escStr(ex.category, db),
        escStr(ex.body_part, db),
        escStr(ex.equipment, db),
        escStr(instrEn, db),
        escStr(instrEs, db),
        escStr(instrIt, db),
        escStr(instrTr, db),
        escStr(instrRu, db),
        escStr(instrZh, db),
        escStr(instrHi, db),
        escStr(instrPl, db),
        escStr(instrKo, db),
        escStr(ex.muscle_group, db),
        escStr(muscles, db),
        escStr(ex.target, db),
        escStr(ex.image, db),
        escStr(ex.gif_url, db),
        escStr(ex.created_at, db),
      ].join(', ');

      lines.push(`INSERT INTO exercises (id, name, category, body_part, equipment, instructions_en, instructions_es, instructions_it, instructions_tr, instructions_ru, instructions_zh, instructions_hi, instructions_pl, instructions_ko, muscle_group, secondary_muscles, target, image, gif_url, created_at) VALUES (${vals});`);"""

    insert_new = """      const instrEn = ex.instructions && ex.instructions.en
        ? ex.instructions.en
        : (Array.isArray(ex.instruction_steps) ? ex.instruction_steps.join(' ') : (ex.instructions || ''));
      const instrVi = ex.instructions && ex.instructions.vi ? ex.instructions.vi : '';

      const vals = [
        escStr(ex.id, db),
        escStr(ex.name, db),
        escStr(ex.category, db),
        escStr(ex.body_part, db),
        escStr(ex.equipment, db),
        escStr(instrEn, db),
        escStr(instrVi, db),
        escStr(ex.muscle_group, db),
        escStr(muscles, db),
        escStr(ex.target, db),
        escStr(ex.image, db),
        escStr(ex.gif_url, db),
        escStr(ex.created_at, db),
      ].join(', ');

      lines.push(`INSERT INTO exercises (id, name, category, body_part, equipment, instructions_en, instructions_vi, muscle_group, secondary_muscles, target, image, gif_url, created_at) VALUES (${vals});`);"""

    html_content_updated = html_content_updated.replace(insert_old.replace("\r\n", "\n"), insert_new)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html_content_updated)
    print("index.html updated successfully.")

def update_readme_md():
    if not os.path.exists(README_MD):
        return
    print("Updating README.md documentation...")
    with open(README_MD, "r", encoding="utf-8") as f:
        content = f.read()
        
    content = content.replace("9 languages (English, Spanish, Italian, Turkish, Russian, Chinese, Hindi, Polish, Korean)", "2 languages (English, Vietnamese)")
    content = content.replace("9 languages (🇬🇧 English, 🇪🇸 Spanish, 🇮🇹 Italian, 🇹🇷 Turkish, 🇷🇺 Russian, 🇨🇳 Chinese, 🇮🇳 Hindi, 🇵🇱 Polish, 🇰🇷 Korean)", "2 languages (🇬🇧 English, 🇻🇳 Vietnamese)")
    content = content.replace("English, Spanish, Italian, Turkish, Russian, Chinese, Hindi, Polish, or Korean", "English or Vietnamese")
    content = content.replace("🇬🇧 English · 🇪🇸 Spanish · 🇮🇹 Italian · 🇹🇷 Turkish · 🇷🇺 Russian · 🇨🇳 Chinese · 🇮🇳 Hindi · 🇵🇱 Polish · 🇰🇷 Korean", "🇬🇧 English · 🇻🇳 Vietnamese")
    content = content.replace("instructions_en, instructions_es, instructions_it, instructions_tr, instructions_ru, instructions_zh, instructions_hi, instructions_pl, instructions_ko", "instructions_en, instructions_vi")

    with open(README_MD, "w", encoding="utf-8") as f:
        f.write(content)
    print("README.md updated successfully.")

def main():
    if not os.path.exists(EXERCISES_JSON):
        print(f"Error: {EXERCISES_JSON} not found!")
        return

    with open(EXERCISES_JSON, "r", encoding="utf-8") as f:
        original_exercises = json.load(f)

    total_exercises = len(original_exercises)
    print(f"Loaded {total_exercises} exercises from database.")

    # Load progress if exists
    translated_map = {}
    if os.path.exists(PROGRESS_JSON):
        print("Found existing progress file. Resuming...")
        try:
            with open(PROGRESS_JSON, "r", encoding="utf-8") as f:
                progress_list = json.load(f)
                for ex in progress_list:
                    translated_map[ex["id"]] = ex
            print(f"Resumed translation: {len(translated_map)} / {total_exercises} already translated.")
        except Exception as e:
            print(f"Error reading progress file: {e}. Starting fresh.")

    # Filter out already translated exercises
    remaining_exercises = [ex for ex in original_exercises if ex["id"] not in translated_map]
    
    batch_size = 10
    batch = []
    
    last_saved_time = time.time()
    
    for i, ex in enumerate(remaining_exercises):
        batch.append(ex)
        
        # When batch size is reached or we are at the end
        if len(batch) == batch_size or i == len(remaining_exercises) - 1:
            print(f"\nTranslating batch of {len(batch)} exercises... ({len(translated_map)}/{total_exercises} done)")
            
            # Try batch translation
            batch_results = translate_batch(batch)
            
            if batch_results:
                # Batch translation succeeded
                for res_ex in batch_results:
                    translated_map[res_ex["id"]] = res_ex
            else:
                # Fallback to individual
                print("Batch translation failed or mismatched lines. Translating exercises individually...")
                for single_ex in batch:
                    print(f"  Translating exercise {single_ex['id']} ({single_ex['name']})...")
                    res_ex = translate_exercise_individually(single_ex)
                    translated_map[res_ex["id"]] = res_ex
                    time.sleep(0.3) # rate limit prevention

            # Clear batch
            batch = []
            
            # Periodically save progress to file (every 20 translated exercises or 30 seconds)
            if len(translated_map) % 20 == 0 or (time.time() - last_saved_time) > 30:
                with open(PROGRESS_JSON, "w", encoding="utf-8") as f:
                    json.dump(list(translated_map.values()), f, ensure_ascii=False, indent=2)
                last_saved_time = time.time()
                print(f"Progress saved to {PROGRESS_JSON}")
                
            time.sleep(0.2) # small rate limit prevention

    # Save final translations
    final_translated_list = []
    # Make sure we maintain the original order of exercises
    for orig_ex in original_exercises:
        ex_id = orig_ex["id"]
        if ex_id in translated_map:
            final_translated_list.append(translated_map[ex_id])
        else:
            print(f"[Warning] Exercise {ex_id} was not translated! Using original.")
            final_translated_list.append(orig_ex)

    # Backup original files and write final results
    print("\nAll translations completed! Backing up and updating database...")
    shutil.copy(EXERCISES_JSON, EXERCISES_JSON + ".bak")
    
    with open(EXERCISES_JSON, "w", encoding="utf-8") as f:
        json.dump(final_translated_list, f, ensure_ascii=False, indent=2)
    print(f"Database {EXERCISES_JSON} successfully updated!")

    # Update index.html
    update_index_html(final_translated_list)

    # Update README.md
    update_readme_md()

    # Clean up progress file
    if os.path.exists(PROGRESS_JSON):
        os.remove(PROGRESS_JSON)
        print("Cleaned up progress cache.")

    print("\nSuccessfully finished! English + Vietnamese translation generated.")

if __name__ == "__main__":
    main()
