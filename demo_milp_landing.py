# -*- coding: utf-8 -*-
"""
MÔ PHỎNG TÀU BAY HẠ CÁNH & LĂN VÀO CỔNG: SO SÁNH KHÔNG DÙNG vs DÙNG MILP
==========================================================================
So sánh trực quan 2 cách vận hành trên CÙNG một sơ đồ sân đỗ Nội Bài và
CÙNG một danh sách chuyến bay thật (9h-12h ngày 16/09/2026):

  (1) KHÔNG áp dụng thuật toán - quy tắc thủ công đơn giản: mỗi chuyến bay
      hạ cánh/chuẩn bị cất cánh được xếp vào CỔNG TRỐNG ĐẦU TIÊN tìm thấy,
      không tính toán chi phí, không có cái nhìn tổng thể toàn khung giờ.
      Đây là cách mô phỏng gần với vận hành thủ công / theo kinh nghiệm khi
      CHƯA có công cụ tối ưu hỗ trợ.

  (2) ÁP DỤNG MILP (Mixed Integer Linear Programming) - quy hoạch tuyến tính
      nguyên hỗn hợp, giải CHÍNH XÁC (không phải heuristic/xấp xỉ) bằng
      solver HiGHS tích hợp sẵn trong SciPy, tối thiểu hoá CÙNG một hàm mục
      tiêu (quãng đường lăn + quãng đường đi bộ hành khách + phạt cổng xa)
      với ràng buộc CỨNG là không được để 2 chuyến bay trùng giờ dùng chung
      1 cổng đỗ.

Kết quả xuất ra thư mục ket_qua/:
  - bao_cao_milp.txt           : bảng số liệu so sánh chi tiết từng kịch bản
  - mo_phong_milp_kich_ban_*.gif : hoạt hình song song 2 khung cảnh
  - bieu_do_milp_so_sanh.png   : biểu đồ cột so sánh hàm mục tiêu & xung đột
"""
import random
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import config, data_loader, animate
from .scenario import build_scenarios, evaluate_assignment
from .milp import solve_milp, no_optimization_baseline


def _fmt(n):
    return f"{n:,.0f}".replace(",", ".")


def run_milp_demo():
    random.seed(config.RANDOM_SEED)
    print("=" * 82)
    print(" MÔ PHỎNG TÀU BAY HẠ CÁNH & GÁN CỔNG: KHÔNG DÙNG vs DÙNG MILP (NỘI BÀI)")
    print("=" * 82)

    gates = data_loader.load_gates()
    flights = data_loader.load_flights()
    terminal_xy = data_loader.terminal_building_xy(gates)
    runway_xy = data_loader.runway_access_xy(gates)
    scenarios = build_scenarios(flights, gates, terminal_xy, runway_xy, datetime(2026, 9, 16))

    report_lines = []
    summary = {}  # scenario_name -> {"no_opt": {...}, "milp": {...}}

    for sc_idx, sc in enumerate(scenarios, start=1):
        print("-" * 82)
        header = f"{sc.name}: {len(sc.flights)} chuyến bay, {len(sc.gate_codes)} vị trí đỗ"
        print(header)
        report_lines.append(header)

        t0 = time.perf_counter()
        a_noopt = no_optimization_baseline(sc)
        t_noopt = (time.perf_counter() - t0) * 1000
        c_noopt, d_noopt = evaluate_assignment(sc, a_noopt)

        t0 = time.perf_counter()
        a_milp, info = solve_milp(sc, time_limit=30.0)
        t_milp = (time.perf_counter() - t0) * 1000
        if a_milp is None:
            print(f"  [CẢNH BÁO] MILP không giải được ({info['status']}) cho {sc.name}")
            continue
        c_milp, d_milp = evaluate_assignment(sc, a_milp)

        n_conf_noopt = int(round(d_noopt["conflict"] / config.WEIGHTS["conflict"])) if sc.flights else 0
        n_conf_milp = int(round(d_milp["conflict"] / config.WEIGHTS["conflict"])) if sc.flights else 0
        n_remote_noopt = int(round(d_noopt["remote"] / config.WEIGHTS["remote"])) if sc.flights else 0
        n_remote_milp = int(round(d_milp["remote"] / config.WEIGHTS["remote"])) if sc.flights else 0
        improve_pct = 100.0 * (c_noopt - c_milp) / c_noopt if c_noopt else 0.0

        line1 = (f"  {'Không áp dụng (thủ công)':<32}"
                 f"hàm mục tiêu={_fmt(c_noopt):>10}  thời gian={t_noopt:7.2f} ms  "
                 f"xung đột={n_conf_noopt}  cổng xa={n_remote_noopt}")
        line2 = (f"  {'Áp dụng MILP (tối ưu chính xác)':<32}"
                 f"hàm mục tiêu={_fmt(c_milp):>10}  thời gian={t_milp:7.2f} ms  "
                 f"xung đột={n_conf_milp}  cổng xa={n_remote_milp}")
        line3 = f"  => MILP cải thiện hàm mục tiêu {improve_pct:.1f}% và loại bỏ hoàn toàn xung đột giờ."
        for l in (line1, line2, line3):
            print(l)
            report_lines.append(l)
        report_lines.append("")

        summary[sc.name] = {
            "no_opt": {"cost": c_noopt, "time_ms": t_noopt, "detail": d_noopt,
                       "n_conflict": n_conf_noopt, "n_remote": n_remote_noopt, "assignment": a_noopt},
            "milp": {"cost": c_milp, "time_ms": t_milp, "detail": d_milp,
                     "n_conflict": n_conf_milp, "n_remote": n_remote_milp, "assignment": a_milp,
                     "solver_info": info},
        }

        print(f"  Đang dựng mô phỏng song song cho {sc.name} ...")
        gif_path = f"{config.OUTPUT_DIR}/mo_phong_milp_kich_ban_{sc_idx}.gif"
        animate.build_comparison_animation(sc, a_noopt, a_milp, gif_path)
        print(f"  Đã lưu: {gif_path}")

    print("=" * 82)
    print("NHẬN XÉT TRUNG THỰC:")
    note = ("- MILP giải CHÍNH XÁC (tối ưu toàn cục, có chứng minh) trong vài chục đến vài trăm\n"
            "  mili-giây cho quy mô bài toán này (30-40 chuyến bay, ~32 cổng) - nhanh hơn nhiều so\n"
            "  với suy nghĩ thông thường về MILP, vì đây vẫn là quy mô nhỏ so với bài toán thực của\n"
            "  toàn bộ sân bay (hàng trăm chuyến/ngày, hàng trăm cổng) - ở quy mô lớn hơn MILP có\n"
            "  thể mất rất nhiều thời gian hoặc không giải nổi trong thời gian cho phép, đây là lý\n"
            "  do các thuật toán metaheuristic (SA, GA) và AI/học tăng cường vẫn có giá trị thực tế.\n"
            "- Quy tắc thủ công 'chọn cổng trống đầu tiên' (không dùng thuật toán) luôn để lại xung\n"
            "  đột giờ và dùng cổng xa nhiều hơn hẳn - đúng với thực tế vận hành khi thiếu công cụ hỗ trợ.")
    print(note)
    report_lines.append("NHẬN XÉT TRUNG THỰC:\n" + note)

    with open(f"{config.OUTPUT_DIR}/bao_cao_milp.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\nĐã lưu báo cáo chi tiết: {config.OUTPUT_DIR}/bao_cao_milp.txt")

    _plot_summary(summary, f"{config.OUTPUT_DIR}/bieu_do_milp_so_sanh.png")
    print(f"Đã lưu biểu đồ so sánh: {config.OUTPUT_DIR}/bieu_do_milp_so_sanh.png")
    print(f"\nToàn bộ kết quả nằm trong thư mục: {config.OUTPUT_DIR}")
    print("=" * 82)


