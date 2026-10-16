# Hướng nâng cấp từ bộ công khai đợt 2

## Mục tiêu

Giữ kiến trúc Qwen lập kế hoạch → Python tính trên ô nguồn → CSV, nâng khả năng hiểu bảng mới và giảm số lần gọi API. Không huấn luyện hay tạo một ChatGPT mới, không ghi nhớ answers.json.

## Căn cứ từ dữ liệu thực tế

Bộ đợt 2: 15 XLSX, 30 câu ID số; 24 câu tiếng Anh, 3 Việt, 1 Pháp, 1 Hàn, 1 Trung. Có workbook nhiều sheet; bảng lớn nhất 1.071 dòng. Context lớn nhất khoảng 124 KB, dưới mức mặc định 200 KB. Các câu yêu cầu hiểu tiêu đề nhiều tầng, nhóm cha/con, NAICS, tổng so với thành phần, hàng năm so với quý, năm tài chính, lọc nhiều điều kiện, phần trăm và định dạng số.

Các đáp án có thể là số, nhãn nguồn, danh sách xếp hạng hoặc cặp tên/số. Cần giữ đúng số chữ số thập phân: 0.70 không tự bỏ thành 0.7 khi câu yêu cầu hai chữ số.

## Đã thực hiện ở phiên bản 1.1

- Thêm bộ giải theo cấu trúc cho giảm việc làm theo năm, năm có nông nghiệp cao nhất, đếm mã NAICS đúng độ dài, so sánh chuỗi năm, chênh lệch/tỷ lệ nam–nữ trong bảng tiếng Việt.
- Không giả định bộ giải heuristic tiếng Anh hiểu câu hỏi ngôn ngữ khác; các trường hợp chưa hỗ trợ chuyển Qwen.
- Bổ sung `is_numeric`, điều kiện and/or ngắn mạch, percent_ratio và định dạng tuple để hỗ trợ kế hoạch LLM trên bảng có ô thiếu và đáp án ghép.
- Nhận diện số chữ số thập phân qua các mẫu trong năm ngôn ngữ xuất hiện; đây không phải bộ hiểu ngôn ngữ đầy đủ.
- Sửa thứ tự ID dạng số; chặn ID số tương đương bị trùng; chấp nhận đáp án rỗng theo FAQ.
- Giới hạn RAM thử nghiệm 4 GB, tách disk 1 GB; ghi token input + reasoning khi có đủ usage.
- Công cụ benchmark chạy giải bài trước, sau đó mới đọc answers.json để chấm; ứng dụng không nhận đường dẫn đáp án.

## Thứ tự công việc tiếp theo

### 1. Chạy API thật để xác định lỗi còn lại

Dùng lệnh hybrid trong README; đọc evaluation.json cùng run_report.json. 23 câu đợt 2 chưa giải offline là 1–5, 8–16, 18, 21–27 và 30. Không kết luận Qwen giải được các câu này khi chưa chạy thật. Kiểm tra key/model trước khi chạy toàn bộ. Chỉ thử lại câu lỗi sau khi đã xác định nguyên nhân; tránh chạy lặp cả bộ tốn phí.

### 2. Sửa theo nhóm nguyên nhân

- Câu 1–5, 10–16: giữ toàn bộ tiêu đề tầng, nhóm người/năm/giới tính và hàng tổng; xác minh lựa chọn cột trước khi tính.
- Câu 8–9: lọc nhiều điều kiện trên cùng một hàng, không lấy điều kiện ở các năm khác nhau.
- Câu 17–18: mã phân loại đúng sáu chữ số; đọc tỷ lệ tổng đã báo cáo thay vì cộng tỷ lệ thành phần.
- Câu 19–20: chỉ hàng năm thuộc chuỗi chỉ số, không thêm hàng mức chuẩn hoặc các quý.
- Câu 21–24: chọn đúng sheet, năm tài chính và kỳ báo cáo; xác minh mẫu số của tỷ lệ.
- Câu 25–30: hiểu câu hỏi và nhãn bảng qua ngôn ngữ khác nhau; giữ đúng yêu cầu làm tròn, dòng loại trừ và dấu chênh lệch.

Đây là phân nhóm để phân tích lỗi, không phải bảng định tuyến dùng trong chương trình. Mọi sửa đổi phải áp dụng bằng cấu trúc và ngữ nghĩa, không kiểm tra ID/tên file để trả đáp án.

### 3. Kiểm chứng khả năng khái quát

Với mỗi lỗi đã sửa: viết test thay số, đổi nhãn/năm, đổi tên sheet và dời bảng; xác nhận đáp án đổi theo dữ liệu. Chạy lại cả đợt 1 và 2, so hybrid với llm ở những câu local có dấu hiệu chọn sai. Không tăng độ bao phủ offline bằng các quy tắc quá rộng gây đáp án đoán.

### 4. Tối ưu sau khi độ chính xác đã ổn định

Giữ cache một workbook; dùng biểu thức table thay danh sách dài. Đo call/token/latency trước khi thêm song song. Không bỏ dòng ngữ cảnh bằng vài dòng preview cho câu hỏi cực trị/đếm toàn bảng. Nếu phải chia bảng, cần cơ chế tổng hợp đủ mọi phần và đo lại phí/thời gian; bản này chưa có cơ chế chia bảng lớn vượt context.

### 5. Kiểm chứng gói thi

Build Docker Linux amd64; chạy đủ tham số BTC bằng key thật; đo RAM và disk trong Docker; đo thời gian và chi phí từng câu có retry. Kiểm tra CSV, chuỗi rỗng và thứ tự số. Tạo ZIP bằng package.py, đúng tên đội và Dockerfile ngay gốc. Các bước Docker/API thật chưa được chứng minh bởi báo cáo offline.

## Tiêu chí đánh giá

Ưu tiên số câu đúng, sau đó thời gian trung bình và token theo đề. Exact string match nội bộ nghiêm hơn một số chuẩn hóa BTC công bố; cần xem cả nội dung sai và định dạng. Không tự coi hai số trùng nhau là đủ khi câu hỏi yêu cầu một nhãn hoặc một phạm vi khác.
