# -*- coding: utf-8 -*-
"""Mô phỏng chuyển động của tàu bay ra/vào vị trí đỗ trên sơ đồ sân đỗ Nội Bài
(giản lược), dùng matplotlib.animation. Tàu bay được vẽ dưới dạng hình tam
giác di chuyển từ điểm truy cập đường lăn (tham chiếu) tới cổng được thuật
toán gán, đúng theo mốc giờ tương đối trong kịch bản (đã nén thời gian lại
để xem trong vài chục giây thay vì 1 giờ thực)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

plt.rcParams["font.family"] = "DejaVu Sans"


def _gate_color(gate):
    if gate.remote:
        return "#d62728"  # đỏ: cổng xa / không ống lồng
    return "#2ca02c" if gate.terminal == "T1" else "#1f77b4"  # xanh lá T1, xanh dương T2


def build_animation(scenario, assignment, method_name, save_path,
                     time_compression_sec: float = 14.0, fps: int = 10):
    """Tạo và lưu file GIF mô phỏng chuyển động tàu bay cho 1 kịch bản +
    1 phương án gán cổng cụ thể."""
    gates = scenario.gates
    gate_codes = scenario.gate_codes
    flights = scenario.flights

    fig, ax = plt.subplots(figsize=(9, 7.5), dpi=80)

    # vẽ toàn bộ cổng đang khai thác trong kịch bản
    for gc in gate_codes:
        g = gates[gc]
        ax.scatter(g.x, g.y, s=90, color=_gate_color(g), edgecolor="black", zorder=3)
        ax.annotate(gc, (g.x, g.y), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=7)

    ax.scatter(*scenario.runway_xy, marker="s", s=160, color="black", zorder=4)
    ax.annotate("Đường lăn vào/ra", scenario.runway_xy, textcoords="offset points",
                xytext=(10, 5), fontsize=9, fontweight="bold")
    for term, xy in scenario.terminal_xy.items():
        ax.scatter(*xy, marker="*", s=350, color="gold", edgecolor="black", zorder=4)
        ax.annotate(f"Nhà ga {term}", xy, textcoords="offset points",
                    xytext=(10, -12), fontsize=10, fontweight="bold")

    ax.set_title(f"Mô phỏng chuyển động tàu bay - {scenario.name}\nThuật toán: {method_name}",
                 fontsize=12, fontweight="bold")
    ax.set_xlabel("Đông - Tây (mét, toạ độ cục bộ)")
    ax.set_ylabel("Bắc - Nam (mét, toạ độ cục bộ)")
    ax.grid(alpha=0.25)
    ax.set_aspect("equal", adjustable="datalim")

    legend_elems = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c", markersize=10, label="Cổng khu T1"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#1f77b4", markersize=10, label="Cổng khu T2"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d62728", markersize=10, label="Cổng xa (đỗ bus)"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="orange", markersize=10, label="Tàu bay đang di chuyển"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=8)

    if not flights:
        fig.savefig(save_path.replace(".gif", ".png"), dpi=130)
        plt.close(fig)
        return save_path.replace(".gif", ".png")

    t_min = min(f.time for f in flights)
    t_max = max(f.time for f in flights)
    span_sec = max((t_max - t_min).total_seconds(), 1.0)

    # mỗi chuyến: (t_event_norm, x0,y0, x1,y1, is_arrival)
    events = []
    for i, f in enumerate(flights):
        gidx = assignment[i]
        g = gates[gate_codes[gidx]]
        t_norm = (f.time - t_min).total_seconds() / span_sec
        events.append((t_norm, scenario.runway_xy[0], scenario.runway_xy[1], g.x, g.y, f.section, f.flight_no))

    n_frames = int(time_compression_sec * fps)
    move_frac = 0.12  # tỉ lệ thời lượng khung hình dùng để "bay" vào/ra cổng

    aircraft_dots = ax.scatter([], [], marker="^", s=140, color="orange", edgecolor="black", zorder=5)
    time_text = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=10,
                         bbox=dict(boxstyle="round", fc="white", alpha=0.8))

    def frame_positions(frac):
        pts = []
        for (t_norm, x0, y0, x1, y1, section, fno) in events:
            if section == "arrival":
                local = (frac - t_norm) / move_frac
            else:  # departure: bay rời cổng ra đường băng, xuất hiện sớm hơn mốc giờ
                local = (frac - (t_norm - move_frac)) / move_frac
            if local < 0:
                continue
            local = min(local, 1.0)
            if section == "arrival":
                x, y = x0 + (x1 - x0) * local, y0 + (y1 - y0) * local
            else:
                x, y = x1 + (x0 - x1) * local, y1 + (y0 - y1) * local
            pts.append((x, y))
        return pts

    def update(frame_idx):
        frac = frame_idx / n_frames
        pts = frame_positions(frac)
        if pts:
            aircraft_dots.set_offsets(np.array(pts))
        else:
            aircraft_dots.set_offsets(np.empty((0, 2)))
        clock = t_min + (t_max - t_min) * frac
        time_text.set_text(f"Giờ mô phỏng: {clock.strftime('%H:%M')}   "
                            f"(tổng {len(flights)} chuyến bay trong khung giờ)")
        return aircraft_dots, time_text

    anim = animation.FuncAnimation(fig, update, frames=n_frames + 1, interval=1000 / fps, blit=False)
    anim.save(save_path, writer=animation.PillowWriter(fps=fps))
    plt.close(fig)
    return save_path


def _conflicting_flight_indices(scenario, assignment):
    """Trả về tập chỉ số các chuyến bay đang bị xung đột giờ (dùng chung
    cổng với 1 chuyến khác cùng khung giờ chiếm dụng) trong 1 phương án gán."""
    from collections import defaultdict
    by_gate = defaultdict(list)
    for i, gidx in enumerate(assignment):
        by_gate[gidx].append(i)
    conflicted = set()
    for gidx, idxs in by_gate.items():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                s1, e1 = scenario.flights[i].occupancy_window
                s2, e2 = scenario.flights[j].occupancy_window
                if s1 < e2 and s2 < e1:
                    conflicted.add(i)
                    conflicted.add(j)
    return conflicted


def build_comparison_animation(scenario, assignment_no_opt, assignment_milp, save_path,
                                time_compression_sec: float = 14.0, fps: int = 10):
    """Mô phỏng SONG SONG 2 khung cảnh dùng chung 1 kịch bản / 1 khung giờ:
    bên trái = KHÔNG áp dụng thuật toán (quy tắc thủ công đơn giản), bên phải
    = ÁP DỤNG MILP (lời giải tối ưu chính xác). Tàu bay bị xung đột giờ (2 tàu
    cùng chiếm 1 cổng) được tô ĐỎ và nhấp nháy ở khung bên trái để thấy rõ hậu
    quả thực tế của việc không dùng thuật toán tối ưu."""
    gates = scenario.gates
    gate_codes = scenario.gate_codes
    flights = scenario.flights

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 6.2), dpi=80)
    panels = [
        (axL, assignment_no_opt, "KHÔNG áp dụng thuật toán\n(quy tắc thủ công: chọn cổng trống đầu tiên)"),
        (axR, assignment_milp, "ÁP DỤNG MILP\n(lời giải tối ưu chính xác bằng quy hoạch nguyên)"),
    ]
    conflicted_no_opt = _conflicting_flight_indices(scenario, assignment_no_opt)

    aircraft_artists = []
    time_texts = []
    for ax, assignment, title in panels:
        for gc in gate_codes:
            g = gates[gc]
            ax.scatter(g.x, g.y, s=80, color=_gate_color(g), edgecolor="black", zorder=3)
            ax.annotate(gc, (g.x, g.y), textcoords="offset points", xytext=(0, 6),
                        ha="center", fontsize=6.5)
        ax.scatter(*scenario.runway_xy, marker="s", s=140, color="black", zorder=4)
        for term, xy in scenario.terminal_xy.items():
            ax.scatter(*xy, marker="*", s=300, color="gold", edgecolor="black", zorder=4)
            ax.annotate(f"Ga {term}", xy, textcoords="offset points", xytext=(8, -10), fontsize=9)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.grid(alpha=0.25)
        ax.set_aspect("equal", adjustable="datalim")
        dots = ax.scatter([], [], marker="^", s=130, color="orange", edgecolor="black", zorder=5)
        txt = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", fontsize=9,
                       bbox=dict(boxstyle="round", fc="white", alpha=0.85))
        aircraft_artists.append(dots)
        time_texts.append(txt)

    n_conf = len(conflicted_no_opt)
    fig.suptitle(
        f"{scenario.name}  -  {len(flights)} chuyến bay, {len(gate_codes)} vị trí đỗ đang khai thác\n"
        f"Số lượt xung đột cổng khi KHÔNG tối ưu: {n_conf} chuyến bay bị ảnh hưởng  |  "
        f"Khi dùng MILP: 0 xung đột (ràng buộc cứng)",
        fontsize=12, fontweight="bold")

    if not flights:
        fig.savefig(save_path.replace(".gif", ".png"), dpi=130)
        plt.close(fig)
        return save_path.replace(".gif", ".png")

    t_min = min(f.time for f in flights)
    t_max = max(f.time for f in flights)
    span_sec = max((t_max - t_min).total_seconds(), 1.0)
    n_frames = int(time_compression_sec * fps)
    move_frac = 0.12

    def build_events(assignment):
        ev = []
        for i, f in enumerate(flights):
            g = gates[gate_codes[assignment[i]]]
            t_norm = (f.time - t_min).total_seconds() / span_sec
            ev.append((t_norm, scenario.runway_xy[0], scenario.runway_xy[1], g.x, g.y, f.section, i))
        return ev

    events_list = [build_events(assignment_no_opt), build_events(assignment_milp)]

    def frame_positions(events, frac, conflicted_set=None):
        pts, colors = [], []
        for (t_norm, x0, y0, x1, y1, section, idx) in events:
            if section == "arrival":
                local = (frac - t_norm) / move_frac
            else:
                local = (frac - (t_norm - move_frac)) / move_frac
            if local < 0:
                continue
            local = min(local, 1.0)
            if section == "arrival":
                x, y = x0 + (x1 - x0) * local, y0 + (y1 - y0) * local
            else:
                x, y = x1 + (x0 - x1) * local, y1 + (y0 - y1) * local
            pts.append((x, y))
            is_conf = conflicted_set is not None and idx in conflicted_set and local >= 0.98
            colors.append("red" if is_conf else "orange")
        return pts, colors

    def update(frame_idx):
        frac = frame_idx / n_frames
        clock = t_min + (t_max - t_min) * frac
        for panel_i, (dots, events) in enumerate(zip(aircraft_artists, events_list)):
            conf_set = conflicted_no_opt if panel_i == 0 else None
            pts, colors = frame_positions(events, frac, conf_set)
            if pts:
                dots.set_offsets(np.array(pts))
                dots.set_color(colors)
            else:
                dots.set_offsets(np.empty((0, 2)))
            time_texts[panel_i].set_text(f"Giờ mô phỏng: {clock.strftime('%H:%M')}")
        return aircraft_artists + time_texts

    anim = animation.FuncAnimation(fig, update, frames=n_frames + 1, interval=1000 / fps, blit=False)
    anim.save(save_path, writer=animation.PillowWriter(fps=fps))
    plt.close(fig)
    return save_path
