#!/usr/bin/env python3
"""
FLOW TRACER AGENT (Agent 3) - Traces process flows

Usage: python flow_tracer.py /path/to/codebase --output flows.md
"""

import sys
import re
from pathlib import Path
from datetime import datetime

SKIP = {'node_modules', '.git', '__pycache__', 'dist', 'build', 'venv'}

class FlowTracer:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.routes = []
        self.externals = set()
    
    def analyze(self):
        for folder in ['routes', 'api', 'controllers', 'src/api', 'src/routes', 'server/routes']:
            path = self.root / folder
            if path.exists():
                self._scan(path)
        
        return {
            'path': str(self.root),
            'analyzed_at': datetime.now().isoformat(),
            'routes': self.routes,
            'external_deps': list(self.externals),
        }
    
    def _scan(self, folder):
        try:
            for f in folder.iterdir():
                if f.name in SKIP: continue
                if f.is_dir(): self._scan(f)
                elif f.suffix in ['.ts', '.js', '.py']: self._parse(f)
        except: pass
    
    def _parse(self, file):
        try:
            content = file.read_text(errors='ignore')
            rel = str(file.relative_to(self.root))
            
            for m in re.finditer(r'(?:router|app)\.(get|post|put|delete)\s*\(\s*[\'"]([^\'"]+)', content, re.I):
                self.routes.append({'method': m.group(1).upper(), 'path': m.group(2), 'file': rel})
            
            for pattern in ['stripe', 'paypal', 'redis', 'prisma', 'mongoose', 'axios', 'fetch(']:
                if pattern in content.lower():
                    self.externals.add(pattern)
        except: pass

def generate_report(r):
    lines = [
        "# Flow Analysis", "",
        f"**Codebase:** {r['path']}", "",
        "---", "",
        "## API Endpoints", "",
        "| Method | Path | File |",
        "|--------|------|------|",
    ]
    
    for route in r['routes'][:20]:
        lines.append(f"| {route['method']} | {route['path']} | `{route['file']}` |")
    
    if r['external_deps']:
        lines.extend(["", "---", "", "## External Dependencies", ""])
        for dep in r['external_deps']:
            lines.append(f"- {dep}")
    
    lines.extend(["", "---", "", "## Next Steps", "", "1. Run **Risk Spotter** next", ""])
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python flow_tracer.py /path/to/codebase [--output flows.md]")
        sys.exit(1)
    
    output = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]
    
    print(f"[FLOW] Analyzing: {sys.argv[1]}")
    
    result = FlowTracer(sys.argv[1]).analyze()
    report = generate_report(result)
    
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[OK] Saved to: {output}")
    else:
        print(report)

if __name__ == "__main__":
    main()
