#!/usr/bin/env python3
"""
TRANSLATOR AGENT (Agent 2)
==========================
Translates code into business meaning.

Job: Explain what the system represents in plain English.

This agent reads models, entities, database schemas, and API payloads
to build a glossary of business terms.

Inputs: A folder path to a codebase
Outputs: 
    - Business glossary (what each "thing" represents)
    - Relationships between things
    - Naming issues (same thing with different names)

Usage:
    python translator.py /path/to/codebase
    python translator.py /path/to/codebase --output glossary.md
"""

import os
import sys
import re
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

# Folders where models/entities typically live
MODEL_FOLDERS = [
    'models', 'model', 'entities', 'entity', 'schemas', 'schema',
    'types', 'interfaces', 'domain', 'domains',
    'src/models', 'src/entities', 'src/types', 'src/domain',
    'app/models', 'app/entities', 'lib/models',
    'server/models', 'api/models', 'backend/models',
    'prisma', 'db', 'database',
]

# Common field types and what they mean in business terms
FIELD_TYPE_MEANINGS = {
    'id': 'Unique identifier',
    'uuid': 'Unique identifier',
    'created_at': 'When this was created',
    'createdAt': 'When this was created',
    'updated_at': 'When this was last modified',
    'updatedAt': 'When this was last modified',
    'status': 'Current state/status',
    'email': 'Email address',
    'password': 'Password (should be hashed)',
    'username': 'Username for login',
    'firstName': 'First name',
    'lastName': 'Last name',
    'name': 'Name',
    'phone': 'Phone number',
    'price': 'Price/cost',
    'amount': 'Monetary amount',
    'total': 'Total amount',
    'quantity': 'Number of items',
    'title': 'Title/heading',
    'description': 'Description/details',
    'address': 'Physical address',
    'city': 'City',
    'state': 'State/province',
    'country': 'Country',
}

# Folders to skip
SKIP_FOLDERS = {
    'node_modules', '.git', '__pycache__', '.next', 'dist', 'build',
    'coverage', 'vendor', 'venv', '.venv', 'env', '.env',
}


# ============================================================================
# TRANSLATOR CLASS
# ============================================================================

