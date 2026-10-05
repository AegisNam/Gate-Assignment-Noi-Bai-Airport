# -*- coding: utf-8 -*-
"""Xây dựng kịch bản (batch chuyến bay trong 1 khung giờ) và hàm mục tiêu
dùng chung cho mọi thuật toán, để việc so sánh là công bằng."""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from . import config
from .data_loader import Flight, Gate


@dataclass
class Scenario:
    name: str
    start: datetime
    end: datetime
    flights: List[Flight]
    gates: Dict[str, Gate]
    terminal_xy: Dict[str, tuple]
    runway_xy: tuple
    gate_codes: List[str]  # thứ tự cố định để lập chỉ số

    def compatible_gate_indices(self, flight: Flight) -> List[int]:
        idxs = [i for i, g in enumerate(self.gate_codes)
                if self.gates[g].max_wingspan_m >= flight.wingspan_m]
        if not idxs:  # không có cổng nào đủ lớn -> vẫn cho phép, sẽ bị phạt "infeasible"
            idxs = list(range(len(self.gate_codes)))
        return idxs


def build_scenarios(flights: List[Flight], gates: Dict[str, Gate],
                     terminal_xy, runway_xy, base_date: datetime) -> List[Scenario]:
    windows = [
        ("Kịch bản 1 (09:00 - 10:00)", 9, 10),
        ("Kịch bản 2 (10:00 - 11:00)", 10, 11),
        ("Kịch bản 3 (11:00 - 12:00)", 11, 12),
    ]
    gate_codes = sorted(g for g in gates.keys() if g in config.OPERATIONAL_STANDS)
    scenarios = []
    for name, h0, h1 in windows:
        start = base_date.replace(hour=h0, minute=0)
        end = base_date.replace(hour=h1, minute=0) if h1 < 24 else base_date + timedelta(days=1)
        batch = [f for f in flights if start <= f.time < end]
        scenarios.append(Scenario(name, start, end, batch, gates, terminal_xy, runway_xy, gate_codes))
    return scenarios


def _dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def evaluate_assignment(scenario: Scenario, assignment: List[int]) -> Tuple[float, dict]:
    """assignment[i] = chỉ số cổng (trong scenario.gate_codes) gán cho scenario.flights[i].
    Trả về (tổng_chi_phí, chi_tiết_các_thành_phần)."""
    w = config.WEIGHTS
    taxi_cost = walk_cost = remote_cost = infeasible_cost = conflict_cost = 0.0
    n = len(scenario.flights)

    gate_of = {}
    for i, gidx in enumerate(assignment):
        gate = scenario.gates[scenario.gate_codes[gidx]]
        flight = scenario.flights[i]

        taxi_cost += w["taxi"] * _dist((gate.x, gate.y), scenario.runway_xy)
        term_pt = scenario.terminal_xy[flight.terminal]
        walk_cost += w["walk"] * _dist((gate.x, gate.y), term_pt)
        if gate.remote:
            remote_cost += w["remote"]
        if gate.max_wingspan_m < flight.wingspan_m:
            infeasible_cost += w["infeasible"]
        gate_of.setdefault(gidx, []).append(i)

    # phạt xung đột: 2 chuyến cùng cổng có khung giờ chiếm dụng chồng lấn
    for gidx, flight_ids in gate_of.items():
        if len(flight_ids) < 2:
            continue
        windows_ = [scenario.flights[i].occupancy_window for i in flight_ids]
        for a in range(len(windows_)):
            for b in range(a + 1, len(windows_)):
                s1, e1 = windows_[a]
                s2, e2 = windows_[b]
                if s1 < e2 and s2 < e1:  # chồng lấn thời gian
                    conflict_cost += w["conflict"]

    total = taxi_cost + walk_cost + remote_cost + infeasible_cost + conflict_cost
    detail = {
        "taxi": taxi_cost, "walk": walk_cost, "remote": remote_cost,
        "infeasible": infeasible_cost, "conflict": conflict_cost, "total": total,
        "n_flights": n,
    }
    return total, detail
