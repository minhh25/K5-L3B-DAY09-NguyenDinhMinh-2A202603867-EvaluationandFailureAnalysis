"""Additional edge/regression tests. Public tests are unchanged."""
import copy
import math
import os
from types import SimpleNamespace

import pytest
from lab9 import gate, stats
from lab9.eval import aggregate
from lab9.graders import ProposalAmountCorrect, ReplyLedgerConsistent, DbFactKept
from lab9.trace_case import investigate

pytestmark = pytest.mark.student


@pytest.fixture(autouse=True)
def isolated_shape_registry():
    from lab8.shapes import SHAPES
    original = SHAPES.copy()
    yield
    SHAPES.clear()
    SHAPES.update(original)


@pytest.mark.parametrize('fn', [stats.pass_at_k, stats.pass_hat_k])
@pytest.mark.parametrize('args', [(0,0,1),(-1,0,1),(5,-1,1),(5,6,1),(5,1,0),(5,1,6),(5.0,1,1),(True,1,1)])
def test_advanced_pass_k_rejects_invalid(fn, args):
    with pytest.raises(ValueError): fn(*args)


def test_advanced_pass_k_exact_and_large():
    for n in range(1,18):
        for c in range(n+1):
            for k in range(1,n+1):
                assert stats.pass_at_k(n,c,k)==pytest.approx(1-math.comb(n-c,k)/math.comb(n,k))
                assert stats.pass_hat_k(n,c,k)==pytest.approx(math.comb(c,k)/math.comb(n,k))
    assert stats.pass_at_k(10**12,1,1)==pytest.approx(1e-12,rel=1e-9,abs=0)
    assert stats.pass_hat_k(10000,9999,9000)==pytest.approx(.1)


@pytest.mark.parametrize('a,b', [([],[]),([1],[]),([float('nan')],[0]),([[1]],[[1]]),([float('inf')],[0])])
def test_bootstrap_invalid(a,b):
    with pytest.raises(ValueError): stats.paired_bootstrap(a,b)


def test_calibration_invalid():
    for h,j in [([],[]),(['PASS'],[]),(['PASS'],['UNKNOWN'])]:
        with pytest.raises(ValueError): stats.confusion(h,j)
    assert stats.precision_recall(['PASS'],['PASS'])==(0,0)
    with pytest.raises(ValueError): stats.rogan_gladen(.5,.5,.5)
    with pytest.raises(ValueError): stats.rogan_gladen(float('nan'),.8,.9)
    assert stats.rogan_gladen(1,.8,.9)==1
    assert stats.paired_bootstrap([.4],[.2])==(.2,.2,.2)


def reply_context(text,actual=37000):
    return SimpleNamespace(output={'snapshot':{'refund_vnd':actual},'events':[{'kind':'reply','payload':{'text':text}}]})


@pytest.mark.parametrize('text,amount', [
    ('Dạ, đã hoàn phí 37.000đ cho đơn O-700.',37000),('Đã hoàn tiền 37,000 VND.',37000),('Đã hoàn 37.000 VNĐ.',37000),
    ('Đã hoàn 37 000 đồng.',37000),('LogiX đã hoàn 37\u202f000 ₫.',37000),('Đã hoàn VND 37000.',37000),
    ('Refunded 37,000 VND.',37000),('Đã hoàn 37 nghìn đồng.',37000),('Đã hoàn 1,5 triệu đồng.',1500000),
    ('Đã hoàn 1.500.000,00 đồng.',1500000),('Đề xuất 50.000đ; đã hoàn 37.000đ theo mức duyệt 50.000đ.',37000)])
def test_fm08_formats(text,amount):
    assert ReplyLedgerConsistent().evaluate(reply_context(text,amount)).value is True
    assert ReplyLedgerConsistent().evaluate(reply_context(text,amount-1000)).value is False


@pytest.mark.parametrize('text',['Chưa hoàn 37.000đ.','Sẽ hoàn phí 37.000đ.','Đề xuất hoàn 37.000đ, chờ duyệt.',
                                 'Đã kiểm tra đơn O-37000.','Không thể hoàn tiền; đã chuyển chuyên viên.','Đã hoàn 0đ.'])
