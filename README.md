# ExcelQA 2026 — phiên bản 1.1.1

Giải pháp hỏi đáp trên bảng tính Excel cho Vòng Khu vực Bảng C. Đọc `xlsx_files/` và `queries.json`, tính đáp án từ ô nguồn, xuất CSV UTF-8 `id,answer`. Docker Linux amd64, CPU; nhận sáu tham số trong hướng dẫn BTC.

**Kết quả đã đo, không gọi API:** đợt 1 đúng 14/20; đợt 2 đúng 9/30, còn 21 câu offline chưa giải được. Không có đáp án sai trong các câu offline đã trả lời. Đây không phải kết quả chạy Qwen thật hoặc điểm dự kiến trên bộ ẩn. Chưa kiểm chứng Docker và OpenRouter thật vì môi trường hiện tại không có Docker/API key. Xem `VALIDATION.md` và `UPGRADE_PLAN.md`.

## Chạy tiếp trên máy thứ nhất, không nạp tiền API

Không cài lại Docker, Python hoặc dự án. Windows launcher mặc định `offline`: không hỏi key, không truyền key vào container và chặn mạng container bằng `--network=none`. Docker build có thể tải base image; đây không phải lời gọi LLM. Để giữ cache và dùng mã mới, build một lần sau mỗi lần sửa mã. Những lần chạy lại không đổi mã có thể thêm `-SkipBuild`.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_WINDOWS.ps1 -DataDir "D:\Download\IMG\0.BC\Publicdata2" -OutputDir "$env:USERPROFILE\ExcelQA_KetQua_Offline" -Solver offline -Cpus 4
```

`llm_calls` phải bằng 0. CSV ghi đủ ID; câu chưa hỗ trợ để rỗng theo FAQ. Bản này đúng 9/30 public 2 khi không gọi API, không phải giải pháp đã hoàn thiện độ chính xác. `Completed` chỉ xác nhận chương trình ghi kết quả. Không thay mô hình runtime bằng Gemini hoặc mô hình miễn phí khác. Giao diện sáu cờ của BTC và mặc định hybrid của ENTRYPOINT vẫn được giữ để nhận key/model do BTC cung cấp khi chấm. Windows launcher mặc định offline chỉ phục vụ việc thử miễn phí trên máy cá nhân.

Bổ sung 1.1.1: lọc năm với hai điều kiện trong bảng lao động, tự đọc tiêu đề nhiều tầng và ngưỡng trong câu hỏi, từ chối nếu có nhiều năm phù hợp. Không tra đáp án theo ID/tên tệp. Windows launcher tự giới hạn CPU theo máy, tối đa 6; có thể chỉ định `-Cpus 4`.

## 1. Chạy thử bộ dữ liệu đợt 2 trên Windows

Giải nén dữ liệu BTC ra thư mục riêng. Ví dụ `C:\DuLieu\Public data 2` phải chứa:

- `xlsx_files\`: 15 workbook.
- `queries.json`: 30 câu hỏi, ID 1–30.
- `answers.json`: đáp án đối chiếu, chỉ công cụ đánh giá đọc.
- `sample_submission.csv`: CSV mẫu.

Mở PowerShell tại thư mục mã nguồn vừa tải từ GitHub. Cài đúng Python 3.12 và thư viện đã đóng kèm:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links dependency_wheels --require-hashes -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Chạy trước ở chế độ không tốn phí API:

```powershell
.\.venv\Scripts\python.exe tools\benchmark.py --data-dir "C:\DuLieu\Public data 2" --output-dir "C:\ExcelQA_Output\public2-offline" --solver offline
```

Kết quả trong output-dir:

- `submission.csv`: đáp án, các câu không giải được để chuỗi rỗng.
- `run_report.json`: kế hoạch, ô nguồn, thời gian và token.
- `evaluation.json`: số câu khớp nguyên dạng, sai, chưa trả lời và danh sách chênh lệch.

`benchmark.py` trả mã 1 nếu có câu chưa khớp đáp án, mã 0 nếu khớp hết, mã 2 nếu lỗi thực thi/định dạng. Mã 1 trong lượt offline còn thiếu câu là kết quả đánh giá, không phải lỗi cài đặt. Công cụ so sánh dùng chuỗi nguyên dạng, không mô phỏng hoàn toàn chuẩn hóa của BTC.

## 2. Chạy hybrid với API key thật

Dùng key được cấp theo hướng dẫn BTC; không đưa key vào mã nguồn, README hoặc GitHub. Mô hình duy nhất của giải pháp: `qwen/qwen3.7-flash`, qua `https://openrouter.ai/api/v1`.

