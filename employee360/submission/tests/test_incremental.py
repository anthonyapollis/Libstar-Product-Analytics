from pathlib import Path
import shutil, sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from incremental_loader import load_incremental
root=Path(__file__).parents[1]; temp=root/'outputs'/'incremental_test'; incoming=temp/'incoming'; state=temp/'state.json'
if temp.exists(): shutil.rmtree(temp)
shutil.copytree(root/'data',incoming)
r1=load_incremental(incoming,state); assert all(x['status']=='LOADED_CHANGED' for x in r1)
r2=load_incremental(incoming,state); assert all(x['status']=='SKIPPED_UNCHANGED' for x in r2)
p=incoming/'HR_Source.csv'; p.write_text(p.read_text()+'\n',encoding='utf-8')
r3=load_incremental(incoming,state); assert next(x for x in r3 if x['file']=='HR_Source.csv')['status']=='LOADED_CHANGED'
assert sum(x['status']=='SKIPPED_UNCHANGED' for x in r3)==2
print('PASS incremental: full load, no-change skip, selective changed-file load')
