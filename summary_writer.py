#!/usr/bin/env python3
"""
SUMMARY WRITER AGENT
====================
Creates a 1-page executive brief in prose style based on all agent reports
and a specific user question.

This agent reads all existing reports and uses AI to synthesize them into
a readable narrative that directly answers the user's question.

Usage:
    py summary_writer.py C:\codebase-agents\reports --question "Is this ready to scale to 100k users?"
    py summary_writer.py C:\codebase-agents\reports --question "What are the biggest risks?" --output summary.md

Requires:
    pip install anthropic
    set ANTHROPIC_API_KEY=your-key
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Check for API key
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

if ANTHROPIC_API_KEY:
    try:
        import anthropic
        HAS_ANTHROPIC = True
    except ImportError:
        HAS_ANTHROPIC = False
else:
    HAS_ANTHROPIC = False


# Reports to read (in order of importance)
REPORT_FILES = [
    ('bouncer_report.md', 'Health Check'),
    ('map_report.md', 'Codebase Structure'),
    ('translator_report.md', 'Business Entities'),
    ('risk_report.md', 'Risk Analysis'),
    ('safety_report.md', 'Test Coverage'),
    ('flow_report.md', 'API & Data Flows'),
]


def load_reports(reports_dir: Path) -> dict:
    """Load all available reports."""
    reports = {}
    
    for filename, label in REPORT_FILES:
        filepath = reports_dir / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                reports[label] = content
            except Exception as e:
                reports[label] = f"[Could not read: {e}]"
        else:
            reports[label] = "[Report not found]"
    
    return reports


def generate_summary_with_ai(reports: dict, question: str) -> str:
    """Use Claude to generate a prose executive summary."""
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Build context from all reports
    reports_context = ""
    for label, content in reports.items():
        # Truncate very long reports
        if len(content) > 8000:
            content = content[:8000] + "\n\n[... truncated for brevity ...]"
        reports_context += f"\n\n=== {label} ===\n{content}"
    
    prompt = f"""You are a senior technical consultant writing an executive brief for a client.

You have analyzed a codebase using multiple specialized tools. Below are the reports from each analysis.

The client's specific question is: "{question}"

Based on ALL the reports below, write a 1-page executive summary that:

1. DIRECTLY answers their question in the first paragraph
2. Provides supporting evidence from the analysis
3. Identifies the top 3 concerns or recommendations
4. Ends with a clear verdict/recommendation

STYLE REQUIREMENTS:
- Write in flowing prose paragraphs, like a well-written business memo
- NO bullet points, NO tables, NO markdown headers
- NO technical jargon without explanation
- Write as if explaining to a smart business person, not a developer
- Be direct and confident in your assessment
- Keep it to roughly 400-600 words (one page when printed)

Here are the analysis reports:
{reports_context}

Now write the executive summary addressing: "{question}"
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text


def generate_summary_basic(reports: dict, question: str) -> str:
    """Generate a basic summary without AI."""
    
    lines = [
        "EXECUTIVE SUMMARY",
        "=" * 50,
        "",
        f"Question: {question}",
        "",
        "NOTE: This is a basic summary. For a detailed prose analysis,",
        "set your ANTHROPIC_API_KEY environment variable.",
        "",
        "-" * 50,
        "",
    ]
    
    # Extract key metrics from reports
    health_report = reports.get('Health Check', '')
    risk_report = reports.get('Risk Analysis', '')
    safety_report = reports.get('Test Coverage', '')
    
    # Try to find health score
    if 'READY FOR ANALYSIS' in health_report:
        lines.append("Codebase Status: HEALTHY - Ready for analysis")
    elif 'NOT READY' in health_report:
        lines.append("Codebase Status: ISSUES FOUND - Needs attention")
    else:
        lines.append("Codebase Status: Unknown")
    
    lines.append("")
    
    # Try to find coverage
    if 'Estimated Coverage:' in safety_report:
        for line in safety_report.split('\n'):
            if 'Estimated Coverage:' in line:
                lines.append(f"Test Coverage: {line.split(':**')[1].strip() if ':**' in line else 'See report'}")
                break
    
    lines.append("")
    lines.append("-" * 50)
    lines.append("")
    lines.append("To get a full AI-powered executive summary that directly")
    lines.append("answers your question, run:")
    lines.append("")
    lines.append("  set ANTHROPIC_API_KEY=your-key")
    lines.append("  py summary_writer.py [reports_dir] --question \"your question\"")
    lines.append("")
    
    return "\n".join(lines)


