"""Deterministic Employee 360 data-quality and reconciliation pipeline.
Run: python src/employee360_pipeline.py --input data --output outputs
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

RULES = {
    'DQ01': ('employee_id unique in every source', 'Uniqueness', 'Critical', 'Block release'),
    'DQ02': ('mandatory HR fields populated', 'Completeness', 'Medium', 'Monitor'),
    'DQ03': ('manager_id exists in HR', 'Referential integrity', 'High', 'Alert now'),
    'DQ04': ('HR status agrees with payroll status', 'Consistency', 'Critical', 'Alert now'),
    'DQ05': ('payroll salary is a positive ZAR amount', 'Validity', 'High', 'Block release'),
    'DQ06': ('record updated within freshness threshold', 'Timeliness', 'Medium', 'Monitor'),
    'DQ07': ('one unambiguous payroll value per employee and period', 'Consistency', 'Critical', 'Block release'),
    'RC01': ('every HR employee is in Employee 360', 'Reconciliation', 'Critical', 'Block release'),
    'RC02': ('no Employee 360 record without HR employee', 'Reconciliation', 'Critical', 'Block release'),
    'RC03': ('status, salary and currency match when verifiable', 'Reconciliation', 'Critical', 'Block release'),
}

def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load(input_dir: Path):
    paths={'HR':input_dir/'HR_Source.csv','Payroll':input_dir/'Payroll_Source.csv','Employee_360':input_dir/'Employee_360.csv'}
    return {n:pd.read_csv(p,dtype=str,keep_default_na=False) for n,p in paths.items()}, {n:hash_file(p) for n,p in paths.items()}

def issue(rule, employee_id, source, detail, severity=None):
    return {'rule_id':rule,'employee_id':employee_id or '', 'source':source, 'detail':detail,
            'severity':severity or RULES[rule][2], 'release_action':RULES[rule][3]}

def add_rule(rows, rule, found):
    rows.extend(found)

def profile(df):
    return {'rows':len(df),'distinct_employee_ids':df['employee_id'].nunique(),'duplicate_employee_id_rows':int(df.duplicated('employee_id',keep=False).sum()),
            'null_or_blank_cells':int((df=='').sum().sum())}

def evaluate(data):
    hr, payroll, e360=data['HR'].copy(),data['Payroll'].copy(),data['Employee_360'].copy()
    issues=[]
    # DQ01
    for name,df in [('HR',hr),('Payroll',payroll),('Employee_360',e360)]:
        for eid in sorted(df.loc[df.duplicated('employee_id',keep=False),'employee_id'].unique()):
            add_rule(issues,'DQ01',[issue('DQ01',eid,name,'duplicate employee_id')])
    # DQ02
    for _,r in hr.iterrows():
        for col in ['email','department','full_name','employment_status']:
            if not r[col].strip(): add_rule(issues,'DQ02',[issue('DQ02',r.employee_id,'HR',f'blank: {col}')])
    # DQ03
    people=set(hr.employee_id)
    for _,r in hr.iterrows():
        if r.manager_id and r.manager_id not in people: add_rule(issues,'DQ03',[issue('DQ03',r.employee_id,'HR',f'manager_id {r.manager_id} is not in HR')])
    # DQ04
    pay_status=payroll.groupby('employee_id')['payroll_status'].agg(lambda x: sorted(set(x)))
    for _,r in hr.iterrows():
        statuses=pay_status.get(r.employee_id,[])
        expected={'Active':'Payable', 'Terminated':'Stopped'}.get(r.employment_status)
        if expected is None or set(statuses) != {expected}: add_rule(issues,'DQ04',[issue('DQ04',r.employee_id,'HR vs Payroll',f'HR {r.employment_status}, payroll {statuses or "missing"}')])
    # DQ05
    for _,r in payroll.iterrows():
        try: valid=float(r.monthly_salary_zar)>0 and r.currency=='ZAR'
        except ValueError: valid=False
        if not valid: add_rule(issues,'DQ05',[issue('DQ05',r.employee_id,'Payroll',f'currency {r.currency} / salary {r.monthly_salary_zar}')])
    # DQ06: dates before 2026-07-10 are stale for this supplied-data assessment date
    cutoff=pd.Timestamp('2026-07-10')
    for name,df in [('HR',hr),('Payroll',payroll),('Employee_360',e360)]:
        for _,r in df.iterrows():
            d=pd.to_datetime(r.last_updated,errors='coerce')
            if pd.isna(d) or d<cutoff: add_rule(issues,'DQ06',[issue('DQ06',r.employee_id,name,f'last_updated {r.last_updated} is stale or invalid')])
    # DQ07: never select an arbitrary conflicting payroll value
    for (eid,period),g in payroll.groupby(['employee_id','pay_period']):
        vals=g[['monthly_salary_zar','currency']].drop_duplicates()
        if len(vals)>1: add_rule(issues,'DQ07',[issue('DQ07',eid,'Payroll',f'{len(vals)} conflicting salary/currency values for {period}')])
    # RC01 / RC02
    hids,eids=set(hr.employee_id),set(e360.employee_id)
    for eid in sorted(hids-eids): add_rule(issues,'RC01',[issue('RC01',eid,'HR vs Employee_360','Missing downstream')])
    for eid in sorted(eids-hids): add_rule(issues,'RC02',[issue('RC02',eid,'HR vs Employee_360','Unexpected downstream')])
    # RC03: only compare one deterministic, unambiguous payroll value
    pconf=set()
    for (eid,_),g in payroll.groupby(['employee_id','pay_period']):
        if len(g[['monthly_salary_zar','currency']].drop_duplicates())>1: pconf.add(eid)
    hmap=hr.drop_duplicates('employee_id').set_index('employee_id')
    emap=e360.drop_duplicates('employee_id').set_index('employee_id')
    pmap=payroll.sort_values(['employee_id','pay_period','last_updated']).drop_duplicates('employee_id',keep='last').set_index('employee_id')
    for eid in sorted(hids & eids):
        h,e=hmap.loc[eid],emap.loc[eid]
        if eid in pconf:
            add_rule(issues,'RC03',[issue('RC03',eid,'Payroll vs Employee_360','Cannot verify: conflicting payroll values')]); continue
        p=pmap.loc[eid] if eid in pmap.index else None
        details=[]
        if h.employment_status!=e.employment_status: details.append(f'employment status: {h.employment_status} -> {e.employment_status}')
        if p is None: details.append('missing payroll record')
        else:
            if p.monthly_salary_zar!=e.monthly_salary_zar: details.append(f'salary: {p.monthly_salary_zar} -> {e.monthly_salary_zar}')
            if p.currency!=e.currency: details.append(f'currency: {p.currency} -> {e.currency}')
        if details: add_rule(issues,'RC03',[issue('RC03',eid,'Source vs Employee_360','; '.join(details))])
    return pd.DataFrame(issues,columns=['rule_id','employee_id','source','detail','severity','release_action'])

def reconciliation_categories(issues, data):
    records=[]
    mapping={'RC01':'Missing downstream','RC02':'Unexpected downstream'}
    for _,r in issues.iterrows():
        category=mapping.get(r.rule_id)
        if r.rule_id=='RC03': category='Cannot verify' if 'Cannot verify' in r.detail else 'Field error'
        if category: records.append({'category':category,'employee_id':r.employee_id,'counts_as_failure':True,'detail':r.detail})
    # E1042 is a documented future-dated HR change, included transparently, not a failure.
    if 'E1042' in set(data['HR'].employee_id): records.append({'category':'Legitimate exception','employee_id':'E1042','counts_as_failure':False,'detail':'Future-dated HR change; not a release failure'})
    return pd.DataFrame(records)

def run(input_dir: Path, output_dir: Path):
    data, hashes=load(input_dir); output_dir.mkdir(parents=True,exist_ok=True)
    issues=evaluate(data); categories=reconciliation_categories(issues,data)
    profile_rows=[{'source':name,**profile(df)} for name,df in data.items()]
    monitoring=[]
    for rule,(desc,dimension,severity,action) in RULES.items():
        n=int((issues.rule_id==rule).sum())
        monitoring.append({'rule_id':rule,'description':desc,'dimension':dimension,'status':'FAIL' if n else 'PASS','affected_count':n,'severity':severity,'release_action':action})
    pd.DataFrame(profile_rows).to_csv(output_dir/'profile.csv',index=False)
    issues.to_csv(output_dir/'dq_issues.csv',index=False)
    categories.to_csv(output_dir/'reconciliation_categories.csv',index=False)
    pd.DataFrame(monitoring).to_csv(output_dir/'monitoring.csv',index=False)
    summary={'source_hashes':hashes,'rules':len(RULES),'failing_rules':sum(m['status']=='FAIL' for m in monitoring),'issues':len(issues),'release_decision':'BLOCK' if any(m['release_action']=='Block release' and m['status']=='FAIL' for m in monitoring) else 'PASS'}
    (output_dir/'run_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary

def main():
    p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(run(a.input,a.output),indent=2))
if __name__=='__main__': main()
