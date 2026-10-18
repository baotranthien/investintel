"""Audit all frontend and backend user-facing source files for Unicode / Mojibake issues."""
import os
import re
from pathlib import Path

# Mojibake patterns resulting from UTF-8 decoded as CP1252 / ISO-8859-1
# Common sequences:
# - Ã followed by another byte (e.g. Ã¡, Ã , Ã¢, Ã£, Ã¨, Ã©, Ãª, Ã¬, Ã­, Ã², Ã³, Ã´, Ãµ, Ã¹, Ãº, Ã½, Ã´)
# - áº or á» followed by another byte
# - Ä‘ or Ä followed by control/special
# - Æ° or Æ¡
# - â followed by 80-bf
# - Â· or Â followed by space/control
# - Replacement character \ufffd

MOJI_PATTERN = re.compile(
    r'('
    r'Ã[¡-¿\x80-\xbf\s]'
    r'|áº[\x80-\xff0-9a-zA-Z]'
    r'|á»[\x80-\xff0-9a-zA-Z]'
    r'|Ä[\x80-\xff‘-™]'
    r'|Æ[°¡\x80-\xff]'
    r'|â[\x80-\xbf]{1,2}'
    r'|Â[·\s\xa0-\xff]'
    r'|\ufffd'
    r'|&#x[0-9a-fA-F]+;'
    r')'
)

def main():
    root_dirs = ['apps/web/src', 'apps/api', 'services']
    checked_files = []
    findings = {}

    for r_dir in root_dirs:
        for root, dirs, files in os.walk(r_dir):
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.next', '__pycache__', '.venv', 'data']]
            for f in files:
                if f.endswith(('.ts', '.tsx', '.py', '.json', '.css', '.html')):
                    path = Path(root) / f
                    checked_files.append(path)
                    try:
                        raw = path.read_bytes()
                        content = raw.decode('utf-8')
                    except UnicodeDecodeError:
                        findings[str(path)] = [(0, ['UTF8_DECODE_ERROR'], 'File failed UTF-8 decode')]
                        continue

                    # Check for BOM
                    if raw.startswith(b'\xef\xbb\xbf'):
                        pass

                    matches = []
                    for line_no, line in enumerate(content.splitlines(), 1):
                        found = MOJI_PATTERN.findall(line)
                        if found:
                            matches.append((line_no, found, line.strip()))
                    if matches:
                        findings[str(path)] = matches

    print(f"Total files checked: {len(checked_files)}")
    print(f"Files with mojibake/issues: {len(findings)}")
    for p, items in findings.items():
        print(f"\n=== {p} ({len(items)} affected lines) ===")
        for line_no, m, sample in items:
            safe_sample = sample.encode('ascii', errors='backslashreplace').decode('ascii')
            safe_m = repr(m).encode('ascii', errors='backslashreplace').decode('ascii')
            print(f"  Line {line_no:3d} [{safe_m}]: {safe_sample[:100]}")

if __name__ == '__main__':
    main()
