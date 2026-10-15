# ExcelQA 2026

Chương trình hỏi đáp trên Excel cho Vòng Khu vực Bảng C. Gói nộp dùng Docker Linux amd64, CPU; nhận đúng sáu tham số trong PDF hướng dẫn nộp bài của BTC.

**Trạng thái kiểm chứng:** bộ tính và giao diện API đã được kiểm thử tự động bằng HTTP giả lập. Trên dữ liệu công khai đợt 1, chế độ không gọi AI trả lời đúng 14/20 câu; 6 câu còn lại được chuyển sang LLM khi có khóa thật. Chưa kiểm chứng lượt chạy với OpenRouter thật hoặc Docker trong môi trường phát triển hiện tại. Không coi kết quả này là đạt 20/20 hoặc bảo đảm điểm trên bộ ẩn. Chạy kiểm tra thực ở mục 2 trước khi nộp.

## 1 Nội dung gói

- `Dockerfile` nằm ngay gốc ZIP, không nằm trong thư mục con.
- `main.py`: chương trình trong ENTRYPOINT, đọc tham số, quản lý thời gian, xuất kết quả.
- `excelqa/workbook.py`: đọc mọi sheet, tọa độ, ô gộp, ngày và công thức có giá trị lưu.
- `excelqa/local.py`: giải trực tiếp một số phép truy xuất, so sánh, tổng, trung bình và thứ hạng khi nhận diện được cấu trúc.
- `excelqa/prompts.py`, `solver.py`: yêu cầu Qwen lập kế hoạch từ dữ liệu nguồn và sửa kế hoạch không hợp lệ.
- `excelqa/expressions.py`: kiểm tra và thực thi biểu thức khai báo; không chạy mã Python do LLM sinh.
- `excelqa/api.py`, `budget.py`: gọi đúng model, giới hạn giá/token, theo dõi chi phí gồm retry.
- `tests/`: kiểm thử dữ liệu mới, lỗi API, CSV và hợp đồng dòng lệnh.
- `tools/evaluate.py`: đối chiếu Exact Match; tách khỏi luồng giải bài.
- `RUN_WINDOWS.ps1`: trợ giúp build và chạy Docker trên Windows.

Thư mục dependency_wheels chứa đúng phiên bản thư viện, được kiểm tra SHA-256 khi cài. Không kèm API key, đáp án cố định, bộ dữ liệu công khai, môi trường ảo hoặc tệp kết quả làm sẵn. Chương trình giải không đọc `sample_submission.csv`.

## 2 Chạy trên Windows bằng Docker Desktop

