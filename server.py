#!/usr/bin/env python3
"""
RS10X CODE ANALYSIS SERVER - Railway Deployment
================================================
Flask backend for codebase analysis.

Deploy to Railway:
1. Push this folder to GitHub
2. Connect Railway to your repo
3. Set ANTHROPIC_API_KEY in Railway environment variables
4. Deploy

Environment Variables (set in Railway):
- ANTHROPIC_API_KEY: Your Anthropic API key
- PORT: Automatically set by Railway
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")  # Allow all origins for now

# Store analysis progress and results
analysis_jobs = {}

# Path to agents directory
AGENTS_DIR = Path(__file__).parent

def get_python_cmd():
    """Get the right Python command for this system."""
    for cmd in ['python3', 'python', 'py']:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return cmd
        except:
            continue
    return 'python3'

PYTHON_CMD = get_python_cmd()


def run_analysis(job_id: str, codebase_path: str, question: str):
    """Run all agents and update progress."""
    job = analysis_jobs[job_id]
    
    agents = [
        ('bouncer.py', 'bouncer_report.md', 'Checking codebase health', 10),
        ('map_maker.py', 'map_report.md', 'Mapping folder structure', 25),
        ('translator_ai.py', 'translator_report.md', 'Creating business dictionary', 45),
        ('flow_tracer.py', 'flow_report.md', 'Tracing data flows', 60),
        ('risk_spotter.py', 'risk_report.md', 'Identifying risks', 75),
        ('safety_inspector.py', 'safety_report.md', 'Checking test coverage', 90),
    ]
    
    output_dir = Path(job['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        for agent_script, report_file, status_msg, progress in agents:
            job['status'] = status_msg
            job['progress'] = progress - 10
            
            script_path = AGENTS_DIR / agent_script
            
            # Fall back to non-AI version if needed
            if not script_path.exists():
                fallback = agent_script.replace('_ai.py', '.py')
                script_path = AGENTS_DIR / fallback
            
            if script_path.exists():
                output_file = str(output_dir / report_file)
                try:
                    result = subprocess.run(
                        [PYTHON_CMD, str(script_path), codebase_path, '--output', output_file],
                        capture_output=True,
                        timeout=300,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                        encoding='utf-8',
                        errors='replace'
                    )
                    job['agents_completed'].append(agent_script.replace('.py', '').replace('_', ' ').title())
                except Exception as e:
                    job['errors'].append(f"{agent_script}: {str(e)}")
            
            job['progress'] = progress
            time.sleep(0.3)
        
        # Run summary writer if question provided
        if question:
            job['status'] = 'Generating executive brief'
            job['progress'] = 95
            
            summary_script = AGENTS_DIR / 'summary_writer.py'
            if summary_script.exists():
                try:
                    result = subprocess.run(
                        [PYTHON_CMD, str(summary_script), str(output_dir), 
                         '--question', question, 
                         '--output', str(output_dir / 'executive_brief.md')],
                        capture_output=True,
                        timeout=120,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                        encoding='utf-8',
                        errors='replace'
                    )
                except Exception as e:
                    job['errors'].append(f"summary_writer: {str(e)}")
        
        job['progress'] = 100
        job['status'] = 'Analysis complete'
        job['completed'] = True
        job['completed_at'] = datetime.now().isoformat()
        
        # Collect all report contents
        job['reports'] = {}
        for _, report_file, _, _ in agents:
            report_path = output_dir / report_file
            if report_path.exists():
                job['reports'][report_file] = report_path.read_text(encoding='utf-8', errors='ignore')
        
        # Add executive brief if exists
        brief_path = output_dir / 'executive_brief.md'
        if brief_path.exists():
            job['reports']['executive_brief.md'] = brief_path.read_text(encoding='utf-8', errors='ignore')
        
    except Exception as e:
        job['status'] = f'Error: {str(e)}'
        job['error'] = str(e)
        job['completed'] = True


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Start a new analysis job."""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    question = request.form.get('question', '')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Create job
    job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
    
    # Create temp directories
    temp_dir = tempfile.mkdtemp()
    upload_path = os.path.join(temp_dir, 'upload')
    extract_path = os.path.join(temp_dir, 'codebase')
    output_path = os.path.join(temp_dir, 'reports')
    
    os.makedirs(upload_path, exist_ok=True)
    os.makedirs(extract_path, exist_ok=True)
    os.makedirs(output_path, exist_ok=True)
    
    # Save uploaded file
    filename = file.filename
    file_path = os.path.join(upload_path, filename)
    file.save(file_path)
    
    # Extract if zip
    codebase_path = extract_path
    if filename.endswith('.zip'):
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Check if zip contained a single folder
            items = os.listdir(extract_path)
            if len(items) == 1 and os.path.isdir(os.path.join(extract_path, items[0])):
                codebase_path = os.path.join(extract_path, items[0])
        except Exception as e:
            return jsonify({'error': f'Failed to extract zip: {str(e)}'}), 400
    else:
        # Single file - just analyze the upload directory
        shutil.move(file_path, os.path.join(extract_path, filename))
    
    # Initialize job
    analysis_jobs[job_id] = {
        'id': job_id,
        'status': 'Starting analysis',
        'progress': 0,
        'completed': False,
        'question': question,
        'temp_dir': temp_dir,
        'output_dir': output_path,
        'codebase_path': codebase_path,
        'agents_completed': [],
        'errors': [],
        'reports': {},
        'created_at': datetime.now().isoformat()
    }
    
    # Start analysis in background
    thread = threading.Thread(target=run_analysis, args=(job_id, codebase_path, question))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Get analysis job status."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    return jsonify({
        'id': job['id'],
        'status': job['status'],
        'progress': job['progress'],
        'completed': job['completed'],
        'agents_completed': job['agents_completed'],
        'errors': job['errors']
    })