Nhập key trong cùng cửa sổ PowerShell, không hiện ký tự:

```powershell
$secureKey = Read-Host "OpenRouter API key" -AsSecureString
$env:OPENROUTER_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
Remove-Variable secureKey
```

Chạy bộ đợt 2:

```powershell
.\.venv\Scripts\python.exe tools\benchmark.py --data-dir "C:\DuLieu\Public data 2" --output-dir "C:\ExcelQA_Output\public2-hybrid" --solver hybrid
```

Hybrid ưu tiên các phép giải trực tiếp được hỗ trợ; chỉ gọi Qwen khi cần. Mỗi câu có trần nội bộ 0,09 USD, bao gồm thử lại; tối đa ba lượt API do bộ giải điều khiển. Kiểm tra chi phí và lỗi trong report; không coi một lượt API thành công là bằng chứng đáp án đúng.

Để so sánh hướng thuần LLM, dùng `--solver llm` và output-dir khác. Cách này có thể tốn phí hơn vì gọi AI cho mọi câu. Không gọi lại hàng loạt nếu chưa đọc các lỗi của lượt trước. Sau khi dùng xong:

```powershell
Remove-Item Env:OPENROUTER_API_KEY
```

## 3. Hợp đồng chạy của BTC

`Dockerfile` nằm ngay gốc gói nộp, ENTRYPOINT:

```dockerfile
ENTRYPOINT ["python", "/app/main.py"]
```

Sáu tham số do hệ thống truyền:

```text
--xlsx-dir /input/xlsx_files
--queries /input/queries.json
--output /output/submission.csv
--openrouter-key <KEY_DO_HE_THONG_TRUYEN>
--openrouter-model qwen/qwen3.7-flash
--openrouter-base-url https://openrouter.ai/api/v1
```

Chạy Docker Desktop bằng Linux containers trên Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\RUN_WINDOWS.ps1 -DataDir "C:\DuLieu\Public data 2" -OutputDir "C:\ExcelQA_Output\docker-public2"
```

Script build ảnh Linux amd64, đặt giới hạn RAM 4 GB và 6 CPU; đầu vào chỉ đọc. Các wheel có mã băm được cài lúc build, không cài thêm lúc chạy. Script chạy CSV và report; muốn đối chiếu, dùng mục 5.

Ví dụ Linux, với key đã có trong biến môi trường:

```bash
docker build --platform linux/amd64 -t excelqa2026 .
mkdir -p output
docker run --rm --platform linux/amd64 --memory=4g --cpus=6 \
  --read-only --tmpfs /tmp:rw,size=64m \
  -v "/ABSOLUTE/DATA:/input:ro" -v "$PWD/output:/output" \
  -e OPENROUTER_API_KEY excelqa2026 \
  --xlsx-dir /input/xlsx_files --queries /input/queries.json \
  --output /output/submission.csv \
  --openrouter-model qwen/qwen3.7-flash \
  --openrouter-base-url https://openrouter.ai/api/v1 \
  --report /output/run_report.json