def format_final_report(summary: str, question: str, reports_dir: str) -> str:
    """Format the final report with header."""
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    output = f"""EXECUTIVE BRIEF
{"=" * 60}

Prepared: {timestamp}
Reports Source: {reports_dir}

Client Question: {question}

{"=" * 60}

{summary}

{"=" * 60}
End of Executive Brief

Supporting documentation available in:
- bouncer_report.md (Health Check)
- map_report.md (Structure Analysis)
- translator_report.md (Business Dictionary)
- risk_report.md (Risk Assessment)
- safety_report.md (Test Coverage)
- flow_report.md (Data Flows)
"""
    
    return output


def main():
    if len(sys.argv) < 2:
        print("=" * 60)
        print("SUMMARY WRITER - Executive Brief Generator")
        print("=" * 60)
        print("")
        print("Usage:")
        print("  py summary_writer.py [reports_dir] --question \"Your question here\"")
        print("")
        print("Examples:")
        print("  py summary_writer.py .\\reports --question \"Is this ready to scale to 100k users?\"")
        print("  py summary_writer.py .\\reports --question \"What are the biggest technical risks?\"")
        print("  py summary_writer.py .\\reports --question \"Should we acquire this codebase?\"")
        print("")
        print("Options:")
        print("  --output FILE    Save to file instead of printing")
        print("")
        print("Requires ANTHROPIC_API_KEY for AI-powered summaries.")
        print("")
        sys.exit(1)
    
    reports_dir = Path(sys.argv[1])
    
    # Parse question
    question = None
    if '--question' in sys.argv:
        idx = sys.argv.index('--question')
        if idx + 1 < len(sys.argv):
            question = sys.argv[idx + 1]
    
    if not question:
        print("[ERROR] Please provide a question with --question \"Your question\"")
        sys.exit(1)
    
    # Parse output file
    output_file = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]
    
    # Validate reports directory
    if not reports_dir.exists():
        print(f"[ERROR] Reports directory not found: {reports_dir}")
        sys.exit(1)
    
    print("[SUMMARY] Loading analysis reports...")
    reports = load_reports(reports_dir)
    
    found_count = sum(1 for v in reports.values() if '[Report not found]' not in v)
    print(f"[SUMMARY] Found {found_count}/{len(REPORT_FILES)} reports")
    
    if found_count == 0:
        print("[ERROR] No reports found. Run the orchestrator first.")
        sys.exit(1)
    
    print(f"[SUMMARY] Answering: {question}")
    
    # Generate summary
    if HAS_ANTHROPIC and ANTHROPIC_API_KEY:
        print("[SUMMARY] Using AI to generate executive brief...")
        try:
            summary = generate_summary_with_ai(reports, question)
        except Exception as e:
            print(f"[ERROR] AI generation failed: {e}")
            print("[SUMMARY] Falling back to basic summary...")
            summary = generate_summary_basic(reports, question)
    else:
        if not ANTHROPIC_API_KEY:
            print("[SUMMARY] No API key found. Generating basic summary...")
        else:
            print("[SUMMARY] Anthropic library not installed. Generating basic summary...")
        summary = generate_summary_basic(reports, question)
    
    # Format final report
    final_report = format_final_report(summary, question, str(reports_dir))
    
    # Output
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_report)
        print(f"[OK] Executive brief saved to: {output_file}")
    else:
        print("")
        print(final_report)


if __name__ == "__main__":
    main()
