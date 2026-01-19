


#!/usr/bin/env python3
"""
RS10X CODE ANALYSIS SERVER - Railway Deployment
================================================
Flask backend for codebase analysis with Supabase persistence.

Environment Variables (set in Railway):
- ANTHROPIC_API_KEY: Your Anthropic API key
- SUPABASE_URL: Your Supabase project URL
- SUPABASE_KEY: Your Supabase anon/service key
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
from supabase import create_client, Client

app = Flask(__name__)
CORS(app, origins="*")

# Supabase setup
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

if supabase:
    print("✓ Supabase connected")
else:
    print("⚠ Supabase not configured - jobs will not persist!")

# In-memory cache (still needed for temp file paths during analysis)
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


# =============================================================================
# SUPABASE JOB PERSISTENCE
# =============================================================================

def get_job_from_db(job_id: str):
    """Fetch job from Supabase."""
    if not supabase:
        return analysis_jobs.get(job_id)
    try:
        result = supabase.table('analysis_jobs').select('*').eq('job_id', job_id).maybe_single().execute()
        return result.data
    except Exception as e:
        print(f"Error fetching job: {e}")
        return analysis_jobs.get(job_id)


def save_job_to_db(job_id: str, status: str, progress: int, step_name: str = None, completed: bool = False, error: str = None):
    """Update job in Supabase."""
    if not supabase:
        return
    try:
        data = {
            'job_id': job_id,
            'status': 'completed' if completed else ('error' if error else 'analyzing'),
            'current_step': progress // 10,
            'total_steps': 10,
            'current_step_name': step_name or status,
            'progress': progress,
            'completed': completed,
            'updated_at': datetime.now().isoformat()
        }
        if error:
            data['error'] = error
        if completed:
            data['completed_at'] = datetime.now().isoformat()
        
        supabase.table('analysis_jobs').upsert(data, on_conflict='job_id').execute()
    except Exception as e:
        print(f"Error saving job: {e}")


def create_job_in_db(job_id: str, question: str = ''):
    """Create new job in Supabase."""
    if not supabase:
        return
    try:
        supabase.table('analysis_jobs').insert({
            'job_id': job_id,
            'status': 'pending',
            'current_step': 0,
            'total_steps': 10,
            'current_step_name': 'Starting analysis',
            'progress': 0,
            'completed': False,
            'question': question,
            'created_at': datetime.now().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error creating job: {e}")


def save_reports_to_db(job_id: str, reports: dict):
    """Save reports to Supabase."""
    if not supabase:
        return
    try:
        for filename, content in reports.items():
            supabase.table('analysis_reports').upsert({
                'job_id': job_id,
                'filename': filename,
                'content': content
            }, on_conflict='job_id,filename').execute()
    except Exception as e:
        print(f"Error saving reports: {e}")


def get_reports_from_db(job_id: str):
    """Fetch reports from Supabase."""
    if not supabase:
        job = analysis_jobs.get(job_id)
        return job.get('reports', {}) if job else {}
    try:
        result = supabase.table('analysis_reports').select('filename, content').eq('job_id', job_id).execute()
        return {row['filename']: row['content'] for row in result.data} if result.data else {}
    except Exception as e:
        print(f"Error fetching reports: {e}")
        return {}


def delete_job_from_db(job_id: str):
    """Delete job and reports from Supabase."""
    if not supabase:
        return
    try:
        supabase.table('analysis_reports').delete().eq('job_id', job_id).execute()
        supabase.table('analysis_jobs').delete().eq('job_id', job_id).execute()
    except Exception as e:
        print(f"Error deleting job: {e}")


# =============================================================================
# ANALYSIS LOGIC
# =============================================================================

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
            save_job_to_db(job_id, status_msg, progress - 10, status_msg)
            
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
            save_job_to_db(job_id, status_msg, progress, status_msg)
            time.sleep(0.3)
        
        # Run summary writer if question provided
        if question:
            job['status'] = 'Generating executive brief'
            job['progress'] = 95
            save_job_to_db(job_id, 'Generating executive brief', 95, 'Generating executive brief')
            
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
        
        # Save to database
        save_job_to_db(job_id, 'Analysis complete', 100, 'Complete', completed=True)
        save_reports_to_db(job_id, job['reports'])
        
    except Exception as e:
        job['status'] = f'Error: {str(e)}'
        job['error'] = str(e)
        job['completed'] = True
        save_job_to_db(job_id, f'Error: {str(e)}', job['progress'], error=str(e))


# =============================================================================
# API ROUTES
# =============================================================================

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
    
    # Initialize job in memory
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
    
    # Create job in database
    create_job_in_db(job_id, question)
    
    # Start analysis in background
    thread = threading.Thread(target=run_analysis, args=(job_id, codebase_path, question))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Get analysis job status."""
    
    # Try database first
    db_job = get_job_from_db(job_id)
    
    if db_job:
        return jsonify({
            'id': db_job.get('job_id', job_id),
            'status': db_job.get('current_step_name', db_job.get('status', '')),
            'progress': db_job.get('progress', 0),
            'completed': db_job.get('completed', False),
            'current_step': db_job.get('current_step', 0),
            'total_steps': db_job.get('total_steps', 10),
            'agents_completed': [],
            'errors': []
        })
    
    # Fall back to memory
    if job_id in analysis_jobs:
        job = analysis_jobs[job_id]
        return jsonify({
            'id': job['id'],
            'status': job['status'],
            'progress': job['progress'],
            'completed': job['completed'],
            'agents_completed': job['agents_completed'],
            'errors': job['errors']
        })
    
    return jsonify({'error': 'Job not found'}), 404


