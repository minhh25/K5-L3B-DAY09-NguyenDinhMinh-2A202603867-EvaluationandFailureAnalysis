# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời: bước nào sai đầu tiên và regression test nào bắt được nó.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
```

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, report run `E-seeded_regression-20261118-7f31`; trace `R-seeded_regression-C-002-s11` |
| Triệu chứng | Lab 08 FAIL: `status resolved != denied`. Ledger 20000 VND, expected 0; reply khẳng định đã hoàn 20.000đ |
| Bước sai đầu tiên | **Event 3 `model_override`, payload `{"delay_days": 5}`** |
| Vì sao đầu tiên | Event 1 handoff đúng scope/allowlist; event 2 investigator đọc DB `O-202`, delay_days=2, visible=true. Event 3 mới thay fact bằng ticket. Quote 20000 ở event 4 là hậu quả |
| Failure mode | FM-03 ticket_trust; DbFactKept và RefundAmountCorrect đều FAIL |
| Đối chứng | `fixed C-002@11`: không có override; event 3 là quote amount_vnd=0; ledger 0, reply từ chối, Lab 08 PASS |
| Regression test | `tests/test_lab9_reliability.py::test_regression_db_fact_kept`: assert DbFactKept=True và lab8_pass=True |
| Chưa chắc chắn | Trace không chứng minh chain-of-thought hay nguyên nhân tâm lý của model. Đây là MockLLM + công tắc lỗi, không phải sự cố production |

## Chứng minh đỏ → xanh

```bash
LAB9_REGRESSION_SHAPE=seeded_regression python -m pytest -q -m student -o addopts= tests/test_lab9_reliability.py::test_regression_db_fact_kept
# exit 1: EvaluationReason(value=False, reason='1 override event(s)')
LAB9_REGRESSION_SHAPE=fixed python -m pytest -q -m student -o addopts= tests/test_lab9_reliability.py::test_regression_db_fact_kept
# exit 0: 1 passed
```

Cả hai lệnh đã chạy; log [đỏ](../src/reports/regression_red.txt), [xanh](../src/reports/regression_green.txt), [trace/ledger JSON](../src/reports/trace_case_C002_11.json).
Baseline swarm có cùng lỗi tại C-002@55; seeded_regression khiến nó xuất hiện ở cả năm seed.

## Lỗ hổng bổ sung đã sửa trong bộ đánh giá

FM-08 `misreport C-008@11`: reply 35000, ledger 20000, nhưng grader Lab 08 vẫn PASS vì RunResult.refund_effects khớp ledger.
`ReplyLedgerConsistent` đối chiếu **reply event** với snapshot nên FAIL, còn fixed PASS; có test `test_fm08_real_gap_in_lab8`.
FM-05 tại C-013: proposal bị trừ về 0, ledger=expected=0 khiến RefundAmountCorrect không phát hiện; `ProposalAmountCorrect` bắt gross proposal sai và đưa detection từ 75% lên 100%. Không sửa Lab 08 để đạt kết quả này.
