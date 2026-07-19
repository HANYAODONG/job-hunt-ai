import json
from pathlib import Path

p = Path('artifacts/semantic_index/semantic_rerank_output.json')
out = Path('artifacts/semantic_index/semantic_rerank_output.sample.json')
if not p.exists():
    print('source not found:', p)
    raise SystemExit(1)

data = json.loads(p.read_text(encoding='utf-8'))
# take first 3 profiles
sample = data[:3]
out.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', out)
