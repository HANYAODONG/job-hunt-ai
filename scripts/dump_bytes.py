from pathlib import Path
p = Path(r"e:/job-hunt-ai-main/backend-src/scripts/generate_semantic_artifacts.py")
b = p.read_bytes()
print('len', len(b))
print('head_hex', b[:128].hex())
print('head_bytes', list(b[:64]))
for i, byte in enumerate(b[:64]):
    print(i, hex(byte))
