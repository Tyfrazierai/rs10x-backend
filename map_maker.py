#!/usr/bin/env python3
"""
MAP MAKER AGENT
===============
The first agent in the Codebase Onboarding System.

Job: Understand what exists in a codebase, not how it works.

Inputs: A folder path to a codebase
Outputs: A plain English map of the system

Usage:
    python map_maker.py /path/to/codebase
    python map_maker.py /path/to/codebase --output report.md
"""

import os
import sys
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

# Folders to ignore (common non-code folders)
IGNORE_FOLDERS = {
    'node_modules', '.git', '.svn', '__pycache__', '.next', '.nuxt',
    'dist', 'build', 'out', '.cache', 'coverage', '.nyc_output',
    'vendor', 'venv', 'env', '.env', '.venv', 'virtualenv',
    '.idea', '.vscode', '.DS_Store', 'tmp', 'temp', 'logs',
    'target', 'bin', 'obj', '.gradle', '.maven',
}

# Files to ignore
IGNORE_FILES = {
    '.DS_Store', 'Thumbs.db', '.gitignore', '.npmrc', '.nvmrc',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'composer.lock',
    'Gemfile.lock', 'poetry.lock', 'Pipfile.lock',
}

# File extensions and what they mean
EXTENSION_MAP = {
    # JavaScript/TypeScript
    '.js': 'JavaScript',
    '.jsx': 'JavaScript (React)',
    '.ts': 'TypeScript',
    '.tsx': 'TypeScript (React)',
    '.mjs': 'JavaScript (ES Module)',
    '.cjs': 'JavaScript (CommonJS)',
    
    # Python
    '.py': 'Python',
    '.pyx': 'Cython',
    '.pyi': 'Python Type Stubs',
    
    # Ruby
    '.rb': 'Ruby',
    '.erb': 'Ruby (ERB Template)',
    '.rake': 'Ruby (Rake)',
    
    # PHP
    '.php': 'PHP',
    '.blade.php': 'PHP (Laravel Blade)',
    
    # Java/Kotlin
    '.java': 'Java',
    '.kt': 'Kotlin',
    '.kts': 'Kotlin Script',
    
    # C#/.NET
    '.cs': 'C#',
    '.fs': 'F#',
    '.vb': 'Visual Basic',
    
    # Go
    '.go': 'Go',
    
    # Rust
    '.rs': 'Rust',
    
    # C/C++
    '.c': 'C',
    '.h': 'C Header',
    '.cpp': 'C++',
    '.hpp': 'C++ Header',
    '.cc': 'C++',
    
    # Swift
    '.swift': 'Swift',
    
    # Web
    '.html': 'HTML',
    '.htm': 'HTML',
    '.css': 'CSS',
    '.scss': 'SCSS',
    '.sass': 'Sass',
    '.less': 'Less',
    '.vue': 'Vue.js',
    '.svelte': 'Svelte',
    
    # Data/Config
    '.json': 'JSON',
    '.yaml': 'YAML',
    '.yml': 'YAML',
    '.toml': 'TOML',
    '.xml': 'XML',
    '.ini': 'INI Config',
    '.env': 'Environment Config',
    
    # Database
    '.sql': 'SQL',
    '.prisma': 'Prisma Schema',
    
    # Documentation
    '.md': 'Markdown',
    '.mdx': 'MDX (Markdown + JSX)',
    '.rst': 'reStructuredText',
    '.txt': 'Text',
    
    # Shell
    '.sh': 'Shell Script',
    '.bash': 'Bash Script',
    '.zsh': 'Zsh Script',
    '.ps1': 'PowerShell',
    
    # Other
    '.dockerfile': 'Dockerfile',
    '.graphql': 'GraphQL',
    '.proto': 'Protocol Buffers',
}

# Framework detection patterns
FRAMEWORK_INDICATORS = {
    # JavaScript Frameworks
    'package.json': {
        'next': 'Next.js',
        'react': 'React',
        'vue': 'Vue.js',
        'angular': 'Angular',
        'svelte': 'Svelte',
        'express': 'Express.js',
        'fastify': 'Fastify',
        'nest': 'NestJS',
        'nuxt': 'Nuxt.js',
        'gatsby': 'Gatsby',
        'remix': 'Remix',
    },
    
    # Python Frameworks
    'requirements.txt': {
        'django': 'Django',
        'flask': 'Flask',
        'fastapi': 'FastAPI',
        'pyramid': 'Pyramid',
        'tornado': 'Tornado',
    },
    'pyproject.toml': {
        'django': 'Django',
        'flask': 'Flask',
        'fastapi': 'FastAPI',
    },
    
    # Ruby
    'Gemfile': {
        'rails': 'Ruby on Rails',
        'sinatra': 'Sinatra',
    },
    
    # PHP
    'composer.json': {
        'laravel': 'Laravel',
        'symfony': 'Symfony',
    },
    
    # Java
    'pom.xml': {
        'spring': 'Spring',
    },
    'build.gradle': {
        'spring': 'Spring',
    },
}

