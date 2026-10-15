# Báo cáo kiểm thử ExcelQA 2026

## Đã kiểm chứng

Môi trường: Linux x86_64, Python 3.12.14. Tạo môi trường ảo mới, cài từ wheel đi kèm bằng `--no-index --require-hashes`. Phiên bản: openpyxl 3.1.5, et_xmlfile 2.0.0, defusedxml 0.7.1. Đã xác nhận openpyxl bật defusedxml.

| Phép kiểm tra | Kết quả |
|---|---|
| Bộ kiểm thử tự động | 40/40 đạt |
| Gọi API bằng máy chủ HTTP giả lập | Đạt gửi model/câu hỏi, nhận kế hoạch, ghi CSV; xử lý 401, phản hồi bị cắt, thiếu usage và giá model |
| Sáu tham số của BTC | Đã kiểm thử qua main.py, có API giả lập |
| Dữ liệu công khai đợt 1, chế độ offline | 14/20 khớp Exact Match; 6 câu chưa giải, không xuất đáp án đoán |
| Thay đổi bố cục với 14 câu trên | 14/14 vẫn đúng khi đổi tên workbook, đổi tên sheet, thêm sheet trống và dời bảng xuống 4 dòng |
| Thay số liệu trong bảng tổng hợp tạo mới | Đáp án thay đổi theo số liệu mới; có kiểm thử tự động |
| Bộ tính cho 6 câu còn lại | Kế hoạch tham chiếu ô được kiểm tra thủ công cho kết quả khớp 6/6; không phải bằng chứng LLM tự tạo đúng kế hoạch |
| Đọc đầu vào | Kiểm tra byte trước/sau không đổi trong kiểm thử tích hợp |
| CSV | UTF-8; id,answer; giữ ID có số 0 đầu; dấu phẩy trong đáp án được bao đúng |
| An toàn thực thi | Không eval/exec mã LLM; từ chối ô giả, ngưỡng không có trong câu hỏi và đường dẫn vượt thư mục |
| Cài phụ thuộc | Thành công từ wheel đi kèm, xác minh hash, không cần truy cập kho gói |

Lượt offline cuối trên máy phát triển: khoảng 0,29 giây; peak RSS khoảng 23,7 MiB. Hai số này chỉ mô tả lượt **không gọi LLM** trên bộ công khai; không phải thời gian hoặc bộ nhớ đo trong Docker hay trong lượt chấm thực tế.

Sáu câu cần LLM ở cấu hình hybrid hiện tại: p4_q002, p4_q003, p4_q004, p4_q005, p4_q015, p4_q019. Chương trình không dùng danh sách này khi giải bài; định tuyến dựa vào nội dung câu hỏi và cấu trúc bảng.

Các kế hoạch thủ công dùng để kiểm tra bộ tính được giữ ngoài mã nguồn vận hành. Không có bảng ánh xạ ID sang đáp án trong main.py hoặc excelqa/. Công cụ evaluate.py đọc đáp án mẫu chỉ để đánh giá, không được ứng dụng giải bài nhập vào.

## Phần chưa kiểm chứng

- **OpenRouter thật:** chưa có API key của đội. Chưa đo độ chính xác của Qwen, độ trễ, chi phí thực và khả năng sẵn sàng của provider khi chạy cả bộ.
- **Docker build và docker run:** môi trường phát triển không có Docker daemon/CLI. Dockerfile đã được đối chiếu cấu trúc, nhưng chưa có bằng chứng build hoặc chạy container thành công.
- **Windows PowerShell:** script hỗ trợ được cung cấp để chạy tại máy đội; chưa chạy bằng PowerShell trong môi trường phát triển Linux.
- **Dữ liệu công khai lần 2 và dữ liệu ẩn:** chưa có trong tệp được cung cấp ở lần xây dựng này.

Đây là các phần cần kiểm tra tiếp trước khi nộp, không được xem là đã đạt. Không có cam kết 20/20 hay không có sai sót trên dữ liệu mới.

## Kiểm tra trước nộp

1. Làm theo README, build và chạy trên Docker Linux amd64 bằng API key thật của đội.
2. Yêu cầu mã thoát 0 và failed=0; đối chiếu các câu trả lời và ngân sách thực.
3. Chạy thêm dữ liệu công khai đợt 2; sửa nguyên nhân chung nếu có lỗi.
4. Nếu bộ giải trực tiếp chọn sai ngữ nghĩa trên cấu trúc mới, đối chiếu `--solver llm` trước khi chốt cấu hình.
5. Đổi tên ZIP đúng tên đội; giữ Dockerfile ở gốc; kiểm tra không có khóa.
