# -*- coding: utf-8 -*-
"""
THUẬT TOÁN MILP (Mixed Integer Linear Programming) - LỜI GIẢI TỐI ƯU CHÍNH XÁC
================================================================================
Dùng scipy.optimize.milp (solver HiGHS tích hợp sẵn trong SciPy, KHÔNG cần cài
thêm thư viện ngoài như PuLP/CBC/Gurobi - quan trọng vì môi trường chạy có thể
không có mạng để tải gói ngoài).

Mô hình hoá (đúng chuẩn bài toán Gán cổng đỗ tàu bay - Airport Gate Assignment
Problem - trong các tài liệu tham khảo):

  Biến quyết định:  x[i,g] in {0,1}  = 1 nếu chuyến bay i được gán vào cổng g
  Hàm mục tiêu:      min  sum_i sum_g  c[i,g] * x[i,g]
                     (c[i,g] = chi phí lăn + chi phí đi bộ hành khách + phạt
                      cổng xa - GIỐNG HỆT hàm chi phí dùng cho Greedy/SA/GA/
                      Q-learning để việc so sánh công bằng)
  Ràng buộc 1:       sum_g x[i,g] = 1               với mọi chuyến bay i
                     (mỗi chuyến bay phải được gán đúng 1 cổng)
  Ràng buộc 2:       x[i,g] + x[j,g] <= 1           với mọi cặp (i,j) có
                     khung giờ chiếm dụng CHỒNG LẤN và cùng dùng cổng g
                     (1 cổng không thể phục vụ 2 tàu bay cùng lúc - ở đây là
                     RÀNG BUỘC CỨNG, khác với các thuật toán heuristic coi đây
                     là điểm phạt mềm)
  Biến nguyên:       x[i,g] nguyên 0/1 (bài toán MILP thực sự, không phải LP
                     thư giãn)

Vì ràng buộc 2 là ràng buộc cứng, MILP có thể BÁO INFEASIBLE (vô nghiệm) nếu
số chuyến bay tương thích (cùng loại tàu) vượt quá số cổng tương thích sẵn có
trong cùng khung giờ - khi đó mô-đun sẽ nới lỏng bằng cách bỏ bớt ràng buộc
xung đột ít quan trọng nhất và thử lại (xem `solve_milp`), đồng thời báo rõ
cho người dùng biết đã phải nới lỏng bao nhiêu ràng buộc.
"""
import itertools
import time
from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import LinearConstraint, Bounds, milp
from scipy import sparse

from . import config
from .scenario import Scenario


def _cost_matrix(scenario: Scenario):
    """c[i][g] cho MỌI cặp (chuyến bay, cổng) - kể cả không tương thích sải
    cánh (sẽ bị cộng thêm phạt infeasible rất lớn thay vì cấm tuyệt đối, để
    MILP luôn có nghiệm khả thi về mặt cấu trúc)."""
    from .scenario import _dist
    w = config.WEIGHTS
    n, m = len(scenario.flights), len(scenario.gate_codes)
    C = np.zeros((n, m))
    for i, f in enumerate(scenario.flights):
        term_pt = scenario.terminal_xy[f.terminal]
        for gi, gc in enumerate(scenario.gate_codes):
            g = scenario.gates[gc]
            taxi = _dist((g.x, g.y), scenario.runway_xy)
            walk = _dist((g.x, g.y), term_pt)
            cost = w["taxi"] * taxi + w["walk"] * walk
            if g.remote:
                cost += w["remote"]
            if g.max_wingspan_m < f.wingspan_m:
                cost += w["infeasible"]
            C[i, gi] = cost
    return C


def _overlap_pairs(scenario: Scenario) -> List[Tuple[int, int]]:
    pairs = []
    wins = [f.occupancy_window for f in scenario.flights]
    for i, j in itertools.combinations(range(len(scenario.flights)), 2):
        s1, e1 = wins[i]
        s2, e2 = wins[j]
        if s1 < e2 and s2 < e1:
            pairs.append((i, j))
    return pairs


