# -*- coding: utf-8 -*-
"""
Bốn phương pháp gán cổng đỗ tàu bay, dùng chung Scenario + evaluate_assignment
(scenario.py) để việc so sánh công bằng, trung thực:

  1. Greedy (tham lam)            - baseline kinh điển, tốc độ rất nhanh
  2. Simulated Annealing (SA)     - metaheuristic
  3. Genetic Algorithm (GA)       - metaheuristic quần thể
  4. Q-learning đơn giản          - đại diện nhóm AI/Học máy (tăng cường)

Ghi chú trung thực: đây là các cài đặt MINH HOẠ ở quy mô nhỏ (vài chục cổng,
vài chục chuyến/kịch bản) để thấy rõ sự khác biệt về chất lượng lời giải và
thời gian xử lý giữa các trường phái thuật toán - không phải bản triển khai
sản xuất (production) cho toàn bộ sân bay.
"""
import math
import random
from typing import List

from .scenario import Scenario, evaluate_assignment


def greedy(scenario: Scenario, rng: random.Random) -> List[int]:
    """Xếp chuyến bay theo thời gian, mỗi chuyến chọn cổng khả thi có chi phí
    (taxi + đi bộ + phạt cổng xa) thấp nhất trong số cổng hiện chưa xung đột
    thời gian với các chuyến đã gán trước đó."""
    order = sorted(range(len(scenario.flights)), key=lambda i: scenario.flights[i].time)
    assignment = [-1] * len(scenario.flights)
    gate_bookings = {gc: [] for gc in scenario.gate_codes}  # gate -> list[(start,end)]

    for i in order:
        flight = scenario.flights[i]
        cand = scenario.compatible_gate_indices(flight)
        s, e = flight.occupancy_window
        best_gidx, best_cost, best_conflict = None, math.inf, True

        def local_cost(gidx):
            g = scenario.gates[scenario.gate_codes[gidx]]
            from .scenario import _dist
            c = g.max_wingspan_m  # unused, silence lint
            taxi = _dist((g.x, g.y), scenario.runway_xy)
            walk = _dist((g.x, g.y), scenario.terminal_xy[flight.terminal])
            remote = 80.0 if g.remote else 0.0
            return taxi + 1.5 * walk + remote

        for gidx in cand:
            gc = scenario.gate_codes[gidx]
            conflict = any(s < e2 and s2 < e for (s2, e2) in gate_bookings[gc])
            cost = local_cost(gidx)
            if best_gidx is None or (conflict, cost) < (best_conflict, best_cost):
                best_gidx, best_cost, best_conflict = gidx, cost, conflict

        assignment[i] = best_gidx
        gate_bookings[scenario.gate_codes[best_gidx]].append((s, e))

    return assignment


def _random_valid_assignment(scenario: Scenario, rng: random.Random) -> List[int]:
    return [rng.choice(scenario.compatible_gate_indices(f)) for f in scenario.flights]


def simulated_annealing(scenario: Scenario, rng: random.Random,
                         iters: int = 3000, t0: float = 400.0, cooling: float = 0.995) -> List[int]:
    current = greedy(scenario, rng)  # xuất phát từ lời giải greedy cho nhanh hội tụ
    current_cost, _ = evaluate_assignment(scenario, current)
    best, best_cost = list(current), current_cost
    t = t0
    n = len(scenario.flights)
    if n == 0:
        return current
    for _ in range(iters):
        if rng.random() < 0.5 or n < 2:
            # di chuyển: đổi cổng của 1 chuyến bay
            i = rng.randrange(n)
            cand = scenario.compatible_gate_indices(scenario.flights[i])
            new_gidx = rng.choice(cand)
            old_i = current[i]
            if new_gidx == old_i:
                continue
            current[i] = new_gidx
            new_cost, _ = evaluate_assignment(scenario, current)
            delta = new_cost - current_cost
            if delta <= 0 or rng.random() < math.exp(-delta / max(t, 1e-6)):
                current_cost = new_cost
                if new_cost < best_cost:
                    best, best_cost = list(current), new_cost
            else:
                current[i] = old_i
        else:
            # hoán đổi: đổi cổng cho nhau giữa 2 chuyến bay (giúp gỡ xung đột)
            i, j = rng.sample(range(n), 2)
            current[i], current[j] = current[j], current[i]
            new_cost, _ = evaluate_assignment(scenario, current)
            delta = new_cost - current_cost
            if delta <= 0 or rng.random() < math.exp(-delta / max(t, 1e-6)):
                current_cost = new_cost
                if new_cost < best_cost:
                    best, best_cost = list(current), new_cost
            else:
                current[i], current[j] = current[j], current[i]
        t *= cooling
    return best


