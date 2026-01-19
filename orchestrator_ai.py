#!/usr/bin/env python3
"""
RS10X ORCHESTRATOR AI
=====================
Coordinates all analysis agents and manages the workflow.

This orchestrator:
1. Receives a codebase path
2. Runs each agent in sequence
3. Collects and aggregates results
4. Handles errors gracefully
5. Reports progress throughout

Usage:
    python orchestrator_ai.py /path/to/codebase --output /path/to/reports --question "Your question"
"""

import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Callable

# Try to import anthropic for AI-powered orchestration decisions
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class OrchestratorAI:
    """AI-powered orchestrator for codebase analysis."""
    
    def __init__(self, codebase_path: str, output_dir: str, question: str = ""):
        self.codebase_path = Path(codebase_path)
        self.output_dir = Path(output_dir)
        self.question = question
        self.agents_dir = Path(__file__).parent
        self.python_cmd = self._get_python_cmd()
        
        # Initialize Anthropic client if available
        self.client = None
        if ANTHROPIC_AVAILABLE and os.environ.get('ANTHROPIC_API_KEY'):
            self.client = anthropic.Anthropic()
        
        # Agent configuration
        self.agents = [
            {
                'name': 'Bouncer',
                'script': 'bouncer.py',
                'output': 'bouncer_report.md',
                'description': 'Validates codebase health and structure',
                'timeout': 60,
                'required': True
            },
            {
                'name': 'Map Maker',
                'script': 'map_maker.py',
                'output': 'map_report.md',
                'description': 'Creates folder structure map',
                'timeout': 120,
                'required': True
            },
            {
                'name': 'Translator',
                'script': 'translator_ai.py',
                'fallback': 'translator.py',
                'output': 'translator_report.md',
                'description': 'Creates business-readable dictionary',
                'timeout': 300,
                'required': True
            },
            {
                'name': 'Flow Tracer',
                'script': 'flow_tracer.py',
                'output': 'flow_report.md',
                'description': 'Traces data flows through the system',
                'timeout': 300,
                'required': True
            },
            {
                'name': 'Risk Spotter',
                'script': 'risk_spotter.py',
                'output': 'risk_report.md',
                'description': 'Identifies technical and business risks',
                'timeout': 300,
                'required': True
            },
            {
                'name': 'Safety Inspector',
                'script': 'safety_inspector.py',
                'output': 'safety_report.md',
                'description': 'Evaluates test coverage and code safety',
                'timeout': 180,
                'required': True
            }
        ]
        
        # Results storage
        self.results = {
            'started_at': None,
            'completed_at': None,
            'agents': {},
            'summary': None,
            'errors': [],
            'warnings': []
        }
    
    def _get_python_cmd(self) -> str:
        """Get the right Python command for this system."""
        for cmd in ['python3', 'python', 'py']:
            try:
                result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return cmd
            except:
                continue
        return 'python3'
    
    def _log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"INFO": "[INFO]", "SUCCESS": "[OK]", "ERROR": "[ERROR]", "WARNING": "[WARN]", "PROGRESS": "[...]"}.get(level, "[*]")
        print(f"[{timestamp}] {prefix} {message}")
    
    def _run_agent(self, agent: Dict, progress_callback: Optional[Callable] = None) -> Dict:
        """Run a single agent and return results."""
        agent_name = agent['name']
        script_name = agent['script']
        output_file = self.output_dir / agent['output']
        
        # Find the script (try primary, then fallback)
        script_path = self.agents_dir / script_name
        if not script_path.exists() and 'fallback' in agent:
            script_path = self.agents_dir / agent['fallback']
            self._log(f"Using fallback script for {agent_name}", "WARNING")
        
        if not script_path.exists():
            return {
                'status': 'skipped',
                'error': f"Script not found: {script_name}",
                'output': None
            }
        
        self._log(f"Running {agent_name}: {agent['description']}", "PROGRESS")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [self.python_cmd, str(script_path), str(self.codebase_path), '--output', str(output_file)],
                capture_output=True,
                timeout=agent['timeout'],
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                encoding='utf-8',
                errors='replace'
            )
            
            elapsed = time.time() - start_time
            
            if result.returncode == 0:
                # Read the output file if it exists
                output_content = None
                if output_file.exists():
                    output_content = output_file.read_text(encoding='utf-8', errors='ignore')
                
                self._log(f"{agent_name} completed in {elapsed:.1f}s", "SUCCESS")
                return {
                    'status': 'success',
                    'elapsed_time': elapsed,
                    'output_file': str(output_file),
                    'output_content': output_content,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
            else:
                self._log(f"{agent_name} failed with code {result.returncode}", "ERROR")
                return {
                    'status': 'failed',
                    'elapsed_time': elapsed,
                    'error': result.stderr or result.stdout,
                    'return_code': result.returncode
                }
                
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            self._log(f"{agent_name} timed out after {agent['timeout']}s", "ERROR")
            return {
                'status': 'timeout',
                'elapsed_time': elapsed,
                'error': f"Timed out after {agent['timeout']} seconds"
            }
        except Exception as e:
            elapsed = time.time() - start_time
            self._log(f"{agent_name} error: {str(e)}", "ERROR")
            return {
                'status': 'error',
                'elapsed_time': elapsed,
                'error': str(e)
            }
    
    def _generate_executive_summary(self) -> str:
        """Generate an executive summary using AI or template."""
        
        # Collect all report contents
        reports = {}
        for agent in self.agents:
            output_file = self.output_dir / agent['output']
            if output_file.exists():
                reports[agent['name']] = output_file.read_text(encoding='utf-8', errors='ignore')
        
        if not reports:
            return "No reports generated - analysis may have failed."
        
        # If we have AI available, generate intelligent summary
        if self.client:
            try:
                reports_text = "\n\n---\n\n".join([
                    f"## {name} Report\n\n{content[:5000]}"  # Limit each report
                    for name, content in reports.items()
                ])
                
                prompt = f"""You are an expert code analyst. Based on the following analysis reports, 
generate a concise executive summary for a non-technical audience (PE firm, business stakeholders).

Question/Focus: {self.question if self.question else 'General codebase health assessment'}

Reports:
{reports_text}

Provide:
1. Overall Assessment (1 paragraph)
2. Key Strengths (3-5 bullet points)
3. Critical Risks (3-5 bullet points)  
4. Recommendation (Buy/Pass/Investigate Further with brief rationale)

Keep it under 500 words. Be direct and actionable."""

                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                return response.content[0].text
                
            except Exception as e:
                self._log(f"AI summary generation failed: {e}", "WARNING")
        
        # Fallback: template-based summary
        summary_parts = [
            "# Executive Summary",
            "",
            f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Codebase: {self.codebase_path}",
            "",
            "## Reports Generated",
            ""
        ]
        
        for agent in self.agents:
            status = self.results['agents'].get(agent['name'], {}).get('status', 'unknown')
            summary_parts.append(f"- {agent['name']}: {status}")
        
        if self.results['errors']:
            summary_parts.extend([
                "",
                "## Errors Encountered",
                ""
            ])
            for error in self.results['errors']:
                summary_parts.append(f"- {error}")
        
        summary_parts.extend([
            "",
            "## Next Steps",
            "",
            "Review individual reports for detailed findings.",
            "Consider the identified risks before proceeding with acquisition."
        ])
        
        return "\n".join(summary_parts)
    
    def run(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Run the full analysis pipeline."""
        
        self._log("=" * 50)
        self._log("RS10X ORCHESTRATOR AI")
        self._log("=" * 50)
        self._log(f"Codebase: {self.codebase_path}")
        self._log(f"Output: {self.output_dir}")
        self._log(f"Question: {self.question or 'General analysis'}")
        self._log(f"AI Available: {'Yes' if self.client else 'No'}")
        self._log("=" * 50)
        
        self.results['started_at'] = datetime.now().isoformat()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate codebase exists
        if not self.codebase_path.exists():
            self._log(f"Codebase not found: {self.codebase_path}", "ERROR")
            self.results['errors'].append(f"Codebase not found: {self.codebase_path}")
            return self.results
        
        # Run each agent
        total_agents = len(self.agents)
        for i, agent in enumerate(self.agents):
            progress = int((i / total_agents) * 100)
            
            if progress_callback:
                progress_callback(progress, f"Running {agent['name']}")
            
            result = self._run_agent(agent)
            self.results['agents'][agent['name']] = result
            
            # Track errors
            if result['status'] in ['failed', 'error', 'timeout']:
                error_msg = f"{agent['name']}: {result.get('error', 'Unknown error')}"
                self.results['errors'].append(error_msg)
                
                # Stop if required agent failed
                if agent['required']:
                    self._log(f"Required agent {agent['name']} failed - continuing anyway", "WARNING")
        
        # Generate executive summary
        self._log("Generating executive summary...", "PROGRESS")
        summary = self._generate_executive_summary()
        self.results['summary'] = summary
        
        # Save summary to file
        summary_file = self.output_dir / 'executive_summary.md'
        summary_file.write_text(summary, encoding='utf-8')
        self._log(f"Summary saved to {summary_file}", "SUCCESS")
        
        # Generate final report
        self._generate_final_report()
        
        self.results['completed_at'] = datetime.now().isoformat()
        
        # Calculate totals
        total_time = sum(
            r.get('elapsed_time', 0) 
            for r in self.results['agents'].values()
        )
        successful = sum(
            1 for r in self.results['agents'].values() 
            if r.get('status') == 'success'
        )
        
        self._log("=" * 50)
        self._log(f"Analysis Complete")
        self._log(f"Agents: {successful}/{total_agents} successful")
        self._log(f"Total time: {total_time:.1f}s")
        self._log(f"Errors: {len(self.results['errors'])}")
        self._log("=" * 50)
        
        if progress_callback:
            progress_callback(100, "Complete")
        
        return self.results
    
    def _generate_final_report(self):
        """Generate a consolidated final report."""
        
        report_parts = [
            "# RS10X Codebase Analysis Report",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Codebase: {self.codebase_path}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            self.results.get('summary', 'No summary available.'),
            "",
            "---",
            ""
        ]
        
        # Add each agent's report
        for agent in self.agents:
            output_file = self.output_dir / agent['output']
            if output_file.exists():
                content = output_file.read_text(encoding='utf-8', errors='ignore')
                report_parts.extend([
                    f"## {agent['name']} Report",
                    "",
                    content,
                    "",
                    "---",
                    ""
                ])
        
        # Save consolidated report
        final_report = self.output_dir / 'FULL_ANALYSIS_REPORT.md'
        final_report.write_text("\n".join(report_parts), encoding='utf-8')
        self._log(f"Full report saved to {final_report}", "SUCCESS")


def main():
    parser = argparse.ArgumentParser(description='RS10X Orchestrator AI')
    parser.add_argument('codebase', help='Path to codebase to analyze')
    parser.add_argument('--output', '-o', default='./reports', help='Output directory for reports')
    parser.add_argument('--question', '-q', default='', help='Specific question to focus analysis on')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    orchestrator = OrchestratorAI(
        codebase_path=args.codebase,
        output_dir=args.output,
        question=args.question
    )
    
    results = orchestrator.run()
    
    if args.json:
        # Remove large content for JSON output
        json_results = {
            'started_at': results['started_at'],
            'completed_at': results['completed_at'],
            'agents': {
                name: {k: v for k, v in data.items() if k != 'output_content'}
                for name, data in results['agents'].items()
            },
            'errors': results['errors'],
            'warnings': results['warnings']
        }
        print(json.dumps(json_results, indent=2))
    
    # Exit with error code if any required agents failed
    failed_required = any(
        results['agents'].get(a['name'], {}).get('status') in ['failed', 'error', 'timeout']
        for a in orchestrator.agents if a['required']
    )
    
    sys.exit(1 if failed_required else 0)


if __name__ == '__main__':
    main()