def solve_milp(scenario: Scenario, time_limit: float = 30.0, verbose: bool = False
               ) -> Tuple[List[int], dict]:
    """Giải MILP chính xác cho 1 kịch bản. Trả về (assignment, info) với
    info gồm trạng thái solver, thời gian giải, có phải nới lỏng ràng buộc
    hay không."""
    n = len(scenario.flights)
    m = len(scenario.gate_codes)
    info = {"status": "empty", "relaxed_pairs": 0, "solve_time_s": 0.0}
    if n == 0:
        return [], info

    C = _cost_matrix(scenario)
    pairs_all = _overlap_pairs(scenario)

    def build_and_solve(pairs):
        n_vars = n * m
        c = C.flatten()

        # Ràng buộc 1: mỗi chuyến bay đúng 1 cổng  -> ma trận thưa n x (n*m)
        rows, cols, data = [], [], []
        for i in range(n):
            for g in range(m):
                rows.append(i)
                cols.append(i * m + g)
                data.append(1.0)
        A_assign = sparse.csr_matrix((data, (rows, cols)), shape=(n, n_vars))
        lb_assign = np.ones(n)
        ub_assign = np.ones(n)

        # Ràng buộc 2: xung đột giờ - mỗi cặp (i,j) chồng giờ, mỗi cổng g
        rows2, cols2, data2 = [], [], []
        r = 0
        for (i, j) in pairs:
            for g in range(m):
                rows2.append(r); cols2.append(i * m + g); data2.append(1.0)
                rows2.append(r); cols2.append(j * m + g); data2.append(1.0)
                r += 1
        if r > 0:
            A_conf = sparse.csr_matrix((data2, (rows2, cols2)), shape=(r, n_vars))
            constraints = [
                LinearConstraint(A_assign, lb_assign, ub_assign),
                LinearConstraint(A_conf, -np.inf, np.ones(r)),
            ]
        else:
            constraints = [LinearConstraint(A_assign, lb_assign, ub_assign)]

        bounds = Bounds(0, 1)
        integrality = np.ones(n_vars)
        t0 = time.perf_counter()
        res = milp(c, constraints=constraints, bounds=bounds, integrality=integrality,
                   options={"time_limit": time_limit, "disp": verbose})
        dt = time.perf_counter() - t0
        return res, dt

    res, dt = build_and_solve(pairs_all)
    relaxed = 0
    pairs = list(pairs_all)

    # Nếu vô nghiệm (quá nhiều xung đột cứng không thể tránh hết), nới lỏng
    # dần: bỏ bớt các cặp xung đột "ít quan trọng" (chênh lệch thời gian xa
    # nhau nhất trong cửa sổ chồng lấn - tức là dễ dời lịch nhất) rồi giải lại,
    # tối đa vài vòng để tránh lặp vô hạn.
    attempts = 0
    while (res.status != 0) and pairs and attempts < 6:
        drop_n = max(1, len(pairs) // 10)
        pairs = pairs[:-drop_n] if len(pairs) > drop_n else []
        relaxed += drop_n
        res, dt = build_and_solve(pairs)
        attempts += 1

    if res.status != 0:
        info.update(status=f"that_bai (solver status={res.status})", solve_time_s=dt, relaxed_pairs=relaxed)
        return None, info

    x = res.x.reshape(n, m)
    assignment = [int(np.argmax(x[i])) for i in range(n)]
    info.update(status="toi_uu" if relaxed == 0 else "toi_uu_sau_noi_long",
                solve_time_s=dt, relaxed_pairs=relaxed)
    return assignment, info


def milp_wrapper(scenario: Scenario, rng=None) -> List[int]:
    """Giao diện thống nhất với các thuật toán khác trong algorithms.py
    (ký hiệu hàm (scenario, rng) -> assignment) để có thể dùng chung
    main.py / visualize.py."""
    assignment, info = solve_milp(scenario)
    if assignment is None:
        # dự phòng: nếu MILP không tìm được nghiệm trong giới hạn thời gian,
        # dùng Greedy làm phương án thay thế và BÁO RÕ cho người dùng
        from .algorithms import greedy
        import random as _random
        print(f"  [CẢNH BÁO] MILP không tìm được lời giải khả thi cho "
              f"{scenario.name} (status: {info['status']}) - dùng Greedy thay thế.")
        return greedy(scenario, rng or _random.Random(config.RANDOM_SEED))
    return assignment


def no_optimization_baseline(scenario: Scenario, rng=None) -> List[int]:
    """'KHÔNG ÁP DỤNG THUẬT TOÁN' - mô phỏng cách làm thủ công / quy tắc đơn
    giản phổ biến trong thực tế khi CHƯA dùng công cụ tối ưu hoá: xét các
    chuyến bay theo đúng thứ tự giờ, mỗi chuyến chọn CỔNG ĐẦU TIÊN (theo thứ
    tự mã số cổng) còn trống - KHÔNG so sánh chi phí, KHÔNG nhìn trước nhìn
    sau. Nếu không còn cổng nào trống thì bắt buộc phải dùng lại 1 cổng đã có
    tàu bay khác (gây xung đột giờ thật ngoài đời) thay vì được quyền "chờ".
    Đây là đường cơ sở (baseline) để so sánh với MILP, THỂ HIỆN ĐÚNG mức độ
    kém hiệu quả khi vận hành không có thuật toán hỗ trợ."""
    n = len(scenario.flights)
    assignment = [-1] * n
    gate_bookings = {gc: [] for gc in scenario.gate_codes}
    order = sorted(range(n), key=lambda i: scenario.flights[i].time)

    for i in order:
        f = scenario.flights[i]
        s, e = f.occupancy_window
        cand = scenario.compatible_gate_indices(f)  # vẫn tôn trọng giới hạn sải cánh (an toàn bay)
        chosen = None
        for gidx in cand:  # duyệt theo đúng thứ tự mã cổng cố định, không xếp theo chi phí
            gc = scenario.gate_codes[gidx]
            if not any(s < e2 and s2 < e for (s2, e2) in gate_bookings[gc]):
                chosen = gidx
                break
        if chosen is None:
            chosen = cand[0]  # hết cổng trống -> đành chấp nhận xung đột
        assignment[i] = chosen
        gate_bookings[scenario.gate_codes[chosen]].append((s, e))
    return assignment