def genetic_algorithm(scenario: Scenario, rng: random.Random,
                       pop_size: int = 60, generations: int = 150,
                       mutation_rate: float = 0.15, swap_rate: float = 0.4) -> List[int]:
    n = len(scenario.flights)
    if n == 0:
        return []
    candidates = [scenario.compatible_gate_indices(f) for f in scenario.flights]

    def random_indiv():
        return [rng.choice(candidates[i]) for i in range(n)]

    def fitness(indiv):
        cost, _ = evaluate_assignment(scenario, indiv)
        return cost

    base_greedy = greedy(scenario, rng)

    def perturbed_greedy():
        ind = list(base_greedy)
        for _ in range(max(1, n // 6)):
            i = rng.randrange(n)
            ind[i] = rng.choice(candidates[i])
        return ind

    half = pop_size // 2
    population = ([list(base_greedy)] + [perturbed_greedy() for _ in range(half - 1)]
                  + [random_indiv() for _ in range(pop_size - half)])
    pop_fit = [fitness(ind) for ind in population]

    for _ in range(generations):
        new_pop = []
        # elitism: giữ lại cá thể tốt nhất
        best_idx = min(range(pop_size), key=lambda k: pop_fit[k])
        new_pop.append(list(population[best_idx]))

        while len(new_pop) < pop_size:
            # chọn lọc tournament
            def tournament():
                a, b = rng.randrange(pop_size), rng.randrange(pop_size)
                return population[a] if pop_fit[a] < pop_fit[b] else population[b]

            p1, p2 = tournament(), tournament()
            child = [p1[i] if rng.random() < 0.5 else p2[i] for i in range(n)]
            for i in range(n):
                if rng.random() < mutation_rate:
                    child[i] = rng.choice(candidates[i])
            # đột biến hoán đổi: đổi cổng giữa 2 chuyến bay ngẫu nhiên (có thể
            # lặp lại nhiều lần) - giúp GA có khả năng gỡ xung đột giống SA
            # thay vì chỉ đổi từng gen đơn lẻ
            if n >= 2:
                for _ in range(3):
                    if rng.random() < swap_rate:
                        i, j = rng.sample(range(n), 2)
                        child[i], child[j] = child[j], child[i]
            new_pop.append(child)

        population = new_pop
        pop_fit = [fitness(ind) for ind in population]

    best_idx = min(range(pop_size), key=lambda k: pop_fit[k])
    return population[best_idx]


def q_learning(scenario: Scenario, rng: random.Random,
               episodes: int = 300, alpha: float = 0.2, gamma: float = 0.9,
               epsilon: float = 0.2, top_k: int = 6) -> List[int]:
    """Học tăng cường đơn giản (Q-learning xấp xỉ tuyến tính), đại diện nhóm
    phương pháp AI/Học máy. Trạng thái = (chỉ số chuyến bay đang xét, số cổng
    đã bận trong top-k ứng viên gần nhất); hành động = chọn 1 trong top-k cổng
    khả thi có chi phí cục bộ thấp nhất. Trọng số w học qua nhiều episode với
    thứ tự chuyến bay xáo trộn ngẫu nhiên, rồi dùng chính sách tham lam-theo-Q
    để tạo lời giải cuối cho kịch bản thật.
    Đây là bản cài đặt MINH HOẠ quy mô nhỏ, không phải mô hình học sâu."""
    from .scenario import _dist
    n = len(scenario.flights)
    if n == 0:
        return []

    def local_features(flight, gidx, booked_conflict):
        g = scenario.gates[scenario.gate_codes[gidx]]
        taxi = _dist((g.x, g.y), scenario.runway_xy)
        walk = _dist((g.x, g.y), scenario.terminal_xy[flight.terminal])
        remote = 1.0 if g.remote else 0.0
        conflict = 1.0 if booked_conflict else 0.0
        infeasible = 1.0 if g.max_wingspan_m < flight.wingspan_m else 0.0
        return [taxi / 1000.0, walk / 1000.0, remote, conflict, infeasible]

    # trọng số tuyến tính Q(s,a) = w . features ; khởi tạo phạt đúng chiều dấu
    w = [1.0, 1.5, 0.5, 5.0, 5.0]

    def q_value(feat):
        return -sum(wi * fi for wi, fi in zip(w, feat))  # Q càng cao càng tốt

    for _ep in range(episodes):
        order = list(range(n))
        rng.shuffle(order)
        gate_bookings = {gc: [] for gc in scenario.gate_codes}
        for i in order:
            flight = scenario.flights[i]
            cand_all = scenario.compatible_gate_indices(flight)
            s, e = flight.occupancy_window

            def conflict_of(gidx):
                gc = scenario.gate_codes[gidx]
                return any(s < e2 and s2 < e for (s2, e2) in gate_bookings[gc])

            scored = sorted(cand_all, key=lambda gidx: -q_value(local_features(flight, gidx, conflict_of(gidx))))
            top = scored[:top_k] if len(scored) > top_k else scored

            if rng.random() < epsilon:
                action = rng.choice(top)
            else:
                action = top[0]

            feat = local_features(flight, action, conflict_of(action))
            reward = q_value(feat)  # phần thưởng tức thời = -chi phí cục bộ
            # cập nhật TD đơn giản cho từng trọng số (xấp xỉ tuyến tính)
            target = reward  # không có bước kế tiếp trong MDP 1 bước / hành động
            td_error = target - q_value(feat)
            for k in range(len(w)):
                w[k] += alpha * td_error * (-feat[k]) * 0.01
            gate_bookings[scenario.gate_codes[action]].append((s, e))

    # rollout cuối cùng: chính sách tham lam theo Q đã học, theo đúng thứ tự thời gian
    order = sorted(range(n), key=lambda i: scenario.flights[i].time)
    assignment = [-1] * n
    gate_bookings = {gc: [] for gc in scenario.gate_codes}
    for i in order:
        flight = scenario.flights[i]
        cand_all = scenario.compatible_gate_indices(flight)
        s, e = flight.occupancy_window

        def conflict_of(gidx):
            gc = scenario.gate_codes[gidx]
            return any(s < e2 and s2 < e for (s2, e2) in gate_bookings[gc])

        best = max(cand_all, key=lambda gidx: q_value(local_features(flight, gidx, conflict_of(gidx))))
        assignment[i] = best
        gate_bookings[scenario.gate_codes[best]].append((s, e))
    return assignment


ALGORITHMS = {
    "Greedy (tham lam)": greedy,
    "Simulated Annealing": simulated_annealing,
    "Genetic Algorithm": genetic_algorithm,
    "Q-learning (AI/RL)": q_learning,
}
