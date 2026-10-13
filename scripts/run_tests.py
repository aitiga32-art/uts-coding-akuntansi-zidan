import json
import os
import sys
import unittest
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
os.chdir(root)
class Result(unittest.TextTestResult):
    def __init__(self,*a,**kw): super().__init__(*a,**kw); self.records=[]
    def addSuccess(self,test): super().addSuccess(test);self.records.append({'test':test.id(),'status':'PASS'})
    def addFailure(self,test,err): super().addFailure(test,err);self.records.append({'test':test.id(),'status':'FAIL'})
    def addError(self,test,err): super().addError(test,err);self.records.append({'test':test.id(),'status':'ERROR'})
    def addSkip(self,test,reason): super().addSkip(test,reason);self.records.append({'test':test.id(),'status':'SKIP','reason':reason})
suite=unittest.defaultTestLoader.discover(str(root/'tests'))
result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(suite)
report={'run_at_utc':datetime.now(timezone.utc).isoformat(),'tests':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'results':result.records}
target=root/'docs'/'hasil_uji.json';target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps(report,indent=2),encoding='utf-8')
sys.exit(0 if result.wasSuccessful() else 1)
