#!/usr/bin/env python3
"""
RISK SPOTTER AGENT (Agent 4) - Identifies risky areas

Usage: python risk_spotter.py /path/to/codebase --output risks.md
"""

import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

SKIP = {'node_modules', '.git', '__pycache__', 'dist', 'build', 'venv', 'coverage'}

class RiskSpotter:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.imports = defaultdict(list)  # file -> what it imports
        self.importers = defaultdict(list)  # file -> who imports it
        self.risks = []
    
    def analyze(self):
        self._scan_imports(self.root)
        self._calculate_risks()
        
        return {
            'path': str(self.root),
            'analyzed_at': datetime.now().isoformat(),
            'high_risk_files': self._get_high_risk(),
            'risks': self.risks,
        }
    
    def _scan_imports(self, folder):
        try:
            for f in folder.iterdir():
                if f.name in SKIP: continue
                if f.is_dir(): self._scan_imports(f)
                elif f.suffix in ['.ts', '.js', '.py']: self._parse_imports(f)
        except: pass
    
    def _parse_imports(self, file):
        try:
            content = file.read_text(errors='ignore')
            rel = str(file.relative_to(self.root))
            
            # JS/TS imports
            for m in re.finditer(r'(?:import|require)\s*\(?[\'"]([^\'"\n]+)[\'"]', content):
                imported = m.group(1)
                if imported.startswith('.'):
                    self.imports[rel].append(imported)
                    # Track reverse
                    self.importers[imported].append(rel)
            
            # Python imports
            for m in re.finditer(r'from\s+(\S+)\s+import|import\s+(\S+)', content):
                imported = m.group(1) or m.group(2)
                if not imported.startswith(('os', 'sys', 'json', 're', 'datetime')):
                    self.imports[rel].append(imported)
        except: pass
    
    def _calculate_risks(self):
        # Find files imported by many others (high fan-in = risky to change)
        import_counts = defaultdict(int)
        
        for file, imports in self.imports.items():
            for imp in imports:
                import_counts[imp] += 1
        
        for file, count in import_counts.items():
            if count >= 5:
                self.risks.append({
                    'file': file,
                    'reason': f'Imported by {count} other files - changes here affect many places',
                    'severity': 'High' if count >= 10 else 'Medium',
                    'importers': count,
                })
    
    def _get_high_risk(self):
        return [r for r in self.risks if r['severity'] == 'High']

def generate_report(r):
    lines = [
        "# Risk Analysis", "",
        f"**Codebase:** {r['path']}", "",
        "---", "",
        "## High Risk Files", "",
        "These files are dangerous to change because many other files depend on them:", "",
    ]
    
    if r['high_risk_files']:
        lines.extend(["| File | Why It's Risky | Severity |", "|------|----------------|----------|"])
        for risk in r['high_risk_files']:
            lines.append(f"| {risk['file']} | {risk['reason']} | {risk['severity']} |")
    else:
        lines.append("No extremely high-risk files found. [OK]")
    
    lines.extend(["", "---", "", "## All Risks", ""])
    
    if r['risks']:
        for risk in sorted(r['risks'], key=lambda x: x['importers'], reverse=True)[:15]:
            lines.append(f"- **{risk['file']}** - {risk['reason']}")
    else:
        lines.append("No significant coupling risks detected.")
    
    lines.extend([
        "", "---", "",
        "## Recommendations", "",
        "1. Add tests before changing high-risk files",
        "2. Make small, incremental changes",
        "3. Run **Safety Inspector** to check test coverage",
        ""
    ])
    
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python risk_spotter.py /path/to/codebase [--output risks.md]")
        sys.exit(1)
    
    output = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]
    
    print(f"[!] Risk Spotter analyzing: {sys.argv[1]}")
    
    result = RiskSpotter(sys.argv[1]).analyze()
    report = generate_report(result)
    
    if output:
        open(output, 'w').write(report)
        print(f"[OK] Saved to: {output}")
        print(f"   Found {len(result['risks'])} risk areas")
    else:
        print(report)

if __name__ == "__main__":
    main()
