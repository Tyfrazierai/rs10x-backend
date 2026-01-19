#!/usr/bin/env python3
"""
BOUNCER AGENT (Agent 0)
=======================
The gatekeeper of the Codebase Onboarding System.

Job: Determine if this codebase is worth analyzing before wasting time.

This agent runs FIRST, before any other agent.

Inputs: A folder path to a codebase
Outputs: 
    - Is this analyzable? (yes/no)
    - What's the tech stack?
    - Health assessment
    - Red flags
    - Recommended settings for other agents

Usage:
    python bouncer.py /path/to/codebase
    python bouncer.py /path/to/codebase --output assessment.md
    python bouncer.py /path/to/codebase --json  (for machine-readable output)
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

# Folders that should NOT exist in the repo (red flags)
RED_FLAG_FOLDERS = {
    'node_modules': "node_modules is committed - this is a mistake, repo will be bloated",
    '.env': ".env folder committed - possible security risk (secrets exposed)",
}

# Files that indicate problems
RED_FLAG_FILES = {
    '.env': "Environment file committed - possible secrets exposed",
    'credentials.json': "Credentials file committed - security risk",
    'secrets.json': "Secrets file committed - security risk",
    '.aws/credentials': "AWS credentials committed - critical security risk",
}

# Files that indicate good health
HEALTH_POSITIVE_FILES = {
    'README.md': "Has documentation",
    'readme.md': "Has documentation",
    'README': "Has documentation",
    '.gitignore': "Has gitignore (knows what to exclude)",
    'LICENSE': "Has license file",
    'CONTRIBUTING.md': "Has contribution guidelines",
    'CHANGELOG.md': "Has changelog",
}

# Files that indicate testing exists
TEST_INDICATORS = {
    'jest.config.js': "Jest testing configured",
    'jest.config.ts': "Jest testing configured",
    'pytest.ini': "Pytest configured",
    'phpunit.xml': "PHPUnit configured",
    '.rspec': "RSpec configured",
    'karma.conf.js': "Karma testing configured",
    'cypress.json': "Cypress E2E testing configured",
    'cypress.config.js': "Cypress E2E testing configured",
    'playwright.config.ts': "Playwright E2E testing configured",
}

# Files that indicate CI/CD exists
CI_INDICATORS = {
    '.github/workflows': "GitHub Actions configured",
    '.gitlab-ci.yml': "GitLab CI configured",
    'Jenkinsfile': "Jenkins configured",
    '.circleci': "CircleCI configured",
    '.travis.yml': "Travis CI configured",
    'azure-pipelines.yml': "Azure Pipelines configured",
    'bitbucket-pipelines.yml': "Bitbucket Pipelines configured",
}

# Package/dependency files and what they indicate
PACKAGE_FILES = {
    'package.json': 'JavaScript/Node.js',
    'requirements.txt': 'Python',
    'pyproject.toml': 'Python (modern)',
    'Pipfile': 'Python (Pipenv)',
    'setup.py': 'Python (package)',
    'Gemfile': 'Ruby',
    'composer.json': 'PHP',
    'pom.xml': 'Java (Maven)',
    'build.gradle': 'Java/Kotlin (Gradle)',
    'Cargo.toml': 'Rust',
    'go.mod': 'Go',
    'Package.swift': 'Swift',
    'pubspec.yaml': 'Dart/Flutter',
    'mix.exs': 'Elixir',
}

# Folders to skip when scanning
SKIP_FOLDERS = {
    '.git', '.svn', '.hg', '__pycache__', '.pytest_cache',
    '.next', '.nuxt', 'dist', 'build', 'out', 'target',
    '.cache', 'coverage', '.nyc_output', 'vendor',
    '.idea', '.vscode', 'tmp', 'temp', 'logs',
}

# Maximum reasonable sizes
MAX_RECOMMENDED_FILES = 5000  # More than this is very large
MAX_RECOMMENDED_DEPTH = 15   # Deeper than this is unusual


# ============================================================================
# BOUNCER CLASS
# ============================================================================

class Bouncer:
    """Evaluates whether a codebase should be analyzed."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.red_flags = []
        self.warnings = []
        self.positives = []
        self.tech_stack = []
        self.file_count = 0
        self.folder_count = 0
        self.max_depth = 0
        self.has_tests = False
        self.has_ci = False
        self.has_readme = False
        self.has_git = False
        self.extensions = defaultdict(int)
        self.blockers = []
        
    def assess(self) -> dict:
        """Run the full assessment."""
        
        # Check if path exists
        if not self.root_path.exists():
            self.blockers.append(f"Path does not exist: {self.root_path}")
            return self._build_result()
        
        if not self.root_path.is_dir():
            self.blockers.append(f"Path is not a directory: {self.root_path}")
            return self._build_result()
        
        # Check if it's empty
        try:
            contents = list(self.root_path.iterdir())
            if not contents:
                self.blockers.append("Directory is empty")
                return self._build_result()
        except PermissionError:
            self.blockers.append("Permission denied - cannot read directory")
            return self._build_result()
        
        # Run all checks
        self._scan_structure()
        self._check_health_files()
        self._check_red_flags()
        self._detect_tech_stack()
        self._check_testing()
        self._check_ci()
        self._assess_size()
        
        return self._build_result()
    
    def _scan_structure(self, path: Path = None, depth: int = 0):
        """Scan the directory structure."""
        if path is None:
            path = self.root_path
            
        if depth > self.max_depth:
            self.max_depth = depth
            
        try:
            entries = list(path.iterdir())
        except PermissionError:
            return
            
        for entry in entries:
            # Skip certain folders
            if entry.is_dir() and entry.name in SKIP_FOLDERS:
                # But check for node_modules committed (red flag)
                if entry.name == 'node_modules' and (path / 'node_modules').exists():
                    # Check if it's actually populated (not just empty)
                    try:
                        nm_contents = list(entry.iterdir())
                        if len(nm_contents) > 10:  # Has actual modules
                            self.red_flags.append(RED_FLAG_FOLDERS['node_modules'])
                    except:
                        pass
                continue
                
            if entry.is_dir():
                self.folder_count += 1
                self._scan_structure(entry, depth + 1)
            elif entry.is_file():
                self.file_count += 1
                ext = entry.suffix.lower()
                self.extensions[ext] += 1
    
    def _check_health_files(self):
        """Check for files that indicate good project health."""
        for filename, description in HEALTH_POSITIVE_FILES.items():
            if (self.root_path / filename).exists():
                self.positives.append(description)
                if 'readme' in filename.lower():
                    self.has_readme = True
        
        # Check for git
        if (self.root_path / '.git').exists():
            self.has_git = True
            self.positives.append("Version controlled with Git")
    
    def _check_red_flags(self):
        """Check for problematic files or folders."""
        for filename, description in RED_FLAG_FILES.items():
            filepath = self.root_path / filename
            if filepath.exists():
                # Check if it's in gitignore
                gitignore_path = self.root_path / '.gitignore'
                is_ignored = False
                if gitignore_path.exists():
                    try:
                        gitignore_content = gitignore_path.read_text()
                        if filename in gitignore_content:
                            is_ignored = True
                    except:
                        pass
                
                if not is_ignored:
                    self.red_flags.append(description)
    
    def _detect_tech_stack(self):
        """Detect the technology stack."""
        for filename, tech in PACKAGE_FILES.items():
            if (self.root_path / filename).exists():
                self.tech_stack.append(tech)
        
        # Also detect from file extensions
        ext_to_tech = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'JavaScript (React)',
            '.tsx': 'TypeScript (React)',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.java': 'Java',
            '.go': 'Go',
            '.rs': 'Rust',
            '.cs': 'C#',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
        }
        
        for ext, count in self.extensions.items():
            if ext in ext_to_tech and count >= 3:  # At least 3 files
                tech = ext_to_tech[ext]
                if tech not in self.tech_stack:
                    self.tech_stack.append(tech)
    
    def _check_testing(self):
        """Check if testing is set up."""
        for indicator, description in TEST_INDICATORS.items():
            if (self.root_path / indicator).exists():
                self.has_tests = True
                self.positives.append(description)
                break
        
        # Also check for test folders
        test_folders = ['tests', 'test', '__tests__', 'spec', 'specs']
        for folder in test_folders:
            if (self.root_path / folder).exists():
                self.has_tests = True
                if "testing" not in ' '.join(self.positives).lower():
                    self.positives.append(f"Has {folder}/ folder")
                break
    
    def _check_ci(self):
        """Check if CI/CD is set up."""
        for indicator, description in CI_INDICATORS.items():
            if (self.root_path / indicator).exists():
                self.has_ci = True
                self.positives.append(description)
                break
    
    def _assess_size(self):
        """Assess if the codebase size is reasonable."""
        if self.file_count > MAX_RECOMMENDED_FILES:
            self.warnings.append(
                f"Very large codebase ({self.file_count} files). "
                f"Analysis may take longer and cost more."
            )
        
        if self.max_depth > MAX_RECOMMENDED_DEPTH:
            self.warnings.append(
                f"Very deep folder structure (depth {self.max_depth}). "
                f"May indicate unusual organization."
            )
        
        if self.file_count < 5:
            self.warnings.append(
                "Very small codebase. May not be complete or may be a template."
            )
    
    def _calculate_health_score(self) -> int:
        """Calculate an overall health score (0-100)."""
        score = 50  # Start at neutral
        
        # Positives
        if self.has_readme:
            score += 10
        if self.has_git:
            score += 10
        if self.has_tests:
            score += 15
        if self.has_ci:
            score += 10
        if '.gitignore' in [p.lower() for p in HEALTH_POSITIVE_FILES.keys() if (self.root_path / p).exists()]:
            score += 5
        
        # Negatives
        score -= len(self.red_flags) * 15
        score -= len(self.warnings) * 5
        
        # Clamp to 0-100
        return max(0, min(100, score))
    
    def _determine_analyzable(self) -> tuple:
        """Determine if this codebase should be analyzed."""
        if self.blockers:
            return False, "Cannot analyze - blockers present"
        
        if len(self.red_flags) >= 3:
            return False, "Too many red flags - needs cleanup first"
        
        if not self.tech_stack:
            return True, "Analyzable but tech stack unclear - may need manual review"
        
        return True, "Ready for analysis"
    
    def _get_agent_recommendations(self) -> dict:
        """Recommend settings for other agents."""
        recommendations = {
            'flow_tracer_depth': 4,  # Default
            'domain_interpreter_focus': [],
            'skip_folders': list(SKIP_FOLDERS),
        }
        
        # Adjust based on size
        if self.file_count > 1000:
            recommendations['flow_tracer_depth'] = 3  # Shallower for large codebases
        elif self.file_count < 100:
            recommendations['flow_tracer_depth'] = 6  # Deeper for small codebases
        
        # Suggest focus areas
        focus_folders = ['models', 'entities', 'schemas', 'src/models', 'app/models']
        for folder in focus_folders:
            if (self.root_path / folder).exists():
                recommendations['domain_interpreter_focus'].append(folder)
        
        return recommendations
    
    def _build_result(self) -> dict:
        """Build the final assessment result."""
        analyzable, status = self._determine_analyzable()
        
        return {
            'path': str(self.root_path),
            'assessed_at': datetime.now().isoformat(),
            'analyzable': analyzable,
            'status': status,
            'health_score': self._calculate_health_score(),
            'tech_stack': list(set(self.tech_stack)),  # Remove duplicates
            'statistics': {
                'file_count': self.file_count,
                'folder_count': self.folder_count,
                'max_depth': self.max_depth,
            },
            'health_indicators': {
                'has_readme': self.has_readme,
                'has_git': self.has_git,
                'has_tests': self.has_tests,
                'has_ci': self.has_ci,
            },
            'positives': self.positives,
            'warnings': self.warnings,
            'red_flags': self.red_flags,
            'blockers': self.blockers,
            'agent_recommendations': self._get_agent_recommendations(),
        }


