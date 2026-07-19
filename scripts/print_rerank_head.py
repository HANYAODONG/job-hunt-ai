import json
from pathlib import Path

p = Path("e:/job-hunt-ai-main/artifacts/semantic_index/semantic_rerank_output.json")
if not p.exists():
    print(f"File not found: {p}")
    raise SystemExit(1)

text = p.read_text(encoding="utf-8")
# find start of array
start = text.find('[')
if start == -1:
    print('No JSON array found')
    raise SystemExit(1)

decoder = json.JSONDecoder()
idx = start + 1
n = len(text)
results = []
count = 0
while idx < n and count < 3:
    # skip whitespace and commas
    while idx < n and (text[idx].isspace() or text[idx] == ','):
        idx += 1
    if idx >= n or text[idx] == ']':
        break
    try:
        obj, end = decoder.raw_decode(text, idx)
    except json.JSONDecodeError as e:
        snippet = text[idx:idx+200].replace('\n','\\n')
        print('JSONDecodeError near:', snippet)
        raise
    results.append(obj)
    count += 1
    idx = end

print(json.dumps(results, ensure_ascii=False, indent=2))
