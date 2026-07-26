import json
from pathlib import Path

skills = set()
for f in ['artifacts/dataset_iteration_04/jobs.jsonl', 'artifacts/dataset_iteration_04/candidate_profiles.jsonl']:
    if Path(f).exists():
        with open(f, 'r', encoding='utf-8') as fp:
            for line in fp:
                data = json.loads(line)
                for s in data.get('skills', []):
                    skills.add(s)

with open('skills_temp.txt', 'w', encoding='utf-8') as fp:
    for s in sorted(skills):
        fp.write(s + '\n')

print(f'共收集 {len(skills)} 个技能')