1. Cài và khởi động Docker Desktop theo tài liệu chính thức: https://docs.docker.com/desktop/setup/install/windows-install/ . Dùng Linux containers, không dùng Windows containers.
2. Giải nén gói này vào một thư mục, ví dụ `C:\ExcelQA2026`. Mở PowerShell tại đó.
3. Giải nén dữ liệu BTC vào một thư mục riêng. Thư mục truyền cho `-DataDir` phải chứa `queries.json` và thư mục `xlsx_files`.
4. Chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_WINDOWS.ps1 -DataDir "C:\DuLieu\Public data 1" -OutputDir "C:\ExcelQA_Output"
```

Script yêu cầu nhập API key bằng ô nhập ẩn nếu biến môi trường chưa có khóa. Không lưu khóa vào tệp hoặc ghi khóa ra màn hình. Khóa được chuyển vào container qua biến môi trường cho lượt chạy thử; hệ thống BTC có thể truyền bằng `--openrouter-key` như mục 3.

Script build ảnh Linux amd64, đặt giới hạn 1 GB và 6 CPU, gắn đầu vào chỉ đọc, gắn thư mục kết quả riêng có quyền ghi. Các thư viện đã được cài vào ảnh ở bước build; khi chạy không cài thêm thư viện. Gói có sẵn wheel Python và mã băm để cài phụ thuộc không qua mạng; chỉ cần mạng để lấy ảnh nền Docker nếu máy chưa có, và để kết nối OpenRouter khi chạy LLM.

Sau khi hoàn tất, kiểm tra:

- `submission.csv`: CSV UTF-8 với hai cột `id,answer`.
- `run_report.json`: trạng thái từng câu, ô nguồn, kế hoạch tính, thời gian, token và chi phí đã ghi nhận hoặc dự phòng.
- Mã thoát phải bằng 0; `failed` phải bằng 0. Nếu mã thoát 2, CSV có thể là kết quả chẩn đoán với câu chưa trả lời; không coi đó là lượt chạy thành công.

Đối chiếu với tệp mẫu bằng Python, hoặc mở CSV bằng công cụ giữ nguyên chuỗi và số 0 đầu ID. Không lưu lại CSV bằng Excel nếu chưa kiểm soát tự đổi kiểu dữ liệu.

## 3 Hợp đồng chạy đúng hướng dẫn BTC

Build ảnh:

```bash
docker build --platform linux/amd64 -t excelqa2026 .
```

Dockerfile khai báo:

```dockerfile
ENTRYPOINT ["python", "/app/main.py"]
```

Ví dụ sáu tham số được hệ thống chấm truyền vào ENTRYPOINT:

```text
--xlsx-dir /input/xlsx_files
--queries /input/queries.json
--output /output/submission.csv
--openrouter-key <KEY_DO_HE_THONG_TRUYEN>
--openrouter-model qwen/qwen3.7-flash
--openrouter-base-url https://openrouter.ai/api/v1
```

Ví dụ chạy từ Linux/macOS với khóa đã nằm trong biến môi trường, không ghi khóa thật vào tệp lệnh:

```bash
mkdir -p output
docker run --rm --platform linux/amd64 --memory=1g --cpus=6 \
  --read-only --tmpfs /tmp:rw,size=64m \
  -v "/ABSOLUTE/DATA:/input:ro" \
  -v "$PWD/output:/output" \
  -e OPENROUTER_API_KEY excelqa2026 \
  --xlsx-dir /input/xlsx_files \
  --queries /input/queries.json \
  --output /output/submission.csv \
  --openrouter-model qwen/qwen3.7-flash \
  --openrouter-base-url https://openrouter.ai/api/v1 \
  --report /output/run_report.json
```

Đổi `/ABSOLUTE/DATA` thành đường dẫn dữ liệu thật. `--report` là tùy chọn của giải pháp, không phải tham số BTC bắt buộc. Chương trình nhận `--openrouter-key` và ưu tiên giá trị tham số đó; biến `OPENROUTER_API_KEY` chỉ là phương án thay thế khi chạy thử.

Chỉ mô hình `qwen/qwen3.7-flash` được chấp nhận. Không tự chuyển sang mô hình khác. Base URL thật được giới hạn ở `https://openrouter.ai/api/v1`; các phép thử HTTP cục bộ chỉ được bật bên trong kiểm thử, không phải đường vòng trong CLI thi.

## 4 Cách chương trình trả lời

1. Kiểm tra JSON, ID không thiếu/trùng, đường dẫn nằm trong thư mục Excel được cấp.
2. Đọc tệp trong `file_name`, mọi sheet và danh sách vùng gộp; giữ tọa độ gốc.
3. Ở chế độ mặc định `hybrid`, thử bộ giải trực tiếp cho những cấu trúc được hỗ trợ. Nếu không tạo được kế hoạch hợp lệ thì gọi Qwen.
4. Qwen nhận câu hỏi cùng biểu diễn ô và tiêu đề từ tệp tương ứng; trả về kế hoạch JSON dùng tọa độ và phép toán được cho phép.
5. Bộ tính kiểm tra sheet/ô có thật, kiểu số/ngày, phạm vi và độ phức tạp; tính bằng Python/Decimal. Không nhận một đáp án số được LLM viết sẵn thay cho phép tính từ nguồn.
6. Lỗi kế hoạch có thể được yêu cầu sửa, tối đa 3 lượt API/câu gồm lượt đầu. Retry vẫn phải nằm trong thời gian và ngân sách.
7. Định dạng theo query: số nguyên, chữ số thập phân, Yes/No hoặc danh sách ngăn bằng dấu phẩy và một khoảng trắng. Đầu ra không kèm giải thích.
8. Ghi CSV tạm, đọc kiểm tra cấu trúc và ID, rồi thay thế nguyên tử sang đúng `--output`. Nhật ký đi stderr.