```

`main.py` trả 0 khi hoàn tất CSV hợp lệ, kể cả câu chưa trả lời theo FAQ; báo cáo vẫn ghi `unanswered` và `failed`. Mã 0 không đồng nghĩa đúng hết. Lỗi đầu vào, workbook hỏng, ghi file hoặc hết thời gian trả mã 2. ID dạng số được sắp theo giá trị số tăng dần, không sắp chuỗi kiểu 1,10,2; vẫn đọc ID chuỗi của bộ đợt 1 để kiểm thử tương thích.

## 4. Kiến trúc và giới hạn

1. Đọc mọi sheet, giữ tọa độ, ô gộp và tiêu đề. Không đọc đáp án mẫu trong ứng dụng.
2. `local.py` và `structured.py` nhận diện một số dạng bài bằng nội dung câu hỏi và cấu trúc bảng. Không chọn đáp án theo ID hoặc tên file.
3. Nếu chưa hỗ trợ, Qwen nhận dữ liệu ô và câu hỏi để lập kế hoạch JSON. Không chạy mã Python do AI sinh ra.
4. `expressions.py` kiểm tra và tính biểu thức từ các ô thật. Hỗ trợ lọc, xếp hạng, chênh lệch, phần trăm, tuổi và định dạng đáp án ghép.
5. Ghi CSV nguyên tử; logs ra stderr. Lỗi không được ghi thành chuỗi `ERROR:` trong answer.

| Quy định | Cách áp dụng |
|---|---|
| Tối đa 0,10 USD/câu/lượt chấm | Trần mặc định 0,09; dự phòng trước API; đặt giá trần provider; tính cả retry. |
| 40 phút cho 20 câu theo đề | Toàn lượt mặc định 2.300 giây; tối đa 110 giây/câu và phân bổ theo thời gian còn lại. Bộ công khai 2 có 30 câu; số này không thay đổi quy định lượt chấm. |
| RAM tối đa 4 GB theo FAQ | Docker thử giới hạn 4g; Linux giới hạn không gian địa chỉ tiến trình 3.500 MiB. Đây là hai loại giới hạn khác nhau. |
| Disk tối đa 1 GB theo FAQ | Ít phụ thuộc, không chép dữ liệu vào ảnh. Cần đo ảnh/container thật trước nộp; chưa có số đo Docker trong môi trường hiện tại. |
| CSV UTF-8, ID tăng dần, bỏ trống khi không trả lời | Có kiểm thử. ID số biểu diễn tương đương như 2 và "002" không được trùng. |
| Token tính input + reasoning theo FAQ | Báo cáo riêng prompt/completion/reasoning. Tổng theo FAQ để null nếu API không cung cấp đủ reasoning usage; completion không được giả định là reasoning. |
| Trung bình "across all" | Bao gồm mọi cột trong phạm vi, kể cả Total, trừ khi câu hỏi loại trừ. |
| AI khi phát triển và khi chạy | FAQ cho phép dùng công cụ bất kỳ khi phát triển; giải pháp cuối chỉ gọi AI/LLM BTC quy định. |

Không thay đổi dữ liệu đầu vào. Chỉ truy cập mạng để cài phụ thuộc và gọi OpenRouter. Context giữ toàn bộ ô của workbook trong giới hạn mặc định 200.000 byte; vượt giới hạn thì từ chối thay vì cắt âm thầm. Có thể tăng `--max-context-bytes` đến 1.000.000 khi đã kiểm tra phí và thời gian.

Công thức dùng giá trị cache; chỉ hỗ trợ bổ sung tham chiếu trực tiếp cùng sheet khi cache thiếu. Chưa có bộ tính Excel đầy đủ. Biểu thức hợp lệ vẫn có thể sai ngữ nghĩa do AI chọn nhầm phạm vi; cần đánh giá thực tế.

## 5. Đối chiếu và đóng gói

Đối chiếu riêng với `answers.json` đợt 2:

```powershell
.\.venv\Scripts\python.exe tools\evaluate.py --queries "C:\DuLieu\Public data 2\queries.json" --prediction "C:\ExcelQA_Output\docker-public2\submission.csv" --reference "C:\DuLieu\Public data 2\answers.json" --report "C:\ExcelQA_Output\docker-public2\evaluation.json"
```

Bộ đợt 1 có thể dùng `sample_submission.csv` làm reference. Không lấy đáp án mẫu để tạo câu trả lời khi chạy.

Tạo ZIP theo tên đội:

```powershell
.\.venv\Scripts\python.exe tools\package.py --team TEN_DOI_THAT --out dist
```

ZIP tối đa 100 MB, Dockerfile ở gốc; không kèm dữ liệu, key hoặc môi trường ảo. Tải mã qua **Code → Download ZIP** trên GitHub để phát triển; gói GitHub có thư mục bao ngoài, nên dùng `tools/package.py` tạo gói thi. Kiểm tra build Docker, runtime, disk/RAM, ngân sách và độ chính xác bằng key thật trước khi nộp tại https://ai.tainangviet.vn.

Căn cứ: đề, hướng dẫn nộp bài và FAQ BTC do đội cung cấp; FAQ là căn cứ cập nhật RAM/disk, ID, chuỗi rỗng và token. Hạn đề gốc: 12:00 ngày 17/10/2026, ưu tiên thông báo chính thức mới hơn nếu có.
