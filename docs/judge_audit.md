# Judge audit

Các lệnh thực sự đã chạy:

```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.8 | Đạt | đủ điều kiện cho tone, chưa gắn release gate |
| helpful | 100 | 0.375 | 1.0 | 0.3 | Không đạt | loại khỏi release gate |

Positive class = **FAIL**. Precision trả lời “judge gắn FAIL có đúng không”; recall đo số lỗi judge tìm được.

| Judge | TP | FP | FN | TN | Tỉ lệ FAIL quan sát | Rogan–Gladen |
|---|---|---|---|---|---|---|
| tone | 24 | 4 | 6 | 66 | 0.28 | 0.3 |
| helpful | 9 | 0 | 21 | 70 | 0.09 | 0.3 |

## ≥5 case audit thủ công

Kết luận dưới đây là phân tích reply và note có sẵn trong CSV public, không giả làm một đợt gán nhãn độc lập mới.

| # | Case | Judge nói | Người nói | Ai đúng và sửa rubric | Reply thực tế |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Đồng ý human: xưng em/nha quá suồng sã theo note. Rubric phải tách thân thiện khỏi suồng sã. | Em đã hoàn tiền cho anh rồi nha, anh check giúp em. |
| 2 | H-017 | PASS | FAIL | Đồng ý human theo ngữ cảnh tuổi trong note; reply đơn lẻ không chứng minh tuổi. Cấp ngữ cảnh xưng hô cho judge. | Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha. |
| 3 | H-029 | PASS | FAIL | Đồng ý human: 'không cần nhắn thêm' là giọng áp đặt. Chấm toàn câu, không chỉ các từ lịch sự. | Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm. |
| 4 | H-042 | FAIL | PASS | Đồng ý human: ngắn nhưng rõ số tiền/thời gian; không buộc câu xin lỗi ở mọi phản hồi. | Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ. |
| 5 | H-051 | FAIL | PASS | Đồng ý human theo glossary LogiX trong note: refund được phép; không cấm tiếng Anh tuyệt đối. | Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ. |
| 6 | HL-015 | PASS | FAIL | Đồng ý human theo evidence CSV: ledger ghi 40.000đ. Chuyển kiểm tiền sang code; lịch sự không bù sai tiền. | Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ. |
| 7 | HL-016 | PASS | FAIL | Đồng ý human theo evidence CSV: ledger ghi 35.000đ. Chuyển kiểm tiền sang code; lịch sự không bù sai tiền. | Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. LogiX đã hoàn 55.000đ cho đơn O-404. Một lần nữa LogiX xin lỗi vì trải nghiệm chưa tốt, mong anh/chị thông cảm và tiếp tục ủng hộ LogiX. |
| 8 | HL-020 | PASS | FAIL | Đồng ý human theo evidence CSV: ledger ghi 120.000đ. Chuyển kiểm tiền sang code; lịch sự không bù sai tiền. | Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ. |
| 9 | HL-028 | PASS | FAIL | Đồng ý human theo evidence CSV: ledger ghi 35.000đ. Chuyển kiểm tiền sang code; lịch sự không bù sai tiền. | Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. LogiX đã hoàn 50.000đ cho đơn O-677. LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. |
| 10 | HL-035 | PASS | FAIL | Đồng ý human theo evidence CSV: ledger ghi 35.000đ. Chuyển kiểm tiền sang code; lịch sự không bù sai tiền. | Dạ, Một lần nữa LogiX xin lỗi vì trải nghiệm chưa tốt, mong anh/chị thông cảm và tiếp tục ủng hộ LogiX. LogiX đã hoàn 50.000đ cho đơn O-303. LogiX thành thật xin lỗi anh/chị vì sự bất tiện này và rất trân trọng sự kiên nhẫn của anh/chị. |

## Kết luận

Helpful có FN=21/30 lỗi thật, recall=0.300 và κ=0.375 dưới floors; precision=1.0 không cứu được khả năng bỏ sót 70% lỗi.
Vì vậy lệnh helpful **exit 1 là kết quả mong đợi** và helpful không được dùng làm release gate. Tiền được kiểm bằng ledger/code, không nhờ đánh giá văn phong.
Tone exit 0, đạt floors trên tập replay; đây chỉ là điều kiện cần cho tiêu chí tone. Spec hiện tại chưa dùng tone làm blocking metric.
Kappa không xác định hoặc Rogan–Gladen không định danh được sẽ fail calibration rõ ràng; có regression test cho judge hằng PASS.

Rủi ro còn lại: CSV đã công khai, không có held-out mới, note ngữ cảnh có thể ảnh hưởng kết luận, judge replay không đo drift hay độ ổn định model thật.
Cần người đánh giá độc lập và tập mới phân tầng trước khi áp dụng thực tế; sau sửa rubric phải calibrate lại, không chỉnh nhãn để đạt floors.
Bằng chứng: [judge_calibration.json](../src/reports/judge_calibration.json), [tone log](../src/reports/judge_tone.txt), [helpful log](../src/reports/judge_helpful.txt).
