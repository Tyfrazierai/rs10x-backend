#!/usr/bin/env python3
"""
SAFETY INSPECTOR AGENT (Agent 5) - Checks test coverage

Usage: python safety_inspector.py /path/to/codebase --output safety.md
"""

import sys
from pathlib import Path
from datetime import datetime

SKIP = {'node_modules', '.git', '__pycache__', 'dist', 'build', 'venv'}

class SafetyInspector:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.test_files = []
        self.source_files = []
        self.test_config = None
        self.ci_config = None
    
    def analyze(self):
        self._find_tests()
        self._find_source_files()
        self._check_test_config()
        self._check_ci()
        
        coverage = self._estimate_coverage()
        
        return {
            'path': str(self.root),
            'analyzed_at': datetime.now().isoformat(),
            'test_file_count': len(self.test_files),
            'source_file_count': len(self.source_files),
            'test_files': self.test_files[:20],
            'has_test_config': self.test_config is not None,
            'has_ci': self.ci_config is not None,
            'estimated_coverage': coverage,
            'test_config': self.test_config,
            'ci_config': self.ci_config,
        }
    
    def _find_tests(self):
        test_patterns = ['test', 'tests', 'spec', 'specs', '__tests__']
        
        for pattern in test_patterns:
            test_dir = self.root / pattern
            if test_dir.exists():
                self._scan_tests(test_dir)
        
        # Also find test files in src
        self._find_test_files_in_src(self.root)
    
    def _scan_tests(self, folder):
        try:
            for f in folder.iterdir():
                if f.name in SKIP: continue
                if f.is_dir(): self._scan_tests(f)
                elif f.suffix in ['.ts', '.js', '.py', '.rb']:
                    self.test_files.append(str(f.relative_to(self.root)))
        except: pass
    
    def _find_test_files_in_src(self, folder):
        try:
            for f in folder.iterdir():
                if f.name in SKIP: continue
                if f.is_dir(): self._find_test_files_in_src(f)
                elif '.test.' in f.name or '.spec.' in f.name or '_test.' in f.name:
                    rel = str(f.relative_to(self.root))
                    if rel not in self.test_files:
                        self.test_files.append(rel)
        except: pass
    
    def _find_source_files(self):
        self._scan_source(self.root)
    
    def _scan_source(self, folder):
        try:
            for f in folder.iterdir():
                if f.name in SKIP or f.name in ['test', 'tests', '__tests__', 'spec']:
                    continue
                if f.is_dir():
                    self._scan_source(f)
                elif f.suffix in ['.ts', '.js', '.py', '.rb', '.go', '.java']:
                    if '.test.' not in f.name and '.spec.' not in f.name:
                        self.source_files.append(str(f.relative_to(self.root)))
        except: pass
    
    def _check_test_config(self):
        configs = ['jest.config.js', 'jest.config.ts', 'pytest.ini', 'vitest.config.ts', 
                   'karma.conf.js', 'cypress.config.js', 'playwright.config.ts']
        
        for config in configs:
            if (self.root / config).exists():
                self.test_config = config
                return
    
    def _check_ci(self):
        ci_paths = ['.github/workflows', '.gitlab-ci.yml', 'Jenkinsfile', '.circleci']
        
        for ci in ci_paths:
            if (self.root / ci).exists():
                self.ci_config = ci
                return
    
    def _estimate_coverage(self):
        if not self.source_files:
            return 0
        
        # Simple heuristic: ratio of test files to source files
        ratio = len(self.test_files) / len(self.source_files)
        
        # Scale it (more test files = better, but cap at 100%)
        coverage = min(ratio * 70, 100)
        
        # Bonus for having test config and CI
        if self.test_config:
            coverage += 10
        if self.ci_config:
            coverage += 10
        
        return min(coverage, 100)

def generate_report(r):
    lines = [
        "# Safety Inspection", "",
        f"**Codebase:** {r['path']}", "",
        "---", "",
        "## Test Coverage Summary", "",
    ]
    
    # Coverage meter
    coverage = r['estimated_coverage']
    if coverage >= 70:
        status = "[GOOD]"
    elif coverage >= 40:
        status = "[NEEDS IMPROVEMENT]"
    else:
        status = "[POOR]"
    
    lines.extend([
        f"**Estimated Coverage:** {coverage:.0f}% {status}", "",
        f"- **Test files:** {r['test_file_count']}",
        f"- **Source files:** {r['source_file_count']}",
        f"- **Test framework configured:** {'Yes (' + r['test_config'] + ')' if r['has_test_config'] else 'No'}",
        f"- **CI/CD configured:** {'Yes (' + r['ci_config'] + ')' if r['has_ci'] else 'No'}",
        ""
    ])
    
    # Health Check
    lines.extend(["---", "", "## Health Check", "", "| Check | Status |", "|-------|--------|"])
    
    lines.append(f"| Has test files | {'Yes' if r['test_file_count'] > 0 else 'No'} |")
    lines.append(f"| Has test config | {'Yes' if r['has_test_config'] else 'No'} |")
    lines.append(f"| Has CI/CD | {'Yes' if r['has_ci'] else 'No'} |")
    lines.append(f"| Good test ratio | {'Yes' if coverage >= 50 else 'No'} |")
    
    # Test files
    if r['test_files']:
        lines.extend(["", "---", "", "## Test Files Found", ""])
        for tf in r['test_files'][:15]:
            lines.append(f"- `{tf}`")
        if len(r['test_files']) > 15:
            lines.append(f"- ...and {len(r['test_files']) - 15} more")
    
    # Recommendations
    lines.extend(["", "---", "", "## Recommendations", ""])
    
    if not r['has_test_config']:
        lines.append("1. **Add a test framework** (Jest, Pytest, etc.)")
    if not r['has_ci']:
        lines.append("2. **Set up CI/CD** to run tests automatically")
    if coverage < 50:
        lines.append("3. **Add more tests** - especially for critical business logic")
    if coverage >= 70:
        lines.append("- Coverage looks good! Focus on testing edge cases.")
    
    lines.extend(["", "---", "", "## Next Steps", "", "1. Run **Change Planner** when ready to make changes", ""])
    
    return "\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python safety_inspector.py /path/to/codebase [--output safety.md]")
        sys.exit(1)
    
    output = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output = sys.argv[idx + 1]
    
    print(f"[SAFETY] Analyzing: {sys.argv[1]}")
    
    result = SafetyInspector(sys.argv[1]).analyze()
    report = generate_report(result)
    
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"[OK] Saved to: {output}")
        print(f"     Estimated coverage: {result['estimated_coverage']:.0f}%")
    else:
        print(report)

if __name__ == "__main__":
    main()