`--solver llm` bỏ bộ giải trực tiếp, để Qwen lập kế hoạch mọi câu. Dùng tùy chọn này để so sánh với hybrid trên dữ liệu đợt 2 nếu thấy bộ giải trực tiếp chọn sai ngữ nghĩa. Không mặc định cách nào có điểm cao hơn khi chưa đo.

`--solver offline` không gọi mạng và có thể không giải hết. Dùng để thử bộ đọc/bộ tính và đo chi phí 0; không dùng lượt chạy thiếu câu này làm minh chứng hoàn thành bài thi.

## 5 Giới hạn và kiểm soát

| Nội dung | Cách thực hiện |
|---|---|
| Chi phí BTC không quá 0,10 USD/câu/mỗi lần chấm | Mặc định trần nội bộ 0,09 USD/câu, cộng mọi lượt thử lại; không dồn ngân sách giữa câu. |
| Kiểm tra trước yêu cầu | Đọc giá model từ `/models`; đặt `provider.max_price` và `max_tokens`; dự phòng đầu vào theo số byte UTF-8 cộng phần dư. Nếu không xác minh được giá thì không gọi mù. |
| Giá thiếu hoặc chi phí thiếu | Thiếu giá thì báo lỗi; thiếu cost nhưng có token thì tính theo giá trần; thiếu cả usage thì giữ khoản dự phòng, không ghi bằng 0. Khoản dự phòng không đồng nghĩa hóa đơn thực. BTC ghi nhận chi phí chính thức. |
| Không đổi mô hình | Khóa model theo yêu cầu BTC; không có model fallback. |
| Thời gian 40 phút cho 20 câu | Mặc định 2.300 giây toàn lượt, giữ dư địa xuất CSV; 110 giây/câu theo phân bổ thời gian còn lại. Linux có timer để ngắt khi hết thời gian. |
| Bộ nhớ giải pháp không quá 1 GB | Chạy một tiến trình CPU; Linux áp dụng trần không gian địa chỉ 900 MiB; chỉ giữ một workbook trong cache. Docker chạy thử đặt `--memory=1g`. |
| ZIP không quá 100 MB | Script đóng gói kiểm tra ≤100.000.000 byte và Dockerfile ở gốc. |
| Không sửa đầu vào | Kiểm tra đường dẫn đầu ra; chạy Docker với `/input:ro`. |

Mô hình có thể lập kế hoạch sai ngữ nghĩa dù biểu thức hợp lệ. Kiểm tra tọa độ giúp truy vết và chặn ô giả, không chứng minh AI đã hiểu đúng câu hỏi. Không có bảo đảm đúng toàn bộ bộ ẩn.

Làm tròn phần thập phân dùng Decimal với ROUND_HALF_UP; nếu BTC công bố quy ước khác phải chỉnh theo quy ước đó. Không tự nhân số liệu “in thousands” nếu câu hỏi không yêu cầu chuyển đơn vị.

Công thức Excel: dùng giá trị cache nếu có; hỗ trợ tham chiếu trực tiếp cùng sheet khi cache thiếu. Không có bộ tính Excel đầy đủ. Ô công thức chưa có giá trị không bị biến thành số 0. Workbook quá lớn, vùng trống làm phình kích thước hoặc ngữ cảnh trên 200.000 byte sẽ bị từ chối thay vì cắt dữ liệu âm thầm. `--max-context-bytes` có thể tăng tối đa 1.000.000 sau khi kiểm tra chi phí và thời gian.