def test_fm08_no_transaction(text):
    assert ReplyLedgerConsistent().evaluate(reply_context(text,0)).value is True


def test_fm08_real_gap_in_lab8():
    from lab8.shapes import SHAPES
    from lab9.variant_agent import make_shape
    SHAPES['test_reply_gap']=make_shape('test_reply_gap',{'no_override','misreport'})
    case=investigate('test_reply_gap','C-008',11)
    assert case['trial']['lab8_pass'] is True
    assert ReplyLedgerConsistent().evaluate(SimpleNamespace(output=case['trial'])).value is False
    fixed=investigate('fixed','C-008',11)
    assert ReplyLedgerConsistent().evaluate(SimpleNamespace(output=fixed['trial'])).value is True


def test_proposal_double_deduction_hidden_by_zero_ledger():
    for shape,want in [('seeded_regression',False),('fixed',True)]:
        case=investigate(shape,'C-013',11)
        assert ProposalAmountCorrect().evaluate(SimpleNamespace(output=case['trial'],expected_output=case['label'])).value is want


def test_regression_db_fact_kept():
    """Set LAB9_REGRESSION_SHAPE=seeded_regression to show red; fixed is green."""
    case=investigate(os.environ.get('LAB9_REGRESSION_SHAPE','fixed'),'C-002',11)
    assert DbFactKept().evaluate(SimpleNamespace(output=case['trial'])).value is True
    assert case['trial']['lab8_pass'] is True


def fixture_report():
    rows=[{'item_id':f'i{i}','seed':s,'slices':['cash'] if i<2 else [],'pass_rate':True} for i in range(4) for s in (7,8)]
    rep={'manifest':{'eval_set_sha':'fixture','items':4,'seeds':[7,8]},'rows':rows,'metrics':{'pass_rate':1.0},'evaluator_failures':[]}
    spec={'eval_set_version':'v2','metrics':[{'id':'pass_rate','kind':'capability','grader':'code','blocking':True,
           'threshold':{'min':.8,'no_significant_drop':True}}],
          'slices':[{'name':'cash','metric':'pass_rate','min':.9,'no_significant_drop':True,'blocking':True}]}
    return rep,spec


@pytest.mark.parametrize('attack',['nan','inf','none','missing_metric','row_none','duplicate','dropped','seed','tags','failures','headline','baseline'])
def test_advanced_integrity_tampering(attack):
    base,spec=fixture_report();pr=copy.deepcopy(base)
    if attack in ('nan','inf','none'): pr['metrics']['pass_rate']={'nan':float('nan'),'inf':float('inf'),'none':None}[attack]
    elif attack=='missing_metric': pr['metrics'].clear()
    elif attack=='row_none': pr['rows'][0]['pass_rate']=None
    elif attack=='duplicate': pr['rows'][-1]=copy.deepcopy(pr['rows'][0])
    elif attack=='dropped': pr['rows'].pop()
    elif attack=='seed':
        pr['manifest']['seeds']=[7,9]
        for r in pr['rows']:
            if r['seed']==8:r['seed']=9
    elif attack=='tags':pr['rows'][0]['slices']=[]
    elif attack=='failures':pr['evaluator_failures']=['crashed grader on otherwise green run']
    elif attack=='headline':pr['rows'][0]['pass_rate']=False
    elif attack=='baseline':base['rows'][0]['pass_rate']=None
    assert gate.check(pr,base,spec)[0]==['integrity']


@pytest.mark.parametrize('attack',['min','drop_ci','disable','delete_metric','slice_min','delete_slice','slice_ci','grader','max'])
def test_advanced_ratchet_generic(attack):
    rep,base_spec=fixture_report();spec=copy.deepcopy(base_spec)
    if attack=='min':spec['metrics'][0]['threshold']['min']=.7
    elif attack=='drop_ci':spec['metrics'][0]['threshold'].pop('no_significant_drop')
    elif attack=='disable':spec['metrics'][0]['blocking']=False
    elif attack=='delete_metric':spec['metrics']=[]
    elif attack=='slice_min':spec['slices'][0]['min']=.5
    elif attack=='delete_slice':spec['slices']=[]
    elif attack=='slice_ci':spec['slices'][0]['no_significant_drop']=False
    elif attack=='grader':spec['metrics'][0]['grader']=None
    elif attack=='max':
        base_spec['metrics'][0]['threshold']['max']=1
        spec['metrics'][0]['threshold']['max']=2
    assert gate.integrity_check(rep,rep,spec,base_spec)


