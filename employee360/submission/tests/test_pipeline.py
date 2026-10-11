from pathlib import Path
import json, sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from employee360_pipeline import run, load, evaluate
root=Path(__file__).parents[1]
out=root/'outputs'/'test_run'
summary=run(root/'data',out)
assert summary['rules']==10
assert summary['release_decision']=='BLOCK'
assert summary['failing_rules'] >= 5
issues=(out/'dq_issues.csv').read_text(encoding='utf-8')
for identifier in ['E1027','E1099','E1015']:
    assert identifier in issues, identifier
categories=(out/'reconciliation_categories.csv').read_text(encoding='utf-8')
assert 'Legitimate exception,E1042,False' in categories
print('PASS',json.dumps(summary))

# Valid terminated/stopped pairs must not be reported as inconsistent.
data, _ = load(root/'data')
found = evaluate(data)
status_ids = set(found.loc[found.rule_id == 'DQ04', 'employee_id'])
assert status_ids == {'E1029', 'E1044'}, status_ids
assert summary['issues'] == 17
# A contradictory status within a payroll group must still be reported.
changed = {key: frame.copy() for key, frame in data.items()}
changed['Payroll'].loc[changed['Payroll'].employee_id == 'E1041', 'payroll_status'] = 'Payable'
changed_issues = evaluate(changed)
assert 'E1041' in set(changed_issues.loc[changed_issues.rule_id == 'DQ04', 'employee_id'])
print('PASS status mapping: terminated/stopped accepted; contradictory payable detected')