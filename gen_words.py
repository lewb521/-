#!/usr/bin/env python3
"""Generate 8000-word vocabulary with Chinese translations for 不白背"""
import json, time, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Read wordlist
with open('/workspace/wordlist.txt', 'r') as f:
    all_words = [line.strip().lower() for line in f if line.strip() and len(line.strip()) >= 2]

# Remove duplicates while preserving order
seen = set()
unique_words = []
for w in all_words:
    if w not in seen:
        seen.add(w)
        unique_words.append(w)

print(f"Total unique words: {len(unique_words)}", file=sys.stderr)

# Take first 8000 words
words_8000 = unique_words[:8000]
print(f"Selected {len(words_8000)} words", file=sys.stderr)

# Stage distributions
stage_sizes = [
    ('中考', 1000),
    ('高考', 1500),
    ('四级', 2000),
    ('六级', 2000),
    ('考研', 1500)
]

stages = {}
idx = 0
for stage_name, size in stage_sizes:
    stages[stage_name] = words_8000[idx:idx+size]
    idx += size

print(f"Stage counts: { {k: len(v) for k, v in stages.items()} }", file=sys.stderr)

# Check for existing translations cache
cache_file = '/workspace/trans_cache.json'
cache = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r', encoding='utf-8') as f:
        cache = json.load(f)
    print(f"Loaded {len(cache)} cached translations", file=sys.stderr)

# Collect all words that need translation
all_stage_words = []
for stage_name, word_list in stages.items():
    all_stage_words.extend(word_list)

words_to_translate = [w for w in all_stage_words if w not in cache]
print(f"Words to translate: {len(words_to_translate)}", file=sys.stderr)

# Translation function
def translate_word(word):
    url = 'https://api.mymemory.translated.net/get'
    try:
        r = requests.get(url, params={'q': word, 'langpair': 'en-GB|zh-CN'}, timeout=10)
        data = r.json()
        if data['responseStatus'] == 200:
            trans = data['responseData']['translatedText']
            # Clean up translation: remove common MT artifacts
            trans = trans.strip()
            # Remove leading "n.", "adj.", "v." etc.
            import re
            trans = re.sub(r'^[a-z]+\.\s*', '', trans)
            return word, trans
    except Exception as e:
        print(f"Error translating {word}: {e}", file=sys.stderr)
    return word, ''

# Translate in parallel batches
BATCH_SIZE = 50
total = len(words_to_translate)
translated = 0

for i in range(0, total, BATCH_SIZE):
    batch = words_to_translate[i:i+BATCH_SIZE]
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(translate_word, w): w for w in batch}
        for future in as_completed(futures):
            word, trans = future.result()
            if trans:
                cache[word] = trans
                translated += 1
    
    # Save cache periodically
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    
    progress = min(i + BATCH_SIZE, total)
    print(f"Progress: {progress}/{total} ({translated} translated)", file=sys.stderr)
    time.sleep(0.5)  # Small delay between batches

# Build final output
output = {
    'stages': stages,
    'translations': {}
}

# Build translations dict (only for words in our stages)
for stage_name, word_list in stages.items():
    for word in word_list:
        if word in cache and cache[word]:
            output['translations'][word] = cache[word]

print(f"Final translations: {len(output['translations'])}", file=sys.stderr)

# Write to JSON
with open('/workspace/words-data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("DONE - Saved to words-data.json", file=sys.stderr)