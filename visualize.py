# -*- coding: utf-8 -*-
"""Vẽ biểu đồ so sánh giá trị hàm mục tiêu và thời gian xử lý giữa các
thuật toán, cho từng kịch bản (khung giờ)."""
import os
import matplotlib
matplotlib.use("Agg")  # để có thể chạy cả khi không có màn hình (headless)
import matplotlib.pyplot as plt
import numpy as np

from . import config

plt.rcParams["font.family"] = "DejaVu Sans"  # font hỗ trợ tốt tiếng Việt có dấu


def plot_cost_and_time(results: dict, out_path: str):
    """results: {scenario_name: {method_name: {"cost":.., "time_ms":.., "detail":{...}}}}"""
    scenario_names = list(results.keys())
    method_names = list(next(iter(results.values())).keys())

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    x = np.arange(len(scenario_names))
    width = 0.8 / len(method_names)
    colors = plt.cm.tab10(np.linspace(0, 1, len(method_names)))

    ax = axes[0]
    for i, m in enumerate(method_names):
        vals = [results[s][m]["cost"] for s in scenario_names]
        ax.bar(x + i * width, vals, width, label=m, color=colors[i])
    ax.set_xticks(x + width * (len(method_names) - 1) / 2)
    ax.set_xticklabels([s.split("(")[0].strip() for s in scenario_names], rotation=10)
    ax.set_ylabel("Giá trị hàm mục tiêu (càng thấp càng tốt)")
    ax.set_title("So sánh chất lượng lời giải giữa các thuật toán")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    for i, m in enumerate(method_names):
        vals = [results[s][m]["time_ms"] for s in scenario_names]
        ax.bar(x + i * width, vals, width, label=m, color=colors[i])
    ax.set_xticks(x + width * (len(method_names) - 1) / 2)
    ax.set_xticklabels([s.split("(")[0].strip() for s in scenario_names], rotation=10)
    ax.set_ylabel("Thời gian xử lý (mili-giây, thang log)")
    ax.set_yscale("log")
    ax.set_title("So sánh thời gian xử lý giữa các thuật toán")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("MÔ PHỎNG GÁN CỔNG ĐỖ TÀU BAY - SÂN BAY QUỐC TẾ NỘI BÀI", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_cost_breakdown(results: dict, out_path: str):
    """Biểu đồ cột chồng: phân rã hàm mục tiêu (taxi/đi bộ/cổng xa/xung đột)
    theo từng thuật toán, gộp cả 3 kịch bản."""
    method_names = list(next(iter(results.values())).keys())
    components = ["taxi", "walk", "remote", "conflict", "infeasible"]
    labels_vi = {
        "taxi": "Quãng đường lăn",
        "walk": "Quãng đường đi bộ HK",
        "remote": "Phạt đỗ cổng xa",
        "conflict": "Phạt xung đột giờ",
        "infeasible": "Phạt không khả thi",
    }
    sums = {c: [] for c in components}
    for m in method_names:
        for c in components:
            total_c = sum(results[s][m]["detail"][c] for s in results)
            sums[c].append(total_c)

    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(method_names))
    bottom = np.zeros(len(method_names))
    for c in components:
        vals = np.array(sums[c])
        ax.bar(x, vals, bottom=bottom, label=labels_vi[c])
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels(method_names, rotation=15)
    ax.set_ylabel("Tổng điểm phạt (cộng dồn 3 kịch bản)")
    ax.set_title("Phân rã các thành phần trong hàm mục tiêu theo từng thuật toán")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
