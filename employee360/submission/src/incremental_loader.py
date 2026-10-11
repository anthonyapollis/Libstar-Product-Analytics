"""Content-hash incremental-load gate used before the DQ pipeline."""
from __future__ import annotations
import hashlib, json
from pathlib import Path

def digest(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load_incremental(input_dir: Path, state_file: Path):
    state=json.loads(state_file.read_text()) if state_file.exists() else {'files':{}}
    decision=[]
    for filename in ['HR_Source.csv','Payroll_Source.csv','Employee_360.csv']:
        path=input_dir/filename; value=digest(path)
        previous=state['files'].get(filename)
        status='SKIPPED_UNCHANGED' if previous==value else 'LOADED_CHANGED'
        decision.append({'file':filename,'sha256':value,'status':status})
        state['files'][filename]=value
    state_file.parent.mkdir(parents=True,exist_ok=True)
    state_file.write_text(json.dumps(state,indent=2))
    return decision