@app.route('/api/results/<job_id>', methods=['GET'])
def get_results(job_id):
    """Get analysis results."""
    
    # Try database first
    db_job = get_job_from_db(job_id)
    
    if db_job:
        if not db_job.get('completed', False):
            return jsonify({'error': 'Analysis not complete'}), 400
        
        reports = get_reports_from_db(job_id)
        return jsonify({
            'id': db_job.get('job_id', job_id),
            'reports': reports,
            'question': db_job.get('question', ''),
            'completed_at': db_job.get('completed_at'),
            'errors': []
        })
    
    # Fall back to memory
    if job_id in analysis_jobs:
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
    
    return jsonify({'error': 'Job not found'}), 404


@app.route('/api/download/<job_id>/<report_name>', methods=['GET'])
def download_report(job_id, report_name):
    """Download a specific report."""
    
    # Check local files first
    if job_id in analysis_jobs:
        report_path = Path(analysis_jobs[job_id]['output_dir']) / report_name
        if report_path.exists():
            return send_file(report_path, as_attachment=True, download_name=report_name)
    
    # Fall back to database
    reports = get_reports_from_db(job_id)
    if report_name in reports:
        return Response(
            reports[report_name],
            mimetype='text/markdown',
            headers={'Content-Disposition': f'attachment; filename={report_name}'}
        )
    
    return jsonify({'error': 'Report not found'}), 404


@app.route('/api/download-all/<job_id>', methods=['GET'])
def download_all(job_id):
    """Download all reports as zip."""
    
    # Check local files first
    if job_id in analysis_jobs:
        output_dir = Path(analysis_jobs[job_id]['output_dir'])
        zip_path = output_dir.parent / 'analysis_reports.zip'
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for report_file in output_dir.iterdir():
                if report_file.is_file():
                    zipf.write(report_file, report_file.name)
        return send_file(zip_path, as_attachment=True, download_name='analysis_reports.zip')
    
    # Fall back to database
    reports = get_reports_from_db(job_id)
    if reports:
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'analysis_reports.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for name, content in reports.items():
                zipf.writestr(name, content)
        return send_file(zip_path, as_attachment=True, download_name='analysis_reports.zip')
    
    return jsonify({'error': 'Job not found'}), 404


@app.route('/api/ask/<job_id>', methods=['POST'])
def ask_followup(job_id):
    """Ask a follow-up question about the analyzed codebase."""
    
    # Check if job exists
    db_job = get_job_from_db(job_id)
    mem_job = analysis_jobs.get(job_id)
    
    if not db_job and not mem_job:
        return jsonify({'error': 'Job not found'}), 404
    
    completed = (db_job and db_job.get('completed')) or (mem_job and mem_job.get('completed'))
    if not completed:
        return jsonify({'error': 'Analysis not complete'}), 400
    
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'error': 'No question provided'}), 400
    
    # Get output directory
    output_dir = None
    if mem_job:
        output_dir = Path(mem_job['output_dir'])
    else:
        # Create temp dir with reports from database
        reports = get_reports_from_db(job_id)
        temp_dir = tempfile.mkdtemp()
        output_dir = Path(temp_dir)
        for name, content in reports.items():
            (output_dir / name).write_text(content)
    
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
    
    try:
        if job_id in analysis_jobs:
            job = analysis_jobs[job_id]
            if 'temp_dir' in job and os.path.exists(job['temp_dir']):
                shutil.rmtree(job['temp_dir'])
            del analysis_jobs[job_id]
        
        delete_job_from_db(job_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    """Health check."""
    return jsonify({
        'service': 'RS10X Code Analysis API',
        'status': 'running',
        'version': '1.1.0',
        'api_key_set': bool(os.environ.get('ANTHROPIC_API_KEY')),
        'supabase_connected': supabase is not None
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
    print(f"Supabase: {'Connected' if supabase else 'NOT CONFIGURED'}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=False)