@app.route('/api/results/<job_id>', methods=['GET'])
def get_results(job_id):
    """Get analysis results."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    
    if not job['completed']:
        return jsonify({'error': 'Analysis not complete'}), 400
    
    return jsonify({
        'id': job['id'],
        'reports': job['reports'],
        'question': job['question'],
        'completed_at': job.get('completed_at'),
        'errors': job['errors']
    })


@app.route('/api/download/<job_id>/<report_name>', methods=['GET'])
def download_report(job_id, report_name):
    """Download a specific report."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    report_path = Path(job['output_dir']) / report_name
    
    if not report_path.exists():
        return jsonify({'error': 'Report not found'}), 404
    
    return send_file(report_path, as_attachment=True, download_name=report_name)


@app.route('/api/download-all/<job_id>', methods=['GET'])
def download_all(job_id):
    """Download all reports as zip."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    output_dir = Path(job['output_dir'])
    
    # Create zip file
    zip_path = output_dir.parent / 'analysis_reports.zip'
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for report_file in output_dir.iterdir():
            if report_file.is_file():
                zipf.write(report_file, report_file.name)
    
    return send_file(zip_path, as_attachment=True, download_name='analysis_reports.zip')


@app.route('/api/ask/<job_id>', methods=['POST'])
def ask_followup(job_id):
    """Ask a follow-up question about the analyzed codebase."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    
    if not job['completed']:
        return jsonify({'error': 'Analysis not complete'}), 400
    
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Run summary writer with new question
    output_dir = Path(job['output_dir'])
    summary_script = AGENTS_DIR / 'summary_writer.py'
    
    if not summary_script.exists():
        return jsonify({'error': 'Summary writer not available'}), 500
    
    try:
        result = subprocess.run(
            [PYTHON_CMD, str(summary_script), str(output_dir), '--question', question],
            capture_output=True,
            timeout=120,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            encoding='utf-8',
            errors='replace'
        )
        
        answer = result.stdout
        
        if 'EXECUTIVE BRIEF' in answer:
            lines = answer.split('\n')
            start_idx = 0
            for i, line in enumerate(lines):
                if '=' * 20 in line and i > 5:
                    start_idx = i + 1
                    break
            answer = '\n'.join(lines[start_idx:])
        
        return jsonify({
            'question': question,
            'answer': answer.strip()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/cleanup/<job_id>', methods=['DELETE'])
def cleanup(job_id):
    """Clean up job temp files."""
    if job_id not in analysis_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = analysis_jobs[job_id]
    
    try:
        if 'temp_dir' in job and os.path.exists(job['temp_dir']):
            shutil.rmtree(job['temp_dir'])
        del analysis_jobs[job_id]
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    """Health check."""
    return jsonify({
        'service': 'RS10X Code Analysis API',
        'status': 'running',
        'version': '1.0.0',
        'api_key_set': bool(os.environ.get('ANTHROPIC_API_KEY'))
    })


@app.route('/health')
def health():
    """Health check endpoint for Railway."""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 50)
    print("RS10X CODE ANALYSIS SERVER")
    print("=" * 50)
    print(f"Python: {PYTHON_CMD}")
    print(f"Port: {port}")
    print(f"API Key: {'Set' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET'}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=False)
