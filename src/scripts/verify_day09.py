"""Reproduce Day 09 evidence. Run from src/: python -m scripts.verify_day09.

Full inherited Day 08 matrix is deliberately run and its 186 stub failures reported.
Those do not count as completed Day 09 work. Every other unexpected result exits 1.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports'


def main() -> int:
    OUT.mkdir(exist_ok=True)
    results = []

    def run(name, args, expected=0, env=None, contains=()):
        proc = subprocess.run([sys.executable, '-m', *args], cwd=ROOT,
                              env={**os.environ, **(env or {})}, capture_output=True, text=True)
        output = proc.stdout + proc.stderr
        (OUT / f'{name}.txt').write_text(output, encoding='utf-8')
        ok = proc.returncode == expected and all(text in output for text in contains)
        results.append({'name':name,'command':[sys.executable,'-m',*args],
                        'exit_code':proc.returncode,'expected_exit':expected,'as_expected':ok,
                        'log':f'reports/{name}.txt'})
        print(f'{name}: exit {proc.returncode} (expected {expected}) {"ok" if ok else "UNEXPECTED"}', flush=True)
        return proc

    run('smoke',['lab9.smoke'],contains=['M0 PASS'])
    run('evalset_v1',['lab9.evalset','--build','--check'],contains=['0 problem(s)'])
    run('evalset_v2',['lab9.evalset','--v2','--build','--check'],contains=['0 problem(s)'])
    run('host_tests',['pytest','-q'])
    run('core_tests',['pytest','-q','-m','student','-o','addopts=','-k','lab9 and not advanced'])
    run('advanced_tests',['pytest','-q','-m','student','-o','addopts=','-k','advanced'])
    run('all_tests',['pytest','-q','-o','addopts=','--tb=no','--junitxml=reports/full_tests.xml'],1)
    tree = ET.parse(OUT / 'full_tests.xml').getroot()
    cases = list(tree.iter('testcase'))
    failures = [t for t in cases if t.find('failure') is not None or t.find('error') is not None]
    inherited = (len(failures) == 186 and all(t.get('classname') == 'tests.test_public_matrix'
                 and any(shape in t.get('name','') for shape in ('workflow','single','orchestrator')) for t in failures))
    results[-1]['as_expected'] &= inherited
    test_summary = {'total':len(cases),'passed':len(cases)-len(failures),'failed':len(failures),
                    'all_failures_are_untouched_day8_stubs':inherited}
    run('regression_red',['pytest','-q','-m','student','-o','addopts=','tests/test_lab9_reliability.py::test_regression_db_fact_kept'],1,
        env={'LAB9_REGRESSION_SHAPE':'seeded_regression'},contains=['AssertionError','DbFactKept'])
    run('regression_green',['pytest','-q','-m','student','-o','addopts=','tests/test_lab9_reliability.py::test_regression_db_fact_kept'],
        env={'LAB9_REGRESSION_SHAPE':'fixed'},contains=['1 passed'])
    for judge,code in [('tone',0),('helpful',1)]:
        run(f'judge_{judge}',['lab9.judge','--csv',f'data/eval/judge_{judge}_public.csv','--audit','5'],code)
    run('detection',['lab9.mutation','--detect'],contains=['detection 100.00%','false alarms 0.00%'])
    run('failure_evidence',['lab9.evidence'])
    for v in (1,2):
        spec=f'config/metric_spec{"_v2" if v==2 else ""}.yaml'
        baseline=f'reports/baseline_v{v}.json'
        run(f'baseline_v{v}',['lab9.eval','--shape','swarm','--spec',spec,'--out',baseline])
        run(f'gate_self_v{v}',['lab9.gate','--pr',baseline,'--baseline',baseline,'--spec',spec],contains=['exit 0 — merge'])
        variants=['fixed','seeded_regression'] if v==1 else ['fixed','honest_refactor','seeded_regression','slice_regression','flaky_regression']
        for shape in variants:
            suffix='_v2' if v==2 and shape!='slice_regression' else ''
            report=f'reports/eval_{shape}{suffix}.json'
            run(f'eval_{shape}{suffix}',['lab9.eval','--shape',shape,'--spec',spec,'--out',report])
            expected=0 if shape in ['fixed','honest_refactor'] else 1
            run(f'gate_{shape}{suffix}',['lab9.gate','--pr',report,'--baseline',baseline,'--spec',spec],expected,
                contains=['exit 0 — merge'] if not expected else ['exit 1 — blocked:', *(['pass_rate'] if shape=='seeded_regression' else [])])
        if v==1:
            run('eval_pr',['lab9.eval','--shape','swarm','--spec',spec,'--out','reports/eval_pr.json'])
            run('baseline_sanity',['lab9.ci_check','--pr','reports/eval_pr.json','--baseline',baseline,'--spec',spec])
    v2='config/metric_spec_v2.yaml'
    base2='reports/baseline_v2.json'
    run('mutation',['lab9.mutation','--spec',v2,'--baseline',base2],contains=['mutation score 3/3 · false alarms 0'])
    run('aa',['lab9.mutation','--spec',v2,'--aa','66,77,88,99,110'])
    run('traps',['lab9.traps','--pr','reports/eval_slice_regression.json','--baseline',base2,'--spec',v2],
        contains=['exit 0 — the gate blocked every public trap'])
    for trap in ['evaluator_errors_as_nan','dropped_failing_rows','cherry_picked_seeds','loosened_spec']:
        args=['lab9.gate','--pr',f'reports/traps/{trap}.json','--baseline',base2,'--spec',
              f'reports/traps/{trap}.spec.yaml' if trap=='loosened_spec' else v2]
        if trap=='loosened_spec': args+=['--base-spec',v2]
        run(f'trap_{trap}',args,1,contains=['INTEGRITY','exit 1 — blocked: integrity'])
    source=json.loads((ROOT/'config/day8_source.json').read_text())
    differences=[p for p,sha in source['sha256'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=sha]
    results.append({'name':'day8_immutable','upstream_commit':source['commit'],'differences':differences,'as_expected':not differences})
    result={'generated_at':datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).isoformat(),
            'tests':test_summary,'checks':results,'all_expected':all(r['as_expected'] for r in results)}
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tests':test_summary,'all_expected':result['all_expected']},ensure_ascii=False))
    return 0 if result['all_expected'] else 1


if __name__=='__main__':
    raise SystemExit(main())