## 6 Kiểm thử bằng Python không cần Docker

Cần Python 3.12 và thư viện trong requirements; không cần GPU.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links dependency_wheels --require-hashes -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Chạy dữ liệu thật với khóa lấy từ biến môi trường (đặt khóa ngoài tệp mã):

```powershell
.\.venv\Scripts\python.exe main.py --xlsx-dir "C:\DuLieu\Public data 1\xlsx_files" --queries "C:\DuLieu\Public data 1\queries.json" --output "C:\ExcelQA_Output\submission.csv" --report "C:\ExcelQA_Output\run_report.json"
```

Đánh giá Exact Match sau khi đã chạy chương trình:

```powershell
.\.venv\Scripts\python.exe tools\evaluate.py --queries "C:\DuLieu\Public data 1\queries.json" --prediction "C:\ExcelQA_Output\submission.csv" --reference "C:\DuLieu\Public data 1\sample_submission.csv" --report "C:\ExcelQA_Output\evaluation.json"
```

`evaluate.py` so chuỗi đúng nguyên dạng sau khi đọc CSV; mã thoát 0 nếu mọi câu khớp, 1 nếu có câu lệch, 2 nếu định dạng/ID không hợp lệ. Bộ so sánh nội bộ không thay thế trình chấm BTC.

Khi có dữ liệu công khai đợt 2, giữ riêng hai thư mục, chạy bản hiện tại trên bộ mới trước khi sửa, sau đó chạy lại cả hai bộ. Không thêm ánh xạ đáp án theo ID, tên file hoặc tọa độ mẫu.

## 7 Đóng gói theo tên đội và nộp

Tên đội chưa được cung cấp nên gói phân phối đang dùng tên `TEN_DOI.zip`. **Trước khi nộp, đổi tên ZIP đúng tên đội trên hệ thống.** Nếu sửa mã hoặc muốn tạo lại gói:

```powershell
.\.venv\Scripts\python.exe tools\package.py --team TEN_DOI_THAT --out dist
```

Không nén cả thư mục cha thành một lớp bao ngoài. Mở ZIP và kiểm tra thấy `Dockerfile` ngay ở gốc. Script đóng gói loại dữ liệu, cache, môi trường ảo và chỉ lấy danh sách mã cần thiết. Tệp MANIFEST.sha256 giúp kiểm tra nội dung đã đóng gói.

Trước khi tải lên https://ai.tainangviet.vn:

- Build ảnh Linux amd64 thành công.
- Chạy đủ câu với API thật, `failed=0` và mã thoát 0.
- Kiểm tra kết quả, chi phí, thời gian và bộ nhớ; thử dữ liệu đợt 2 khi đã công bố.
- ZIP đúng tên đội, không quá 100 MB, Dockerfile ở gốc, không có khóa.
- Kiểm tra hệ thống đã ghi nhận đúng bản nộp cuối.

Hạn nộp theo đề gốc: 12:00 ngày 17/10/2026; ưu tiên thông báo cập nhật chính thức nếu có. Đội cần giải thích được bộ đọc, bộ lập kế hoạch, bộ tính, chi phí và cách sửa mã trong phần xác minh.

## 8 Nguồn kỹ thuật

- PDF BTC “Hướng dẫn nộp bài Bảng C” do đội cung cấp: cấu trúc ZIP, Docker, ENTRYPOINT, sáu tham số, CSV và đầu vào chỉ đọc.
- Ba ảnh đề “Chủ đề 2 Hỏi đáp trên bảng tính Excel”: giới hạn và xếp hạng.
- https://openrouter.ai/docs/api_reference/overview
- https://openrouter.ai/docs/guides/routing/provider-selection#max-price
- https://docs.docker.com/reference/dockerfile/
- https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html