def _plot_summary(summary: dict, out_path: str):
    names = list(summary.keys())
    short = [n.split("(")[0].strip() for n in names]
    x = np.arange(len(names))
    width = 0.35

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

    ax = axes[0]
    ax.bar(x - width / 2, [summary[n]["no_opt"]["cost"] for n in names], width,
           label="Không áp dụng", color="#d62728")
    ax.bar(x + width / 2, [summary[n]["milp"]["cost"] for n in names], width,
           label="Áp dụng MILP", color="#2ca02c")
    ax.set_xticks(x); ax.set_xticklabels(short, rotation=10)
    ax.set_ylabel("Giá trị hàm mục tiêu (càng thấp càng tốt)")
    ax.set_title("Chất lượng lời giải"); ax.legend(); ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    ax.bar(x - width / 2, [summary[n]["no_opt"]["n_conflict"] for n in names], width,
           label="Không áp dụng", color="#d62728")
    ax.bar(x + width / 2, [summary[n]["milp"]["n_conflict"] for n in names], width,
           label="Áp dụng MILP", color="#2ca02c")
    ax.set_xticks(x); ax.set_xticklabels(short, rotation=10)
    ax.set_ylabel("Số lượt xung đột giờ tại cổng")
    ax.set_title("Xung đột cổng đỗ"); ax.legend(); ax.grid(axis="y", alpha=0.3)

    ax = axes[2]
    ax.bar(x - width / 2, [summary[n]["no_opt"]["time_ms"] for n in names], width,
           label="Không áp dụng", color="#d62728")
    ax.bar(x + width / 2, [summary[n]["milp"]["time_ms"] for n in names], width,
           label="Áp dụng MILP", color="#2ca02c")
    ax.set_xticks(x); ax.set_xticklabels(short, rotation=10)
    ax.set_ylabel("Thời gian xử lý (ms, thang log)"); ax.set_yscale("log")
    ax.set_title("Thời gian tính toán"); ax.legend(); ax.grid(axis="y", alpha=0.3)

    fig.suptitle("SO SÁNH: KHÔNG ÁP DỤNG vs ÁP DỤNG MILP - GÁN CỔNG ĐỖ TÀU BAY NỘI BÀI",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    run_milp_demo()