# Common folder patterns and what they typically mean
FOLDER_PATTERNS = {
    # Frontend
    'components': 'UI components (buttons, forms, cards, etc.)',
    'pages': 'Page-level components or routes',
    'views': 'View templates or page components',
    'layouts': 'Page layout templates',
    'templates': 'HTML or view templates',
    'assets': 'Static files (images, fonts, etc.)',
    'public': 'Publicly accessible static files',
    'static': 'Static files served directly',
    'styles': 'CSS/styling files',
    'css': 'Stylesheets',
    'scss': 'SCSS stylesheets',
    
    # State/Data
    'store': 'State management (Redux, Vuex, etc.)',
    'stores': 'State management stores',
    'state': 'Application state',
    'redux': 'Redux state management',
    'context': 'React context providers',
    
    # Backend
    'api': 'API endpoints or client',
    'routes': 'URL route definitions',
    'controllers': 'Request handlers (MVC pattern)',
    'handlers': 'Request or event handlers',
    'middleware': 'Request/response middleware',
    'services': 'Business logic services',
    'providers': 'Service providers or dependency injection',
    
    # Data Layer
    'models': 'Data models/entities',
    'entities': 'Database entities',
    'schemas': 'Data schemas (database, validation)',
    'migrations': 'Database migrations',
    'seeds': 'Database seed data',
    'seeders': 'Database seeders',
    'repositories': 'Data access layer',
    'dao': 'Data access objects',
    
    # Utilities
    'utils': 'Utility/helper functions',
    'utilities': 'Utility/helper functions',
    'helpers': 'Helper functions',
    'lib': 'Library code or utilities',
    'common': 'Shared/common code',
    'shared': 'Shared code across modules',
    'core': 'Core application logic',
    
    # Configuration
    'config': 'Configuration files',
    'configs': 'Configuration files',
    'settings': 'Application settings',
    
    # Testing
    'test': 'Test files',
    'tests': 'Test files',
    '__tests__': 'Jest test files',
    'spec': 'Test specifications',
    'specs': 'Test specifications',
    'e2e': 'End-to-end tests',
    'integration': 'Integration tests',
    'unit': 'Unit tests',
    'fixtures': 'Test fixtures/data',
    'mocks': 'Mock data or functions',
    
    # Types
    'types': 'Type definitions',
    'interfaces': 'Interface definitions',
    'typings': 'Type definitions',
    '@types': 'TypeScript type definitions',
    
    # Features/Modules
    'features': 'Feature modules',
    'modules': 'Application modules',
    'domains': 'Domain modules',
    'apps': 'Sub-applications',
    
    # Other
    'hooks': 'React hooks or lifecycle hooks',
    'composables': 'Vue composables',
    'plugins': 'Plugins or extensions',
    'extensions': 'Extensions or plugins',
    'scripts': 'Build or utility scripts',
    'docs': 'Documentation',
    'documentation': 'Documentation',
    'i18n': 'Internationalization',
    'locales': 'Locale/translation files',
    'translations': 'Translation files',
}


# ============================================================================
# SCANNER CLASS
# ============================================================================

