# -*- coding: utf-8 -*-
"""
CHƯƠNG TRÌNH CHÍNH
===================
Chạy so sánh 4 thuật toán gán cổng đỗ tàu bay (Greedy, Simulated Annealing,
Genetic Algorithm, Q-learning) trên 3 kịch bản (khung giờ 9-10h, 10-11h,
11-12h ngày 16/09/2026 tại Nội Bài), gồm cả chuyến bay của nhà ga T1 và T2.

Cách chạy trong PyCharm:
    1. Mở thư mục dự án này (noibai_gapsim) làm Project Root trong PyCharm.
    2. Cài thư viện:  pip install -r requirements.txt
    3. Chạy trực tiếp file main.py (chuột phải -> Run 'main').

Kết quả (biểu đồ .png, mô phỏng .gif, báo cáo .txt) sẽ được lưu vào
thư mục con "ket_qua/".
"""
import random
import time
from datetime import datetime

from . import config, data_loader, visualize, animate
from .scenario import build_scenarios, evaluate_assignment
from .algorithms import ALGORITHMS


def _fmt(n):
    return f"{n:,.0f}".replace(",", ".")


def run_all():
    random.seed(config.RANDOM_SEED)

    print("=" * 78)
    print(" MÔ PHỎNG & SO SÁNH THUẬT TOÁN GÁN CỔNG ĐỖ TÀU BAY - SÂN BAY NỘI BÀI")
    print("=" * 78)

    gates = data_loader.load_gates()
    flights = data_loader.load_flights()
    terminal_xy = data_loader.terminal_building_xy(gates)
    runway_xy = data_loader.runway_access_xy(gates)
    scenarios = build_scenarios(flights, gates, terminal_xy, runway_xy, datetime(2026, 9, 16))

    print(f"\nĐã nạp {len(gates)} vị trí đỗ (từ sơ đồ AIP), trong đó "
          f"{len(config.OPERATIONAL_STANDS)} vị trí được đưa vào mô phỏng vận hành.")
    print(f"Đã nạp {len(flights)} chuyến bay thực tế (9h-12h ngày 16/09/2026).")
    print("LƯU Ý: việc phân chia cổng/chuyến bay theo nhà ga T1-T2 là GIẢ ĐỊNH minh "
          "hoạ (xem chi tiết trong config.py), vì dữ liệu gốc không công bố thông tin này.\n")

    results = {}       # scenario_name -> method -> {"cost","time_ms","detail"}
    assignments = {}   # scenario_name -> method -> assignment (để dựng hoạt hình)

    for sc in scenarios:
        n_t1 = sum(1 for f in sc.flights if f.terminal == "T1")
        n_t2 = sum(1 for f in sc.flights if f.terminal == "T2")
        print("-" * 78)
        print(f"{sc.name}: {len(sc.flights)} chuyến bay  (T1: {n_t1}  |  T2: {n_t2})")
        print("-" * 78)
        print(f"{'Thuật toán':<24}{'Hàm mục tiêu':>16}{'Thời gian (ms)':>18}"
              f"{'Xung đột giờ':>16}{'Cổng xa':>10}")

        results[sc.name] = {}
        assignments[sc.name] = {}
        for method_name, fn in ALGORITHMS.items():
            rng = random.Random(config.RANDOM_SEED)
            t0 = time.perf_counter()
            assignment = fn(sc, rng)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            cost, detail = evaluate_assignment(sc, assignment)
            n_conflict_pairs = int(round(detail["conflict"] / config.WEIGHTS["conflict"])) if sc.flights else 0
            n_remote = int(round(detail["remote"] / config.WEIGHTS["remote"])) if sc.flights else 0

            results[sc.name][method_name] = {"cost": cost, "time_ms": elapsed_ms, "detail": detail}
            assignments[sc.name][method_name] = assignment

            print(f"{method_name:<24}{_fmt(cost):>16}{elapsed_ms:>18.1f}"
                  f"{n_conflict_pairs:>16}{n_remote:>10}")
        print()

    # ------------------------------------------------------------------
    # Tổng kết & xếp hạng
    # ------------------------------------------------------------------
    print("=" * 78)
    print(" TỔNG KẾT (cộng dồn cả 3 kịch bản)")
    print("=" * 78)
    totals = {m: 0.0 for m in ALGORITHMS}
    total_time = {m: 0.0 for m in ALGORITHMS}
    for sc_name, methods in results.items():
        for m, r in methods.items():
            totals[m] += r["cost"]
            total_time[m] += r["time_ms"]
    ranked = sorted(totals.items(), key=lambda kv: kv[1])
    print(f"{'Xếp hạng':<10}{'Thuật toán':<24}{'Tổng hàm mục tiêu':>20}{'Tổng thời gian (ms)':>22}")
    for rank, (m, val) in enumerate(ranked, start=1):
        print(f"{rank:<10}{m:<24}{_fmt(val):>20}{total_time[m]:>22.1f}")

    print("\nNHẬN XÉT TRUNG THỰC:")
    print("- Giá trị hàm mục tiêu càng THẤP nghĩa là lời giải càng tốt (ít quãng đường")
    print("  lăn/đi bộ hơn, ít phải đỗ cổng xa hơn, ít xung đột giờ hơn).")
    print("- Thời gian xử lý phản ánh chi phí tính toán thực tế của từng phương pháp -")
    print("  Greedy luôn nhanh nhất nhưng dễ mắc kẹt ở lời giải cục bộ (không gỡ được")
    print("  hết xung đột giờ); các phương pháp tìm kiếm cục bộ ngẫu nhiên (SA) và")
    print("  học tăng cường (Q-learning) tốn thời gian hơn nhưng có thể tìm ra lời")
    print("  giải tốt hơn - tuy nhiên KHÔNG có gì đảm bảo phương pháp phức tạp hơn")
    print("  luôn thắng: kết quả phía trên là số liệu THẬT của lần chạy này, không")
    print("  được chỉnh sửa để trông "'đẹp'" hơn.")

    # ------------------------------------------------------------------
    # Biểu đồ
    # ------------------------------------------------------------------
    chart1 = visualize.plot_cost_and_time(results, f"{config.OUTPUT_DIR}/bieu_do_so_sanh.png")
    chart2 = visualize.plot_cost_breakdown(results, f"{config.OUTPUT_DIR}/bieu_do_phan_ra_chi_phi.png")
    print(f"\nĐã lưu biểu đồ so sánh: {chart1}")
    print(f"Đã lưu biểu đồ phân rã chi phí: {chart2}")

    # ------------------------------------------------------------------
    # Hoạt hình mô phỏng chuyển động (dùng kịch bản đông chuyến nhất, so sánh
    # thuật toán tốt nhất và Greedy để thấy rõ sự khác biệt)
    # ------------------------------------------------------------------
    busiest = max(scenarios, key=lambda s: len(s.flights))
    best_method_overall = ranked[0][0]
    print(f"\nĐang dựng mô phỏng chuyển động cho '{busiest.name}' "
          f"(thuật toán: {best_method_overall}) - có thể mất một chút thời gian...")
    gif1 = animate.build_animation(
        busiest, assignments[busiest.name][best_method_overall], best_method_overall,
        f"{config.OUTPUT_DIR}/mo_phong_{best_method_overall.split()[0]}.gif")
    print(f"Đã lưu mô phỏng: {gif1}")

    gif2 = animate.build_animation(
        busiest, assignments[busiest.name]["Greedy (tham lam)"], "Greedy (tham lam)",
        f"{config.OUTPUT_DIR}/mo_phong_Greedy.gif")
    print(f"Đã lưu mô phỏng: {gif2}")

    print(f"\nToàn bộ kết quả đã được lưu trong thư mục: {config.OUTPUT_DIR}")
    print("=" * 78)


if __name__ == "__main__":
    run_all()
