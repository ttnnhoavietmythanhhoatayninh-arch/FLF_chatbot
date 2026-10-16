# Kiểm chứng phiên bản 1.1 — 16/10/2026

## Môi trường và kết quả

Python 3.12.14, Linux x86_64. Tạo môi trường ảo mới `/tmp/excelqa-upgrade-verify`, cài offline bằng wheel có SHA-256 trong requirements: openpyxl 3.1.5, et_xmlfile 2.0.0, defusedxml 0.7.1.

| Kiểm tra | Kết quả thực đo |
|---|---|
| Unit/integration tests | 55/55 đạt trong môi trường mới |
| Public 1 offline | 14/20 đúng; 6 rỗng; 0 đáp án sai không rỗng |
| Public 2 trước nâng cấp, offline | 0/30 đúng; 30 rỗng |
| Public 2 sau nâng cấp, offline | 7/30 đúng; 23 rỗng; 0 đáp án sai không rỗng |
| Public 2 đổi tên workbook/sheet, thêm sheet trống, dời dữ liệu và vùng gộp xuống 5 hàng | Cả 7 câu đã giải vẫn đúng |
| Sáu tham số BTC qua API HTTP giả lập | Đạt; đầu vào không thay đổi byte; không in key |
| ID dạng số | Sắp 1,2,10; giữ biểu diễn ID nguồn; chặn 2 và "002" trùng về giá trị |
| Đáp án rỗng theo FAQ | CSV hợp lệ, main trả 0 nếu không có lỗi thực thi cứng |
| Kiểu đáp án | Test số nguyên, 1/2/3 chữ số thập phân, tên kèm số, năm kèm số và tuple |
| Bộ tính | Lọc ô thiếu bằng is_numeric, short-circuit, tỷ lệ phần trăm, biểu thức có bằng chứng ô |
| Token | Test nhận reasoning riêng, không cộng completion thay reasoning |

Câu offline đợt 2: 6, 7, 17, 19, 20, 28, 29. Đây là danh sách báo cáo, không được dùng định tuyến trong mã giải. Bộ giải khớp cấu trúc và đọc giá trị hiện tại, không biết ID hoặc tên file.

Lượt chạy môi trường mới: public 1 khoảng 0,35 giây, peak RSS 23,61 MiB; public 2 khoảng 0,80 giây, peak RSS 29,85 MiB. Đây là số đo offline, không mô tả thời gian API hoặc Docker. Có báo cáo tóm tắt máy đọc tại `reports/public_results.json`.

## Cách tái hiện

Chạy các lệnh cài thư viện/kiểm thử trong README, sau đó:

```powershell
.\.venv\Scripts\python.exe tools\benchmark.py --data-dir "C:\DuLieu\Public data 1" --output-dir "C:\ExcelQA_Output\public1-offline" --solver offline
.\.venv\Scripts\python.exe tools\benchmark.py --data-dir "C:\DuLieu\Public data 2" --output-dir "C:\ExcelQA_Output\public2-offline" --solver offline
```

Đối chiếu nguyên dạng chuỗi; không khẳng định mô phỏng đầy đủ chuẩn hóa BTC. Kết quả benchmark mã 1 khi còn câu chưa khớp; cần xem evaluation.json. Main mã 0 chỉ xác nhận CSV hợp lệ, không phải đạt toàn bộ câu.

Kiểm thử mới được viết và xác nhận thất bại trước khi sửa: sắp ID số, ID tương đương trùng, định dạng nhiều ngôn ngữ, đáp án ghép, lọc số thiếu, NAICS, chuỗi năm, nam/nữ, tỷ lệ, JSON reference và reasoning usage. Các test thay số liệu/năm/nhãn không dùng đáp án công khai làm quy tắc chạy.

## Chưa kiểm chứng

- OpenRouter thật: chưa được cung cấp API key cho lượt chạy này; chưa đo Qwen tự lập kế hoạch đúng bao nhiêu câu, phí hoặc độ trễ thực. 23 câu offline chưa trả lời không được xem là đã giải bởi LLM.
- Docker build/run, kích thước ảnh và tổng disk 1 GB: môi trường không có Docker CLI/daemon. Không khẳng định đạt giới hạn disk chỉ dựa vào kích thước ZIP.
- PowerShell/Windows: chưa thực thi script trên máy Windows.
- Dữ liệu ẩn: chưa có; độ đúng trên công khai không bảo đảm kết quả bộ ẩn.

Cần chạy Docker bằng key thật, đối chiếu đáp án và đo tài nguyên trước nộp. FAQ cho phép câu rỗng; vẫn cần giảm số câu rỗng để tăng điểm. Không cam kết không có sai sót.