class CodebaseScanner:
    """Scans a codebase and extracts structural information."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.files = []
        self.folders = []
        self.extensions = defaultdict(int)
        self.languages = defaultdict(int)
        self.frameworks = []
        self.config_files = {}
        
    def scan(self):
        """Scan the entire codebase."""
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")
        
        if not self.root_path.is_dir():
            raise ValueError(f"Path is not a directory: {self.root_path}")
        
        self._scan_directory(self.root_path)
        self._detect_frameworks()
        
    def _scan_directory(self, path: Path, depth: int = 0):
        """Recursively scan a directory."""
        try:
            entries = list(path.iterdir())
        except PermissionError:
            return
            
        for entry in entries:
            # Skip ignored folders
            if entry.is_dir() and entry.name in IGNORE_FOLDERS:
                continue
                
            # Skip ignored files
            if entry.is_file() and entry.name in IGNORE_FILES:
                continue
                
            # Skip hidden files/folders (starting with .)
            if entry.name.startswith('.') and entry.name not in ['.env', '.gitignore']:
                continue
                
            relative_path = entry.relative_to(self.root_path)
            
            if entry.is_dir():
                self.folders.append({
                    'path': str(relative_path),
                    'name': entry.name,
                    'depth': depth,
                })
                self._scan_directory(entry, depth + 1)
                
            elif entry.is_file():
                ext = entry.suffix.lower()
                self.extensions[ext] += 1
                
                if ext in EXTENSION_MAP:
                    self.languages[EXTENSION_MAP[ext]] += 1
                
                self.files.append({
                    'path': str(relative_path),
                    'name': entry.name,
                    'extension': ext,
                    'size': entry.stat().st_size,
                })
                
                # Check for config files
                if entry.name in FRAMEWORK_INDICATORS:
                    try:
                        content = entry.read_text(encoding='utf-8', errors='ignore')
                        self.config_files[entry.name] = content
                    except:
                        pass
    
    def _detect_frameworks(self):
        """Detect frameworks based on config files."""
        for config_file, content in self.config_files.items():
            if config_file in FRAMEWORK_INDICATORS:
                patterns = FRAMEWORK_INDICATORS[config_file]
                content_lower = content.lower()
                for pattern, framework in patterns.items():
                    if pattern in content_lower:
                        if framework not in self.frameworks:
                            self.frameworks.append(framework)
    
    def get_folder_analysis(self) -> list:
        """Analyze folders and assign likely purposes."""
        analysis = []
        
        for folder in self.folders:
            folder_name = folder['name'].lower()
            purpose = None
            confidence = 'Low'
            
            # Check against known patterns
            for pattern, description in FOLDER_PATTERNS.items():
                if folder_name == pattern or folder_name.endswith(pattern):
                    purpose = description
                    confidence = 'High'
                    break
            
            # If no exact match, try partial matching
            if not purpose:
                for pattern, description in FOLDER_PATTERNS.items():
                    if pattern in folder_name:
                        purpose = f"Likely {description}"
                        confidence = 'Medium'
                        break
            
            # If still no match, mark as unknown
            if not purpose:
                purpose = "Unknown - needs investigation"
                confidence = 'Low'
            
            analysis.append({
                'path': folder['path'],
                'name': folder['name'],
                'depth': folder['depth'],
                'purpose': purpose,
                'confidence': confidence,
            })
        
        return analysis
    
    def get_tech_stack(self) -> dict:
        """Determine the technology stack."""
        # Sort languages by usage
        sorted_languages = sorted(
            self.languages.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        primary_languages = [lang for lang, count in sorted_languages[:3] if count > 0]
        
        return {
            'primary_languages': primary_languages,
            'all_languages': dict(sorted_languages),
            'frameworks': self.frameworks,
            'file_count': len(self.files),
            'folder_count': len(self.folders),
        }
    
    def get_entry_points(self) -> list:
        """Identify likely entry points."""
        entry_points = []
        
        common_entry_files = [
            'index.js', 'index.ts', 'index.tsx', 'index.jsx',
            'main.js', 'main.ts', 'main.py', 'app.py',
            'server.js', 'server.ts', 'server.py',
            'app.js', 'app.ts', 'application.py',
            'manage.py', 'wsgi.py', 'asgi.py',
            'Program.cs', 'Startup.cs',
            'main.go', 'main.rs', 'Main.java',
        ]
        
        for file in self.files:
            if file['name'] in common_entry_files:
                entry_points.append({
                    'path': file['path'],
                    'name': file['name'],
                    'type': 'Likely application entry point',
                })
        
        return entry_points
    
    def get_summary(self) -> dict:
        """Get a complete summary of the codebase."""
        return {
            'root_path': str(self.root_path),
            'scanned_at': datetime.now().isoformat(),
            'tech_stack': self.get_tech_stack(),
            'folder_analysis': self.get_folder_analysis(),
            'entry_points': self.get_entry_points(),
            'statistics': {
                'total_files': len(self.files),
                'total_folders': len(self.folders),
                'extensions': dict(self.extensions),
            }
        }


# ============================================================================
# REPORT GENERATOR
# ============================================================================

def generate_report(summary: dict) -> str:
    """Generate a human-readable markdown report."""
    
    tech = summary['tech_stack']
    folders = summary['folder_analysis']
    entries = summary['entry_points']
    stats = summary['statistics']
    
    report = []
    
    # Header
    report.append("# Codebase Map")
    report.append("")
    report.append(f"**Analyzed:** {summary['root_path']}")
    report.append(f"**Generated:** {summary['scanned_at']}")
    report.append("")
    
    # Executive Summary
    report.append("---")
    report.append("")
    report.append("## Executive Summary")
    report.append("")
    
    if tech['primary_languages']:
        langs = ", ".join(tech['primary_languages'])
        report.append(f"This is a **{langs}** codebase.")
    
    if tech['frameworks']:
        frameworks = ", ".join(tech['frameworks'])
        report.append(f"It uses **{frameworks}**.")
    
    report.append("")
    report.append(f"- **{stats['total_files']}** files")
    report.append(f"- **{stats['total_folders']}** folders")
    report.append("")
    
    # Tech Stack
    report.append("---")
    report.append("")
    report.append("## Technology Stack")
    report.append("")
    
    if tech['all_languages']:
        report.append("| Language | File Count |")
        report.append("|----------|------------|")
        for lang, count in sorted(tech['all_languages'].items(), key=lambda x: -x[1])[:10]:
            report.append(f"| {lang} | {count} |")
        report.append("")
    
    if tech['frameworks']:
        report.append("**Frameworks Detected:**")
        for fw in tech['frameworks']:
            report.append(f"- {fw}")
        report.append("")
    
    # Folder Map
    report.append("---")
    report.append("")
    report.append("## Folder Map")
    report.append("")
    report.append("### High Confidence (I'm sure about these)")
    report.append("")
    report.append("| Folder | What It Does |")
    report.append("|--------|--------------|")
    
    high_conf = [f for f in folders if f['confidence'] == 'High' and f['depth'] <= 2]
    for folder in high_conf:
        indent = "  " * folder['depth']
        report.append(f"| {indent}{folder['path']} | {folder['purpose']} |")
    
    if not high_conf:
        report.append("| (none found) | |")
    
    report.append("")
    report.append("### Medium Confidence (Probably this)")
    report.append("")
    report.append("| Folder | What It Likely Does |")
    report.append("|--------|---------------------|")
    
    med_conf = [f for f in folders if f['confidence'] == 'Medium' and f['depth'] <= 2]
    for folder in med_conf:
        indent = "  " * folder['depth']
        report.append(f"| {indent}{folder['path']} | {folder['purpose']} |")
    
    if not med_conf:
        report.append("| (none found) | |")
    
    report.append("")
    report.append("### Needs Investigation (I'm not sure)")
    report.append("")
    
    low_conf = [f for f in folders if f['confidence'] == 'Low' and f['depth'] <= 1]
    if low_conf:
        report.append("| Folder | Notes |")
        report.append("|--------|-------|")
        for folder in low_conf[:10]:  # Limit to 10
            report.append(f"| {folder['path']} | Needs human review |")
    else:
        report.append("All folders identified with reasonable confidence.")
    
    report.append("")
    
    # Entry Points
    report.append("---")
    report.append("")
    report.append("## Where To Start")
    report.append("")
    report.append("If you're new to this codebase, look at these files first:")
    report.append("")
    
    if entries:
        for i, entry in enumerate(entries[:5], 1):
            report.append(f"{i}. **{entry['path']}** - {entry['type']}")
    else:
        report.append("No obvious entry points found. Look for main application files.")
    
    report.append("")
    
    # Next Steps
    report.append("---")
    report.append("")
    report.append("## Recommended Next Steps")
    report.append("")
    report.append("1. **Read the README** if one exists")
    report.append("2. **Check the entry points** listed above")
    report.append("3. **Explore the models/entities folder** to understand the business objects")
    report.append("4. **Run the Translator Agent** to get a business glossary")
    report.append("5. **Run the Flow Tracer Agent** to understand key processes")
    report.append("")
    
    # Confidence Note
    report.append("---")
    report.append("")
    report.append("## Confidence Note")
    report.append("")
    high_count = len([f for f in folders if f['confidence'] == 'High'])
    med_count = len([f for f in folders if f['confidence'] == 'Medium'])
    low_count = len([f for f in folders if f['confidence'] == 'Low'])
    total = len(folders)
    
    if total > 0:
        confidence_pct = ((high_count + med_count * 0.5) / total) * 100
        report.append(f"**Overall Map Confidence: {confidence_pct:.0f}%**")
        report.append("")
        report.append(f"- High confidence folders: {high_count}")
        report.append(f"- Medium confidence folders: {med_count}")
        report.append(f"- Needs investigation: {low_count}")
    
    report.append("")
    
    return "\n".join(report)


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python map_maker.py /path/to/codebase [--output report.md]")
        print("")
        print("Example:")
        print("  python map_maker.py ./my-project")
        print("  python map_maker.py ./my-project --output analysis.md")
        sys.exit(1)
    
    codebase_path = sys.argv[1]
    output_file = None
    
    # Check for output flag
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    print(f"[MAP] Scanning codebase: {codebase_path}")
    
    try:
        scanner = CodebaseScanner(codebase_path)
        scanner.scan()
        summary = scanner.get_summary()
        report = generate_report(summary)
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"[OK] Report saved to: {output_file}")
        else:
            print(report)
            
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
