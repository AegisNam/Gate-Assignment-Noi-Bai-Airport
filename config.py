# -*- coding: utf-8 -*-
"""
CẤU HÌNH CHUNG CHO MÔ PHỎNG GÁN CỔNG ĐỖ TÀU BAY - SÂN BAY NỘI BÀI (HAN)
========================================================================

QUAN TRỌNG - CÁC GIẢ ĐỊNH DO DỮ LIỆU NGUỒN KHÔNG CUNG CẤP ĐẦY ĐỦ:
Dữ liệu gốc (sơ đồ sân đỗ AIP + bảng lịch bay 9h-12h ngày 16/09/2026) KHÔNG
ghi rõ mỗi vị trí đỗ thuộc nhà ga T1 hay T2, cũng không có thời gian quay đầu
(turnaround) thực tế của từng chuyến. Các giá trị dưới đây là giả định hợp lý
dựa trên cách bố trí sân đỗ thực tế (khu số nhỏ 2-29 sát nhà ga T2, khu số lớn
30-58 + sân đỗ xa 71-86 + khu hangar/quân sự sát về phía T1), CHỨ KHÔNG PHẢI
số liệu chính thức của Cảng HKQT Nội Bài. Hãy chỉnh lại TERMINAL_RULE và
TURNAROUND_MIN nếu bạn có số liệu chính xác hơn.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "ket_qua")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. SẢI CÁNH MÁY BAY THEO LOẠI TÀU (mét) - số liệu công khai của nhà sản xuất
# ---------------------------------------------------------------------------
AIRCRAFT_WINGSPAN_M = {
    "A320": 35.8, "A20N": 35.8, "32N": 35.8, "320": 35.8,
    "A321": 35.8, "A21N": 35.8, "32Q": 35.8, "321": 35.8,
    "B38M": 35.9,
    "A333": 60.3,
    "A359": 64.75,
    "B773": 60.9, "B77L": 64.8, "B77W": 64.8,
    "B788": 60.1, "B789": 60.1,
    "B744": 64.4, "B748": 68.4,
}
DEFAULT_WINGSPAN_M = 36.0  # loại tàu không xác định -> coi như thân hẹp

# Thân hẹp (narrow-body) quay đầu nhanh hơn thân rộng (wide-body)
WIDE_BODY_TYPES = {"A333", "A359", "B773", "B77L", "B77W", "B788", "B789", "B744", "B748"}
TURNAROUND_MIN = {"narrow": 45, "wide": 90}  # phút - GIẢ ĐỊNH thời gian chiếm dụng cổng

# ---------------------------------------------------------------------------
# 2. PHÂN CHIA NHÀ GA T1 / T2 THEO KHU VỰC SÂN ĐỖ (GIẢ ĐỊNH - xem cảnh báo trên)
# ---------------------------------------------------------------------------
def gate_terminal(gate_code: str) -> str:
    """Trả về 'T2' cho các vị trí đỗ số 2-29 (khu sát nhà ga quốc tế T2,
    có ống lồng), 'T1' cho phần còn lại (khu 30-58, sân đỗ xa 71-86,
    khu hangar 1H/2H/3H/9H, khu quân sự QS...)."""
    import re
    m = re.match(r"(\d+)", gate_code)
    if m:
        num = int(m.group(1))
        if 2 <= num <= 29:
            return "T2"
    return "T1"


# Vị trí đỗ được xem là "cổng xa" (không có ống lồng, khách phải đi xe bus)
def is_remote_stand(gate_code: str) -> bool:
    return (
        gate_code.startswith("QS")
        or gate_code.endswith("H")
        or gate_code in {"E"}
        or (gate_code[:2].isdigit() and False)
        or (gate_code.rstrip("ABCD").isdigit() and int(gate_code.rstrip("ABCD") or 0) >= 71)
    )


# ---------------------------------------------------------------------------
# 3. HÃNG BAY NỘI ĐỊA (dùng để gán mỗi chuyến bay cho T1 hoặc T2 - GIẢ ĐỊNH)
# ---------------------------------------------------------------------------
DOMESTIC_CARRIERS = {"VN", "VJ", "VU", "QH", "BL"}  # -> chuyến bay đi/đến nhà ga T1


def flight_terminal(flight_no: str) -> str:
    i = 0
    while i < len(flight_no) and flight_no[i].isalpha():
        i += 1
    code = flight_no[:i]
    return "T1" if code in DOMESTIC_CARRIERS else "T2"


# ---------------------------------------------------------------------------
# 4. TRỌNG SỐ HÀM MỤC TIÊU (đơn vị: điểm phạt, có thể tinh chỉnh)
# ---------------------------------------------------------------------------
WEIGHTS = {
    "taxi": 1.0,       # trọng số quãng đường lăn (tắc nghẽn đường lăn/sân đỗ)
    "walk": 1.5,       # trọng số quãng đường đi bộ của hành khách
    "remote": 80.0,    # phạt cố định nếu phải đỗ cổng xa (khách phải đi xe bus)
    "conflict": 8000.0,  # phạt RẤT nặng nếu 2 chuyến trùng giờ dùng chung 1 cổng
                          # (thực tế đây gần như là ràng buộc cứng - 1 cổng
                          # không thể phục vụ 2 tàu bay cùng lúc)
    "infeasible": 2000.0,  # phạt nếu gán cổng không đủ sải cánh (không khả thi)
}

# Số mét quy đổi từ độ kinh/vĩ (xấp xỉ tại vĩ độ Nội Bài ~21.2N)
METERS_PER_DEG_LAT = 111_320
METERS_PER_DEG_LON = 111_320 * 0.9325  # cos(21.2 độ)

RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# 5. TẬP VỊ TRÍ ĐỖ VẬN HÀNH TRONG MÔ PHỎNG (GIẢ ĐỊNH có chủ đích)
# ---------------------------------------------------------------------------
# Sơ đồ AIP có ~100 vị trí đỗ, nhưng phần lớn là bãi đỗ qua đêm/hangar/quân sự
# hiếm khi cạnh tranh trong giờ cao điểm. Nếu mô phỏng dùng toàn bộ ~100 vị trí
# thì với ~30-40 chuyến/giờ sẽ HẦU NHƯ KHÔNG BAO GIỜ xảy ra tranh chấp cổng,
# khiến 4 thuật toán cho ra kết quả giống hệt nhau (bài toán trở nên tầm thường)
# và không còn phản ánh đúng vấn đề "tắc nghẽn sân đỗ" mà đề bài đặt ra.
# Do đó, mô phỏng CHỦ ĐỘNG giới hạn lại tập vị trí đỗ "đang khai thác" xuống còn
# các vị trí: (a) thực sự xuất hiện trong dữ liệu lịch bay 16/09/2026 thu thập
# được, và (b) một số vị trí thương mại + có ống lồng ở khu số 2-29 (gần T2) để
# nhà ga T2 có đủ lựa chọn cổng cho việc so sánh. Đây là lựa chọn mô hình hoá
# CÓ CHỦ ĐÍCH nhằm tái hiện đúng mức độ cạnh tranh cổng đỗ trong giờ cao điểm,
# không phải số liệu vận hành chính thức của Nội Bài.
_REAL_USED_GATES = {
    "33", "36", "37", "39", "3H", "42", "43", "47", "47A", "49", "52", "53",
    "54B", "58D", "72", "74", "75", "76", "80", "9H", "E", "QS1A", "QS4", "QS4A",
}
_T2_EXTRA_GATES = {"2", "3", "4", "5", "6", "7", "8", "11", "12A", "12B", "28A", "28B", "29", "2H"}
OPERATIONAL_STANDS = sorted(_REAL_USED_GATES | _T2_EXTRA_GATES)
