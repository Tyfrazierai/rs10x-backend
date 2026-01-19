#!/usr/bin/env python3
"""
AI-ENHANCED TRANSLATOR AGENT (Agent 2)
======================================
Uses Claude AI to intelligently explain business entities.

This version connects to the Claude API for smart analysis
instead of just pattern matching.

Setup:
    export ANTHROPIC_API_KEY="your-key-here"

Usage:
    python translator_ai.py /path/to/codebase --output glossary.md
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime

# Check for API key
API_KEY = os.environ.get('ANTHROPIC_API_KEY')

# Try to import anthropic library
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

SKIP_FOLDERS = {'node_modules', '.git', '__pycache__', 'dist', 'build', 'venv', '.venv', 'coverage'}


class AITranslator:
    """AI-powered translator that uses Claude to explain code."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.entities = {}
        self.relationships = []
        self.raw_code = {}  # Store raw code for AI analysis
        
        # Initialize Claude client if available
        if HAS_ANTHROPIC and API_KEY:
            self.client = anthropic.Anthropic(api_key=API_KEY)
            self.ai_enabled = True
        else:
            self.client = None
            self.ai_enabled = False
    
    def analyze(self):
        """Run the full analysis."""
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")
        
        print(" Scanning for models and entities...")
        self._find_model_files()
        
        if self.ai_enabled:
            print("[AI] Running AI analysis (this may take a minute)...")
            self._ai_analyze_entities()
        else:
            print("[!]  AI not available, using basic analysis")
            self._basic_analyze_entities()
        
        self._infer_relationships()
        
        return self._build_result()
    
    def _find_model_files(self):
        """Find all model/entity files."""
        model_folders = [
            'models', 'model', 'entities', 'types', 'domain',
            'src/models', 'src/entities', 'src/types',
            'server/models', 'app/models', 'prisma',
        ]
        
        for folder_name in model_folders:
            folder_path = self.root_path / folder_name
            if folder_path.exists() and folder_path.is_dir():
                self._scan_folder(folder_path)
        
        # Also check for prisma schema
        prisma_schema = self.root_path / 'prisma' / 'schema.prisma'
        if prisma_schema.exists():
            self._parse_prisma_schema(prisma_schema)
    
    def _scan_folder(self, folder: Path):
        """Scan a folder for model files."""
        try:
            for entry in folder.iterdir():
                if entry.name in SKIP_FOLDERS:
                    continue
                if entry.is_file() and entry.suffix in ['.ts', '.js', '.py', '.prisma']:
                    self._parse_model_file(entry)
        except PermissionError:
            pass
    
    def _parse_model_file(self, file_path: Path):
        """Parse a model file and extract entities."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            relative_path = str(file_path.relative_to(self.root_path))
            
            # Store raw code for AI analysis
            self.raw_code[relative_path] = content
            
            # Extract entity names and their code
            if file_path.suffix in ['.ts', '.tsx', '.js', '.jsx']:
                self._extract_typescript_entities(content, relative_path)
            elif file_path.suffix == '.py':
                self._extract_python_entities(content, relative_path)
        except Exception as e:
            print(f"  Warning: Could not parse {file_path}: {e}")
    
    def _extract_typescript_entities(self, content: str, file_path: str):
        """Extract TypeScript/JavaScript entities."""
        patterns = [
            r'(?:export\s+)?interface\s+(\w+)\s*(?:extends\s+[\w\s,<>]+)?\s*\{([^}]*)\}',
            r'(?:export\s+)?type\s+(\w+)\s*=\s*\{([^}]*)\}',
            r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{([^}]*)\}',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.DOTALL):
                name = match.group(1)
                body = match.group(2)
                
                # Skip utility types
                if name.endswith(('Props', 'Options', 'Config', 'State')):
                    continue
                
                fields = self._extract_fields(body)
                if fields:
                    self.entities[name] = {
                        'name': name,
                        'file': file_path,
                        'fields': fields,
                        'raw_code': f"interface {name} {{{body}}}",
                        'description': None,  # Will be filled by AI
                    }
    
    def _extract_python_entities(self, content: str, file_path: str):
        """Extract Python class entities."""
        pattern = r'class\s+(\w+)\s*\([^)]*\)\s*:((?:\n(?:\s+.+)?)*)'
        
        for match in re.finditer(pattern, content):
            name = match.group(1)
            body = match.group(2)
            
            fields = self._extract_python_fields(body)
            if fields:
                self.entities[name] = {
                    'name': name,
                    'file': file_path,
                    'fields': fields,
                    'raw_code': f"class {name}:\n{body}",
                    'description': None,
                }
    
    def _parse_prisma_schema(self, file_path: Path):
        """Parse Prisma schema file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            relative_path = str(file_path.relative_to(self.root_path))
            
            self.raw_code[relative_path] = content
            
            # Extract models
            pattern = r'model\s+(\w+)\s*\{([^}]+)\}'
            for match in re.finditer(pattern, content):
                name = match.group(1)
                body = match.group(2)
                
                fields = self._extract_prisma_fields(body)
                self.entities[name] = {
                    'name': name,
                    'file': relative_path,
                    'fields': fields,
                    'raw_code': f"model {name} {{{body}}}",
                    'description': None,
                }
        except Exception as e:
            print(f"  Warning: Could not parse Prisma schema: {e}")
    
    def _extract_fields(self, body: str) -> list:
        """Extract fields from TypeScript body."""
        fields = []
        pattern = r'(\w+)\s*\??\s*:\s*([^;,\n]+)'
        
        for match in re.finditer(pattern, body):
            name = match.group(1)
            type_str = match.group(2).strip()
            
            if '(' in type_str and ')' in type_str:  # Skip methods
                continue
            
            fields.append({
                'name': name,
                'type': type_str,
                'meaning': None,  # Will be filled by AI
            })
        
        return fields
    
    def _extract_python_fields(self, body: str) -> list:
        """Extract fields from Python class body."""
        fields = []
        patterns = [
            r'(\w+)\s*[=:]\s*(?:Column|Field|models\.\w+)',
            r'(\w+)\s*:\s*(\w+)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, body):
                name = match.group(1)
                if name.startswith('_'):
                    continue
                type_str = match.group(2) if len(match.groups()) > 1 else 'unknown'
                fields.append({
                    'name': name,
                    'type': type_str,
                    'meaning': None,
                })
        
        return fields
    
    def _extract_prisma_fields(self, body: str) -> list:
        """Extract fields from Prisma model body."""
        fields = []
        pattern = r'^\s*(\w+)\s+(\w+(?:\[\])?(?:\?)?)'
        
        for line in body.split('\n'):
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                type_str = match.group(2)
                fields.append({
                    'name': name,
                    'type': type_str,
                    'meaning': None,
                })
        
        return fields
    
    def _ai_analyze_entities(self):
        """Use Claude to analyze and explain entities."""
        if not self.entities:
            return
        
        # Build context about all entities
        entities_summary = []
        for name, entity in self.entities.items():
            field_list = ", ".join([f"{f['name']}: {f['type']}" for f in entity['fields'][:10]])
            entities_summary.append(f"- {name}: {field_list}")
        
        entities_context = "\n".join(entities_summary)
        
        # Analyze each entity with AI
        for name, entity in self.entities.items():
            try:
                description, field_meanings = self._ask_claude_about_entity(
                    name, 
                    entity['raw_code'],
                    entity['fields'],
                    entities_context
                )
                
                entity['description'] = description
                
                # Update field meanings
                for field in entity['fields']:
                    if field['name'] in field_meanings:
                        field['meaning'] = field_meanings[field['name']]
                    else:
                        field['meaning'] = "Purpose unclear"
                
                print(f"  [OK] Analyzed: {name}")
                
            except Exception as e:
                print(f"  [X] Failed to analyze {name}: {e}")
                entity['description'] = "Could not analyze with AI"
                for field in entity['fields']:
                    field['meaning'] = "Analysis failed"
    
    def _ask_claude_about_entity(self, name: str, code: str, fields: list, context: str) -> tuple:
        """Ask Claude to explain an entity."""
        
        field_names = [f['name'] for f in fields]
        
        prompt = f"""You are analyzing a codebase for a business analyst who is not technical.

Here are all the entities in this system:
{context}

Now explain this specific entity:

```
{code}
```

Provide:
1. A one-sentence plain English description of what "{name}" represents in business terms (not technical terms)
2. For each field, a brief plain English explanation of what it means

Respond in this exact JSON format:
{{
  "description": "One sentence explaining what this entity represents",
  "fields": {{
    "fieldName1": "What this field means",
    "fieldName2": "What this field means"
  }}
}}

Only include fields from this list: {field_names}
Keep explanations simple and business-focused, not technical.
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        response_text = response.content[0].text
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            data = json.loads(json_match.group())
            return data.get('description', 'Unknown'), data.get('fields', {})
        
        return "Could not parse AI response", {}
    
    def _basic_analyze_entities(self):
        """Fallback: Basic pattern-based analysis when AI is not available."""
        patterns = {
            'user': "Represents a person who can log into the system",
            'customer': "Represents a customer who makes purchases",
            'order': "Represents a purchase order",
            'product': "Represents an item that can be purchased",
            'cart': "Represents a shopping cart",
            'payment': "Represents a payment transaction",
            'address': "Represents a physical address",
            'category': "Represents a grouping/category",
            'review': "Represents a product review",
            'session': "Represents a login session",
            'discount': "Represents a discount or promotion",
        }
        
        field_patterns = {
            'id': 'Unique identifier',
            'email': 'Email address',
            'name': 'Name',
            'price': 'Price/cost',
            'quantity': 'Number of items',
            'total': 'Total amount',
            'status': 'Current status',
            'createdat': 'When this was created',
            'updatedat': 'When this was last modified',
        }
        
        for name, entity in self.entities.items():
            # Set description
            name_lower = name.lower()
            entity['description'] = next(
                (desc for pattern, desc in patterns.items() if pattern in name_lower),
                "Purpose unclear - needs review"
            )
            
            # Set field meanings
            for field in entity['fields']:
                field_lower = field['name'].lower()
                field['meaning'] = next(
                    (meaning for pattern, meaning in field_patterns.items() if pattern in field_lower),
                    "Purpose unclear - needs review"
                )
    
    def _infer_relationships(self):
        """Infer relationships between entities."""
        entity_names = {name.lower(): name for name in self.entities.keys()}
        
        for name, entity in self.entities.items():
            for field in entity['fields']:
                field_lower = field['name'].lower()
                
                # Check for foreign key patterns
                if field_lower.endswith('id') or field_lower.endswith('_id'):
                    ref = field_lower.replace('_id', '').replace('id', '')
                    
                    # Find matching entity
                    if ref in entity_names:
                        self.relationships.append({
                            'from': name,
                            'to': entity_names[ref],
                            'via': field['name'],
                            'type': 'references',
                        })
    
    def _build_result(self) -> dict:
        """Build the final result."""
        return {
            'path': str(self.root_path),
            'analyzed_at': datetime.now().isoformat(),
            'ai_enabled': self.ai_enabled,
            'entity_count': len(self.entities),
            'entities': self.entities,
            'relationships': self.relationships,
        }


def generate_report(result: dict) -> str:
    """Generate a markdown report."""
    lines = [
        "# Business Dictionary",
        "",
        f"**Codebase:** {result['path']}",
        f"**Generated:** {result['analyzed_at']}",
        f"**AI-Powered:** {'Yes ' if result['ai_enabled'] else 'No (basic mode)'}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"Found **{result['entity_count']}** business entities.",
        "",
    ]
    
    if result['entities']:
        lines.extend(["---", "", "## Business Entities", ""])
        
        for name, entity in sorted(result['entities'].items()):
            lines.append(f"### {name}")
            lines.append("")
            lines.append(f"**What it is:** {entity['description']}")
            lines.append("")
            lines.append(f"**File:** `{entity['file']}`")
            lines.append("")
            
            if entity['fields']:
                lines.append("| Field | Type | What It Means |")
                lines.append("|-------|------|---------------|")
                
                for field in entity['fields'][:15]:
                    meaning = field.get('meaning', 'Unknown')
                    lines.append(f"| {field['name']} | {field['type']} | {meaning} |")
                
                lines.append("")
    
    if result['relationships']:
        lines.extend(["---", "", "## How Things Connect", ""])
        lines.append("| From | Relationship | To | Via Field |")
        lines.append("|------|--------------|-----|-----------|")
        
        for rel in result['relationships']:
            lines.append(f"| {rel['from']} | {rel['type']} | {rel['to']} | {rel['via']} |")
        
        lines.append("")
    
    lines.extend([
        "---", "",
        "## Next Steps", "",
        "1. Review the entity descriptions",
        "2. Run the **Flow Tracer** to understand processes",
        "3. Run the **Risk Spotter** to identify dangerous areas",
        ""
    ])
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("AI-ENHANCED TRANSLATOR AGENT")
        print("=" * 60)
        print("")
        print("Usage: python translator_ai.py /path/to/codebase [--output glossary.md]")
        print("")
        print("Setup:")
        print("  1. Install anthropic: pip install anthropic")
        print("  2. Set your API key: export ANTHROPIC_API_KEY='your-key'")
        print("")
        sys.exit(1)
    
    codebase_path = sys.argv[1]
    output_file = None
    
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    # Check setup
    if not HAS_ANTHROPIC:
        print("[!]  anthropic library not installed")
        print("   Run: pip install anthropic")
        print("   Continuing with basic analysis...")
        print("")
    elif not API_KEY:
        print("[!]  ANTHROPIC_API_KEY not set")
        print("   Run: export ANTHROPIC_API_KEY='your-key'")
        print("   Continuing with basic analysis...")
        print("")
    
    print(f" AI Translator analyzing: {codebase_path}")
    print("")
    
    try:
        translator = AITranslator(codebase_path)
        result = translator.analyze()
        report = generate_report(result)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print("")
            print(f"[OK] Report saved to: {output_file}")
            print(f"   Found {result['entity_count']} entities")
            print(f"   AI-powered: {result['ai_enabled']}")
        else:
            print(report)
            
    except Exception as e:
        print(f"[X] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
