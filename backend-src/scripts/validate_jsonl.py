#!/usr/bin/env python3
import sys
import json

def validate(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, start=1):
                line = line.rstrip('\n')
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except Exception as e:
                    print(f"ERROR line {i}: {e}")
                    snippet = line[:400]
                    print("CONTENT_SNIPPET:", snippet)
                    return 2
    except UnicodeDecodeError as ue:
        print("UnicodeDecodeError:", ue)
        return 3
    except FileNotFoundError:
        print(f"File not found: {path}")
        return 4
    print("ALL_LINES_VALID")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: validate_jsonl.py <path-to-jsonl>")
        sys.exit(1)
    path = sys.argv[1]
    rc = validate(path)
    sys.exit(rc)