def test_advanced_self_comparison_reordered_rows():
    rep,spec=fixture_report();pr=copy.deepcopy(rep);pr['rows'].reverse()
    assert gate.check(pr,rep,spec,spec)[0]==[]


def test_advanced_slice_above_floor_and_missing():
    base,spec=fixture_report();pr=copy.deepcopy(base)
    for r in pr['rows']:
        if 'cash' in r['slices'] and r['seed']==7:r['pass_rate']=False
    pr['metrics']['pass_rate']=.75;spec['slices'][0]['min']=.4
    assert gate.slice_check(pr,base,spec)[0]==['slice:cash/pass_rate']
    spec['slices'][0]['name']='absent'
    assert gate.slice_check(pr,base,spec)[0]==['slice:absent/pass_rate']


def test_aggregate_never_drops_crashed_grader():
    rows=[{'item_id':'a','pass_rate':True,'cost':1},{'item_id':'b','pass_rate':None,'cost':1}]
    assert aggregate(rows,['pass_rate'])['pass_rate'] is None


def test_judge_undefined_kappa_fails_calibration(tmp_path):
    from lab9.judge import calibrate
    csv = tmp_path / "constant.csv"
    csv.write_text("item_id,human,judge,reply\na,PASS,PASS,ok\nb,PASS,PASS,ok\n")
    result = calibrate(csv)
    assert result['passed'] is False
    assert result['kappa'] is None
    assert result['calibration_errors']


@pytest.mark.parametrize('section,value', [('manifest',None),('rows',None),('metrics',[]),('evaluator_failures',None)])
def test_advanced_malformed_baseline_fails_closed(section,value):
    rep,spec=fixture_report();base=copy.deepcopy(rep);base[section]=value
    assert gate.check(rep,base,spec)[0]==['integrity']


@pytest.mark.parametrize('mutation', ['threshold_none','metric_id_list','bootstrap_none','blocking_text','slice_ci_text'])
def test_advanced_malformed_policy_fails_closed(mutation):
    rep,spec=fixture_report()
    if mutation=='threshold_none':spec['metrics'][0]['threshold']=None
    elif mutation=='metric_id_list':spec['metrics'][0]['id']=[]
    elif mutation=='bootstrap_none':spec['bootstrap']=None
    elif mutation=='blocking_text':spec['metrics'][0]['blocking']='false'
    elif mutation=='slice_ci_text':spec['slices'][0]['no_significant_drop']='false'
    assert gate.check(rep,rep,spec)[0]==['integrity']


def test_advanced_derived_metric_supports_paired_and_slice_checks():
    rep,spec=fixture_report()
    rep['metrics']['pass_hat_2']=1.0
    spec['metrics'].append({'id':'pass_hat_2','kind':'capability','blocking':True,
                            'threshold':{'min':.8,'no_significant_drop':True}})
    spec['slices'].append({'name':'cash','metric':'pass_hat_2','min':.8,'blocking':True,'no_significant_drop':True})
    assert gate.check(rep,rep,spec,spec)[0]==[]
    pr=copy.deepcopy(rep)
    for row in pr['rows']:
        if row['seed']==7:row['pass_rate']=False
    pr['metrics']={'pass_rate':.5,'pass_hat_2':0.0}
    blocked,_=gate.check(pr,rep,spec,spec)
    assert 'pass_hat_2' in blocked
    assert 'slice:cash/pass_hat_2' in blocked


def test_advanced_seed_reordering_preserves_plan_and_embedded_ratchet():
    rep,spec=fixture_report();spec['seeds']=[7,8]
    rep['manifest']['metric_spec']=copy.deepcopy(spec)
    reordered=copy.deepcopy(spec);reordered['seeds'].reverse()
    assert gate.check(rep,rep,reordered)[0]==[]
    reordered['metrics'][0]['threshold']['min']=.5
    assert gate.check(rep,rep,reordered)[0]==['integrity']
