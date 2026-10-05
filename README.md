# Mô phỏng & So sánh thuật toán gán cổng đỗ tàu bay - Sân bay Quốc tế Nội Bài

Dự án Python mô phỏng bài toán **Gán cổng đỗ tàu bay (Airport Gate Assignment
Problem - GAP)** tại Nội Bài, dùng dữ liệu thật trích xuất từ:
- Sơ đồ sân đỗ AIP (toạ độ + giới hạn sải cánh từng vị trí đỗ)
- Bảng lịch bay khung giờ 9h-12h ngày **16/09/2026** (108 chuyến bay thật)

Mục tiêu: giảm tắc nghẽn đường lăn/sân đỗ, tối ưu quãng đường di chuyển của
hành khách, giảm số tàu bay phải đỗ cổng xa - so sánh **5 phương pháp**:
Greedy, Simulated Annealing, Genetic Algorithm, Q-learning (AI/học tăng
cường), và **MILP (quy hoạch tuyến tính nguyên hỗn hợp - lời giải tối ưu
chính xác)**.

## ⚠️ Các giả định quan trọng (đọc trước khi dùng)

Dữ liệu nguồn **không** công bố: (1) vị trí đỗ nào thuộc nhà ga T1/T2, (2)
thời gian quay đầu (turnaround) thực tế từng chuyến, (3) lịch bay ngày
17/09/2026 (dù tên file gốc có nhắc tới ngày này, nội dung thực tế chỉ có
dữ liệu 16/09). Mọi giả định (phân chia T1/T2, thời gian quay đầu, tập cổng
đưa vào vận hành...) đều được ghi chú rõ ràng trong `noibai_gapsim/config.py`
- hãy chỉnh lại nếu bạn có số liệu chính thức chính xác hơn.

## Cài đặt

```bash
pip install -r requirements.txt
```

(Chỉ cần `numpy`, `scipy`, `matplotlib`, `pillow` - bài toán MILP được giải
bằng solver **HiGHS tích hợp sẵn trong SciPy**, không cần cài PuLP/CBC/Gurobi.)

## Cách chạy trong PyCharm

Mở thư mục `noibai_gate_sim` (thư mục chứa file này) làm **Project Root**,
sau đó chuột phải vào 1 trong 2 file sau rồi chọn **Run**:

### 1) `chay_so_sanh_4_thuat_toan.py`
So sánh Greedy / Simulated Annealing / Genetic Algorithm / Q-learning trên
3 kịch bản (khung giờ 9-10h, 10-11h, 11-12h), gồm cả chuyến bay nhà ga T1 và
T2. In bảng kết quả tiếng Việt ra console, lưu 2 biểu đồ PNG và 2 hoạt ảnh
GIF mô phỏng chuyển động tàu bay vào thư mục `noibai_gapsim/ket_qua/`.

### 2) `chay_mo_phong_milp.py`
Mô phỏng tàu bay hạ cánh & lăn vào cổng, so sánh trực quan **song song**
2 cách vận hành trên cùng sơ đồ sân đỗ:
- Bên trái: **KHÔNG áp dụng thuật toán** (quy tắc thủ công - chọn cổng trống
  đầu tiên tìm thấy)
- Bên phải: **ÁP DỤNG MILP** (lời giải tối ưu chính xác, không phải xấp xỉ)

Tàu bay bị xung đột giờ (2 chuyến trùng giờ dùng chung 1 cổng) được tô màu
**đỏ** ở khung bên trái để thấy rõ hậu quả thực tế của việc không tối ưu.
Kết quả: báo cáo `bao_cao_milp.txt`, biểu đồ `bieu_do_milp_so_sanh.png`, và
3 file GIF `mo_phong_milp_kich_ban_1/2/3.gif` trong `noibai_gapsim/ket_qua/`.

## Hàm mục tiêu (dùng chung cho mọi thuật toán, để so sánh công bằng)

```
Chi phí = w1 * quãng_đường_lăn + w2 * quãng_đường_đi_bộ_hành_khách
        + w3 * (có đỗ cổng xa?) + w4 * (số cặp chuyến bay xung đột giờ)
        + w5 * (gán cổng không đủ sải cánh?)
```
Trọng số `w1..w5` chỉnh được trong `config.py` (mục `WEIGHTS`).

## Cấu trúc dự án

```
noibai_gate_sim/
├── requirements.txt
├── README.md                          (file này)
├── chay_so_sanh_4_thuat_toan.py       <- chạy file này trong PyCharm (1)
├── chay_mo_phong_milp.py              <- chạy file này trong PyCharm (2)
└── noibai_gapsim/
    ├── config.py          cấu hình, trọng số, các giả định
    ├── data_loader.py     nạp dữ liệu cổng + chuyến bay từ data/*.json
    ├── scenario.py        xây dựng kịch bản + hàm mục tiêu dùng chung
    ├── algorithms.py      Greedy, Simulated Annealing, Genetic Algorithm, Q-learning
    ├── milp.py             MILP (scipy.optimize.milp/HiGHS) + baseline "không áp dụng"
    ├── visualize.py        vẽ biểu đồ so sánh
    ├── animate.py          hoạt ảnh mô phỏng chuyển động tàu bay (đơn + song song)
    ├── main.py              script so sánh 4 thuật toán
    ├── demo_milp_landing.py script mô phỏng MILP vs không-tối-ưu
    └── data/                dữ liệu đã trích xuất sẵn (JSON, không cần mạng)
        ├── gate_coords.json
        ├── gate_wingspan_limit.json
        └── flights_parsed.json
```

## Giới hạn trung thực cần biết

- Đây là mô phỏng **minh hoạ ở quy mô nhỏ** (vài chục chuyến/kịch bản, ~32-38
  cổng đang khai thác trong tổng ~100 cổng trên sơ đồ), không phải hệ thống
  vận hành thực tế cho toàn bộ sân bay.
- Quãng đường lăn được ước lượng bằng khoảng cách Euclid tới 1 điểm tham
  chiếu, **không** phải định tuyến theo mạng đường lăn thực tế.
- Q-learning là bản cài đặt **đơn giản, minh hoạ** (xấp xỉ tuyến tính, vài
  trăm episode) - không phải mô hình học sâu quy mô lớn.
- Trong 1 số lần chạy, Genetic Algorithm có thể cho kết quả bằng đúng Greedy
  (không cải thiện thêm) - đây là kết quả THẬT của cấu hình GA đơn giản dùng
  trong demo, không bị chỉnh sửa để "đẹp" hơn, đúng theo yêu cầu trung thực.