class Translator:
    """Translates code into business terminology."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.entities = {}
        self.relationships = []
        self.naming_issues = []
        
    def analyze(self):
        """Run the full analysis."""
        
        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")
        
        self._find_model_files()
        self._detect_naming_issues()
        self._infer_relationships()
        
        return self._build_result()
    
    def _find_model_files(self):
        """Find and parse model/entity files."""
        
        for folder_name in MODEL_FOLDERS:
            folder_path = self.root_path / folder_name
            if folder_path.exists() and folder_path.is_dir():
                self._scan_folder_for_models(folder_path)
    
    def _scan_folder_for_models(self, folder):
        """Scan a folder for model files."""
        
        try:
            entries = list(folder.iterdir())
        except PermissionError:
            return
        
        for entry in entries:
            if entry.name in SKIP_FOLDERS:
                continue
                
            if entry.is_file():
                if entry.suffix in ['.ts', '.js', '.py', '.prisma']:
                    self._parse_model_file(entry)
    
    def _parse_model_file(self, file_path):
        """Parse a model file and extract entity information."""
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except:
            return
        
        ext = file_path.suffix.lower()
        
        if ext in ['.ts', '.tsx', '.js', '.jsx']:
            self._parse_typescript_model(file_path, content)
        elif ext == '.py':
            self._parse_python_model(file_path, content)
        elif ext == '.prisma':
            self._parse_prisma_schema(file_path, content)
    
    def _parse_typescript_model(self, file_path, content):
        """Parse TypeScript model files."""
        
        patterns = [
            r'(?:export\s+)?interface\s+(\w+)\s*(?:extends\s+[\w\s,<>]+)?\s*\{([^}]*)\}',
            r'(?:export\s+)?type\s+(\w+)\s*=\s*\{([^}]*)\}',
            r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{([^}]*)\}',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.DOTALL)
            for match in matches:
                entity_name = match.group(1)
                body = match.group(2)
                
                if entity_name.endswith('Props') or entity_name.endswith('Options'):
                    continue
                
                fields = self._extract_typescript_fields(body)
                
                if fields:
                    self._add_entity(entity_name, file_path, fields)
    
    def _extract_typescript_fields(self, body):
        """Extract fields from TypeScript body."""
        
        fields = []
        field_pattern = r'(\w+)\s*\??\s*:\s*([^;,\n]+)'
        matches = re.finditer(field_pattern, body)
        
        for match in matches:
            field_name = match.group(1)
            field_type = match.group(2).strip()
            
            if '(' in field_type and ')' in field_type:
                continue
            
            meaning = self._get_field_meaning(field_name, field_type)
            
            fields.append({
                'name': field_name,
                'type': field_type,
                'meaning': meaning,
            })
        
        return fields
    
    def _parse_python_model(self, file_path, content):
        """Parse Python model files."""
        
        class_pattern = r'class\s+(\w+)\s*\(([^)]*)\)\s*:((?:\n(?:\s+.+)?)*)'
        matches = re.finditer(class_pattern, content)
        
        for match in matches:
            entity_name = match.group(1)
            parent_classes = match.group(2)
            body = match.group(3)
            
            model_indicators = ['Model', 'Base', 'Schema', 'Entity', 'Table']
            if not any(ind in parent_classes for ind in model_indicators):
                if 'Column(' not in body and 'Field(' not in body:
                    continue
            
            fields = self._extract_python_fields(body)
            
            if fields:
                self._add_entity(entity_name, file_path, fields)
    
    def _extract_python_fields(self, body):
        """Extract fields from Python class body."""
        
        fields = []
        patterns = [
            r'(\w+)\s*[=:]\s*(?:Column|Field|models\.\w+)\s*\(',
            r'(\w+)\s*:\s*(\w+(?:\[[\w,\s]+\])?)\s*(?:=|$)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, body)
            for match in matches:
                field_name = match.group(1)
                field_type = match.group(2) if len(match.groups()) > 1 else 'unknown'
                
                if field_name.startswith('_'):
                    continue
                
                meaning = self._get_field_meaning(field_name, field_type)
                
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'meaning': meaning,
                })
        
        return fields
    
    def _parse_prisma_schema(self, file_path, content):
        """Parse Prisma schema files."""
        
        model_pattern = r'model\s+(\w+)\s*\{([^}]+)\}'
        matches = re.finditer(model_pattern, content)
        
        for match in matches:
            entity_name = match.group(1)
            body = match.group(2)
            
            fields = []
            field_pattern = r'^\s*(\w+)\s+(\w+(?:\[\])?(?:\?)?)\s*(.*)$'
            
            for line in body.split('\n'):
                field_match = re.match(field_pattern, line)
                if field_match:
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    
                    meaning = self._get_field_meaning(field_name, field_type)
                    
                    fields.append({
                        'name': field_name,
                        'type': field_type,
                        'meaning': meaning,
                    })
            
            if fields:
                self._add_entity(entity_name, file_path, fields)
    
    def _get_field_meaning(self, field_name, field_type):
        """Get the business meaning of a field."""
        
        lower_name = field_name.lower()
        
        if lower_name in FIELD_TYPE_MEANINGS:
            return FIELD_TYPE_MEANINGS[lower_name]
        
        for key, meaning in FIELD_TYPE_MEANINGS.items():
            if key.lower() in lower_name:
                return meaning
        
        if lower_name.endswith('_id') or lower_name.endswith('id'):
            ref_name = lower_name.replace('_id', '').replace('id', '')
            if ref_name:
                return f"Reference to {ref_name}"
        
        return "Purpose unclear - needs review"
    
    def _add_entity(self, name, file_path, fields):
        """Add an entity to our collection."""
        
        description = self._generate_entity_description(name, fields)
        
        self.entities[name] = {
            'name': name,
            'file': str(file_path.relative_to(self.root_path)),
            'fields': fields,
            'description': description,
        }
    
    def _generate_entity_description(self, name, fields):
        """Generate a plain English description of an entity."""
        
        patterns = {
            'user': "Represents a person who can log into the system",
            'customer': "Represents a customer who makes purchases",
            'order': "Represents a purchase order",
            'product': "Represents an item that can be purchased",
            'cart': "Represents a shopping cart",
            'payment': "Represents a payment transaction",
            'account': "Represents a user or business account",
            'profile': "Represents user profile information",
            'address': "Represents a physical address",
            'category': "Represents a grouping/category",
            'comment': "Represents a user comment",
            'review': "Represents a product or service review",
            'notification': "Represents a user notification",
            'message': "Represents a message between users",
            'session': "Represents a user login session",
        }
        
        name_lower = name.lower()
        
        for pattern, desc in patterns.items():
            if pattern in name_lower:
                return desc
        
        return "Purpose unclear - needs human review"
    
    def _detect_naming_issues(self):
        """Detect potential naming inconsistencies."""
        
        entity_names = list(self.entities.keys())
        
        similar_groups = [
            ['User', 'Users', 'Account', 'Accounts', 'Member', 'Members'],
            ['Customer', 'Customers', 'Client', 'Clients'],
            ['Order', 'Orders', 'Purchase', 'Purchases'],
            ['Product', 'Products', 'Item', 'Items'],
        ]
        
        for group in similar_groups:
            found = [name for name in entity_names if name in group]
            if len(found) > 1:
                self.naming_issues.append({
                    'entities': found,
                    'message': f"These might represent the same concept: {', '.join(found)}",
                })
    
    def _infer_relationships(self):
        """Infer relationships between entities."""
        
        for entity_name, entity in self.entities.items():
            for field in entity['fields']:
                field_name = field['name'].lower()
                
                if field_name.endswith('_id') or field_name.endswith('id'):
                    ref_name = field_name.replace('_id', '').replace('id', '')
                    
                    for other_name in self.entities.keys():
                        if other_name.lower() == ref_name:
                            self.relationships.append({
                                'from': entity_name,
                                'to': other_name,
                                'via': field['name'],
                            })
    
    def _build_result(self):
        """Build the final analysis result."""
        
        return {
            'path': str(self.root_path),
            'analyzed_at': datetime.now().isoformat(),
            'entity_count': len(self.entities),
            'entities': self.entities,
            'relationships': self.relationships,
            'naming_issues': self.naming_issues,
        }


# ============================================================================
# REPORT GENERATOR
# ============================================================================

def generate_report(result):
    """Generate a human-readable markdown report."""
    
    report = []
    
    report.append("# Business Dictionary")
    report.append("")
    report.append(f"**Codebase:** {result['path']}")
    report.append(f"**Generated:** {result['analyzed_at']}")
    report.append("")
    
    report.append("---")
    report.append("")
    report.append("## Summary")
    report.append("")
    report.append(f"Found **{result['entity_count']}** business entities.")
    report.append("")
    
    if result['entities']:
        report.append("---")
        report.append("")
        report.append("## Business Entities")
        report.append("")
        
        for name, entity in sorted(result['entities'].items()):
            report.append(f"### {name}")
            report.append("")
            report.append(f"**What it is:** {entity['description']}")
            report.append("")
            report.append(f"**File:** `{entity['file']}`")
            report.append("")
            
            if entity['fields']:
                report.append("| Field | Type | Meaning |")
                report.append("|-------|------|---------|")
                
                for field in entity['fields'][:10]:
                    report.append(f"| {field['name']} | {field['type']} | {field['meaning']} |")
                
                report.append("")
    else:
        report.append("No entities found. Manual review needed.")
        report.append("")
    
    if result['relationships']:
        report.append("---")
        report.append("")
        report.append("## Relationships")
        report.append("")
        report.append("| From | To | Via |")
        report.append("|------|-----|-----|")
        
        for rel in result['relationships']:
            report.append(f"| {rel['from']} | {rel['to']} | {rel['via']} |")
        
        report.append("")
    
    if result['naming_issues']:
        report.append("---")
        report.append("")
        report.append("## Naming Issues")
        report.append("")
        
        for issue in result['naming_issues']:
            report.append(f"- [!] {issue['message']}")
        
        report.append("")
    
    report.append("---")
    report.append("")
    report.append("## Next Steps")
    report.append("")
    report.append("1. Review entities marked 'unclear'")
    report.append("2. Clarify naming issues with the team")
    report.append("3. Run the **Flow Tracer Agent** next")
    report.append("")
    
    return "\n".join(report)


# ============================================================================
# MAIN
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python translator.py /path/to/codebase [--output glossary.md]")
        sys.exit(1)
    
    codebase_path = sys.argv[1]
    output_file = None
    
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    print(f" Translator analyzing: {codebase_path}")
    print("")
    
    try:
        translator = Translator(codebase_path)
        result = translator.analyze()
        report = generate_report(result)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            print(f"[OK] Dictionary saved to: {output_file}")
            print(f"   Found {result['entity_count']} entities")
        else:
            print(report)
            
    except Exception as e:
        print(f"[X] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
