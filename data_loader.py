# -*- coding: utf-8 -*-
"""
Nạp dữ liệu cổng đỗ (từ sơ đồ AIP Nội Bài) và lịch bay (9h-12h 16/09/2026)
đã được trích xuất sẵn thành JSON trong thư mục data/.
"""
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import config


@dataclass
class Gate:
    code: str
    x: float  # mét, hệ toạ độ cục bộ
    y: float
    max_wingspan_m: float
    terminal: str
    remote: bool


@dataclass
class Flight:
    flight_no: str
    section: str          # 'arrival' | 'departure'
    time: datetime
    aircraft_type: str
    wingspan_m: float
    turnaround_min: int
    real_gate: str         # cổng thực tế ghi nhận trong dữ liệu (để đối chiếu)
    terminal: str          # T1 / T2 (giả định theo hãng bay)

    @property
    def occupancy_window(self):
        """Khoảng thời gian tàu bay chiếm dụng vị trí đỗ (giả định)."""
        half = timedelta(minutes=self.turnaround_min)
        if self.section == "arrival":
            return self.time, self.time + half
        else:
            return self.time - half, self.time


def _latlon_to_xy(lat, lon, lat0, lon0):
    x = (lon - lon0) * config.METERS_PER_DEG_LON
    y = (lat - lat0) * config.METERS_PER_DEG_LAT
    return x, y


def load_gates() -> Dict[str, Gate]:
    with open(os.path.join(config.DATA_DIR, "gate_coords.json"), encoding="utf-8") as f:
        coords = json.load(f)
    with open(os.path.join(config.DATA_DIR, "gate_wingspan_limit.json"), encoding="utf-8") as f:
        wingspans = json.load(f)

    lat0 = sum(v["lat"] for v in coords.values()) / len(coords)
    lon0 = sum(v["lon"] for v in coords.values()) / len(coords)

    # Toạ độ nội suy cho vài cổng không có trong sơ đồ trích xuất được
    # (đặt gần cụm số hiệu lân cận nhất theo GHI CHÚ - không phải số liệu gốc)
    fallback = {
        "53": {"lat": (coords["52"]["lat"] + coords.get("55B", coords["52"])["lat"]) / 2,
               "lon": (coords["52"]["lon"] + coords.get("55B", coords["52"])["lon"]) / 2},
        "54B": coords.get("55B", coords["52"]),
        "E": coords["31"],  # gần khu cargo/apron thấp - vị trí gần đúng
    }
    for code, ll in fallback.items():
        if code not in coords:
            coords[code] = {"lat": ll["lat"], "lon": ll["lon"], "elev_m": 12.0}

    gates = {}
    for code, ll in coords.items():
        x, y = _latlon_to_xy(ll["lat"], ll["lon"], lat0, lon0)
        span = wingspans.get(code, config.DEFAULT_WINGSPAN_M)
        gates[code] = Gate(
            code=code,
            x=x,
            y=y,
            max_wingspan_m=span,
            terminal=config.gate_terminal(code),
            remote=config.is_remote_stand(code),
        )
    return gates


_TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(AM|PM)")


def _parse_time(s: str, base_date: datetime) -> datetime:
    m = _TIME_RE.match(s)
    h, mnt, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return base_date.replace(hour=h, minute=mnt)


def load_flights(base_date: Optional[datetime] = None) -> List[Flight]:
    if base_date is None:
        base_date = datetime(2026, 9, 16, 0, 0)
    with open(os.path.join(config.DATA_DIR, "flights_parsed.json"), encoding="utf-8") as f:
        raw = json.load(f)

    flights = []
    for r in raw:
        actype = r["aircraft_type"]
        wingspan = config.AIRCRAFT_WINGSPAN_M.get(actype, config.DEFAULT_WINGSPAN_M)
        body = "wide" if actype in config.WIDE_BODY_TYPES else "narrow"
        turnaround = config.TURNAROUND_MIN[body]
        flights.append(
            Flight(
                flight_no=r["flight_no"],
                section=r["section"],
                time=_parse_time(r["time"], base_date),
                aircraft_type=actype,
                wingspan_m=wingspan,
                turnaround_min=turnaround,
                real_gate=r["gate"],
                terminal=config.flight_terminal(r["flight_no"]),
            )
        )
    flights.sort(key=lambda f: f.time)
    return flights


def terminal_building_xy(gates: Dict[str, Gate]) -> Dict[str, tuple]:
    """Toạ độ (xấp xỉ) của nhà ga T1 / T2, lấy bằng trọng tâm cụm cổng
    thuộc nhà ga đó (GIẢ ĐỊNH minh hoạ, không phải toạ độ chính thức)."""
    result = {}
    for term in ("T1", "T2"):
        pts = [(g.x, g.y) for g in gates.values() if g.terminal == term and not g.remote]
        if not pts:
            pts = [(g.x, g.y) for g in gates.values() if g.terminal == term]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        result[term] = (cx, cy)
    return result


def runway_access_xy(gates: Dict[str, Gate]) -> tuple:
    """Điểm truy cập đường lăn tham chiếu (xấp xỉ) dùng để ước lượng quãng
    đường lăn - lấy là điểm cực Bắc của cụm sân đỗ (gần khu vực đường CHC)."""
    ys = [g.y for g in gates.values()]
    xs = [g.x for g in gates.values()]
    return sum(xs) / len(xs), max(ys)
