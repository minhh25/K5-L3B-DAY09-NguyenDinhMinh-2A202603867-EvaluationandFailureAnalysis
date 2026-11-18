# Đối chiếu RUBRIC.md và SUBMISSION.md

Đây là bằng chứng kiểm chứng public, không tự chấm điểm hidden. Tất cả thay đổi bài làm nằm trong repo Day 09 cá nhân, nhánh `starter/d09`. Repo Day 08 của nhóm không được chỉnh sửa.

| Checkpoint / rubric | Bằng chứng | Trạng thái local |
|---|---|---|
| M0 — setup | `reports/smoke.txt`, `config/day8_source.json` | M0 PASS; Python 3.13; source giảng viên commit `034c6c421c198dae67a9211d15e2587d5a378972` |
| M1 — taxonomy + eval set (12đ) | `failure_taxonomy.md`, `reports/failure_evidence.json`, eval set/labels v1 | FM-01…FM-09 giữ ID; 8 failure probes + 1 scope control; v1 14 item; check sạch; private anchor key chưa có |
| M2 — calibration (12đ) | `judge_audit.md`, `reports/judge_calibration.json` | Tone đạt; helpful loại; audit 10 disagreement từ CSV |
| M3 — trajectory (12đ) | `lab9/graders.py`, `tests/test_lab9_reliability.py`, `reports/detection.txt` | Detection 100%, false alarm 0%; grader FM-08 + gross proposal có regression tests |
| M4 — bootstrap/gate (15đ) | `reports/gate_fixed.txt`, `reports/gate_seeded_regression.txt`, `harness_map.yaml` | Fixed exit 0; seeded exit 1 trên pass_rate; CI khớp tham chiếu; harness version 1.2 |
| Eval card + PRD (9đ) | `eval_card.md`, `PRD_v1.1.md` | Số liệu lấy từ report; owner/approval chưa xác nhận được ghi rõ |
| M5 — v2 + slices | `config/fm_map.yaml`, `metric_spec_v2.yaml`, labels/items v2 | 28 item, đủ v1+pack, ≥3 item/FM bị tấn công, ba slice blocking |
| M6 — reliability/noise | `reports/aa.txt`, `reports/gate_flaky_regression_v2.txt` | A/A Δ=0; pass_hat_5 floor=0.8; baseline tự merge, flaky bị block |
| M7 — integrity/ratchet | `reports/mutation.txt`, `reports/traps.txt`, `reports/trap_*.txt` | Mutation 3/3, 0 false alarm; bốn trap đều INTEGRITY exit 1 |
| Bảo toàn source | `reports/verification.json`, `config/day8_source.json` | lab8 và public fixtures trùng checksum nguồn; variants/traps/public tests không sửa |

## Kiểm thử và giới hạn

`reports/verification.json` ghi đầy đủ command, expected/actual exit code và log. Lệnh helpful, regression red, seeded/slice/flaky gates và từng trap được kỳ vọng exit 1; exception ngoài dự kiến không được coi là thành công.

Toàn bộ test Day 08 được chạy, bao gồm ba shape stub của repo gốc. 186 failure ở `tests/test_public_matrix.py` thuộc workflow/single/orchestrator được ghi nguyên trạng trong `reports/all_tests.txt`; không được gọi là đã sửa. Host và test Lab 09 phải xanh. Tổng số cụ thể đọc trong `reports/verification.json` và eval card.

Private anchor key, hidden variants/traps và điểm cuối do giảng viên xác nhận. Không tự tuyên bố 100/100. Chưa có người dùng thật, model thật, nhãn held-out hoặc phê duyệt production.

## Tái lập

Từ root repo Day 09:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r src/requirements.txt -r src/requirements-lab9.txt -c src/requirements-lock.txt
cd src
../.venv/bin/python -m scripts.verify_day09
../.venv/bin/python -m scripts.render_day09_docs
```

Các JSON report và log được sinh bằng script rồi force-add có chọn lọc. Không nộp `.env`, API key, SQLite hoặc thư mục traces runtime. Các canary trong failure evidence là dữ liệu tổng hợp công khai của đề bài.

## GitHub và LMS

PR phải từ `starter/d09` vào `main` của `minhh25/K5-L3B-DAY09-NguyenDinhMinh-2A202603867-EvaluationandFailureAnalysis`. Chỉ merge sau khi `eval-gate` và `eval-gate-v2` xanh. Trạng thái và URL PR sẽ được ghi sau khi quan sát trên GitHub; tài liệu này không thay cho kết quả CI.

Sau merge, nộp link repo cá nhân trên LMS và kiểm tra hạn nộp theo ca. Phiên làm việc này không có phiên đăng nhập LMS hoặc bằng chứng hạn nộp nên không tự xác nhận đã nộp LMS.