# ============================================================================
# REPORT GENERATOR
# ============================================================================

def generate_report(result: dict) -> str:
    """Generate a human-readable markdown report."""
    
    report = []
    
    # Header
    report.append("# Bouncer Assessment")
    report.append("")
    report.append(f"**Codebase:** {result['path']}")
    report.append(f"**Assessed:** {result['assessed_at']}")
    report.append("")
    
    # Verdict
    report.append("---")
    report.append("")
    report.append("## Verdict")
    report.append("")
    
    if result['analyzable']:
        report.append("[OK] **APPROVED FOR ANALYSIS**")
    else:
        report.append("[X] **NOT READY FOR ANALYSIS**")
    
    report.append("")
    report.append(f"**Status:** {result['status']}")
    report.append(f"**Health Score:** {result['health_score']}/100")
    report.append("")
    
    # Quick Stats
    report.append("---")
    report.append("")
    report.append("## Quick Stats")
    report.append("")
    stats = result['statistics']
    report.append(f"- **Files:** {stats['file_count']}")
    report.append(f"- **Folders:** {stats['folder_count']}")
    report.append(f"- **Max Depth:** {stats['max_depth']} levels")
    report.append("")
    
    # Tech Stack
    report.append("---")
    report.append("")
    report.append("## Technology Stack")
    report.append("")
    if result['tech_stack']:
        for tech in result['tech_stack']:
            report.append(f"- {tech}")
    else:
        report.append("*Could not determine tech stack*")
    report.append("")
    
    # Health Indicators
    report.append("---")
    report.append("")
    report.append("## Health Check")
    report.append("")
    health = result['health_indicators']
    report.append(f"| Check | Status |")
    report.append(f"|-------|--------|")
    report.append(f"| Has README | {'[OK] Yes' if health['has_readme'] else '[X] No'} |")
    report.append(f"| Version Controlled (Git) | {'[OK] Yes' if health['has_git'] else '[X] No'} |")
    report.append(f"| Has Tests | {'[OK] Yes' if health['has_tests'] else '[!] No'} |")
    report.append(f"| Has CI/CD | {'[OK] Yes' if health['has_ci'] else '[!] No'} |")
    report.append("")
    
    # Good Things
    if result['positives']:
        report.append("---")
        report.append("")
        report.append("## Good Signs")
        report.append("")
        for positive in result['positives']:
            report.append(f"- [OK] {positive}")
        report.append("")
    
    # Warnings
    if result['warnings']:
        report.append("---")
        report.append("")
        report.append("## Warnings")
        report.append("")
        for warning in result['warnings']:
            report.append(f"- [!] {warning}")
        report.append("")
    
    # Red Flags
    if result['red_flags']:
        report.append("---")
        report.append("")
        report.append("## Red Flags")
        report.append("")
        for flag in result['red_flags']:
            report.append(f"- 🚨 {flag}")
        report.append("")
    
    # Blockers
    if result['blockers']:
        report.append("---")
        report.append("")
        report.append("## Blockers (Must Fix)")
        report.append("")
        for blocker in result['blockers']:
            report.append(f"- [X] {blocker}")
        report.append("")
    
    # Recommendations
    report.append("---")
    report.append("")
    report.append("## Recommendations For Analysis")
    report.append("")
    recs = result['agent_recommendations']
    report.append(f"- **Flow Tracer Depth:** {recs['flow_tracer_depth']} levels")
    if recs['domain_interpreter_focus']:
        report.append(f"- **Focus Areas:** {', '.join(recs['domain_interpreter_focus'])}")
    report.append("")
    
    # Next Steps
    report.append("---")
    report.append("")
    report.append("## Next Steps")
    report.append("")
    if result['analyzable']:
        report.append("1. Run the **Map Maker Agent** to understand the structure")
        report.append("2. Run the **Translator Agent** to build a business glossary")
        report.append("3. Run the **Flow Tracer Agent** to understand key processes")
    else:
        report.append("1. Fix the blockers listed above")
        report.append("2. Address the red flags")
        report.append("3. Re-run this assessment")
    report.append("")
    
    return "\n".join(report)


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python bouncer.py /path/to/codebase [--output report.md] [--json]")
        print("")
        print("The Bouncer runs FIRST to determine if a codebase is worth analyzing.")
        print("")
        print("Examples:")
        print("  python bouncer.py ./my-project")
        print("  python bouncer.py ./my-project --output assessment.md")
        print("  python bouncer.py ./my-project --json")
        sys.exit(1)
    
    codebase_path = sys.argv[1]
    output_file = None
    output_json = '--json' in sys.argv
    
    # Check for output flag
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    print(f" Bouncer assessing: {codebase_path}")
    print("")
    
    try:
        bouncer = Bouncer(codebase_path)
        result = bouncer.assess()
        
        if output_json:
            print(json.dumps(result, indent=2))
        elif output_file:
            report = generate_report(result)
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"[OK] Assessment saved to: {output_file}")
            print("")
            if result['analyzable']:
                print("[OK] APPROVED - Ready for analysis")
            else:
                print("[X] NOT APPROVED - See report for details")
        else:
            report = generate_report(result)
            print(report)
            
    except Exception as e:
        print(f"[X] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
