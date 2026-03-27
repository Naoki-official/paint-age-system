"""
塗料年齢ダッシュボード — FastAPI バックエンド v2
- 2段FIFOモデル（タンク + 配管）
- 20系統対応
- PostgreSQL or CSVフォールバック
"""

import csv
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="塗料年齢ダッシュボード")

# === 設定 ===
DB_URL = os.environ.get("DATABASE_URL", "")
CSV_PATH = os.path.join(os.path.dirname(__file__), "sensor_data.csv")

# 系統ごとのデフォルト設定
DEFAULT_TANK_CAPACITY = 50.0   # L
DEFAULT_PIPE_CAPACITY = 200.0  # L

LINE_NAMES = {
    1: "ライン 1 (ホワイト)", 2: "ライン 2 (ブラック)", 3: "ライン 3 (シルバー)",
    4: "ライン 4 (レッド)", 5: "ライン 5 (ブルー)", 6: "ライン 6 (グレー)",
    7: "ライン 7 (ホワイトパール)", 8: "ライン 8 (ブラックメタリック)",
    9: "ライン 9 (ダークブルー)", 10: "ライン 10 (ワインレッド)",
    11: "ライン 11 (ベージュ)", 12: "ライン 12 (グリーン)",
    13: "ライン 13 (オレンジ)", 14: "ライン 14 (イエロー)",
    15: "ライン 15 (ブラウン)", 16: "ライン 16 (ライトブルー)",
    17: "ライン 17 (ピンク)", 18: "ライン 18 (パープル)",
    19: "ライン 19 (クリア)", 20: "ライン 20 (プライマー)",
}

# === PostgreSQL接続 ===
pool = None


async def get_pg_pool():
    global pool
    if pool is None and DB_URL:
        try:
            import asyncpg
            pool = await asyncpg.create_pool(DB_URL)
        except Exception as e:
            print(f"PostgreSQL接続失敗（CSVフォールバック使用）: {e}")
    return pool


# === CSVデータ読み込み ===
def read_csv_data():
    """CSVから全系統のセンサーデータを読み込む"""
    data = {}  # line_id -> list of {timestamp, level}
    with open(CSV_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            line_id = int(row["line_id"])
            if line_id not in data:
                data[line_id] = []
            data[line_id].append({
                "timestamp": datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S"),
                "level": float(row["level"]),
            })
    # 各系統をタイムスタンプでソート
    for line_id in data:
        data[line_id].sort(key=lambda x: x["timestamp"])
    return data


# === 2段FIFO方式の塗料年齢計算 ===
def calculate_paint_age_2stage(
    sensor_data: list,
    tank_capacity: float = DEFAULT_TANK_CAPACITY,
    pipe_capacity: float = DEFAULT_PIPE_CAPACITY,
) -> list:
    """
    2段FIFOモデルで塗料年齢を計算。

    タンク(tank_capacity L) → 配管(pipe_capacity L) → ロボット

    - タンクに新塗料補充 → タンクFIFOにバッチ追加
    - タンクから塗料消費 → タンクFIFOの先頭から取り出し → 配管FIFOの末尾に追加
    - ロボットが消費 → 配管FIFOの先頭から消費

    ※センサーはタンク液面のみ観測。タンク液面の減少量 = 配管への流入量 = ロボットの消費量
    """
    batches_tank = deque()  # (volume_L, injection_timestamp)
    batches_pipe = deque()  # (volume_L, injection_timestamp)
    current_level_l = 0.0   # タンク残量 (L)
    pipe_total = 0.0        # 配管内総量 (L)
    results = []

    for event in sensor_data:
        ts = event["timestamp"]
        new_level_pct = event["level"]
        new_level_l = (new_level_pct / 100.0) * tank_capacity

        if new_level_l > current_level_l + 0.3:
            # === 補充検出（タンクに新塗料追加） ===
            inject_vol = new_level_l - current_level_l
            batches_tank.append((inject_vol, ts))

        elif new_level_l < current_level_l - 0.05:
            # === 消費検出（タンク → 配管 → ロボット） ===
            consumption = current_level_l - new_level_l

            # Step 1: タンクFIFOから取り出し → 配管FIFOの末尾に追加
            moved_to_pipe = 0.0
            while consumption > 0.01 and batches_tank:
                batch_vol, batch_ts = batches_tank[0]
                if batch_vol <= consumption + 0.01:
                    consumption -= batch_vol
                    batches_tank.popleft()
                    batches_pipe.append((batch_vol, batch_ts))
                    moved_to_pipe += batch_vol
                else:
                    batches_tank[0] = (batch_vol - consumption, batch_ts)
                    batches_pipe.append((consumption, batch_ts))
                    moved_to_pipe += consumption
                    consumption = 0

            pipe_total += moved_to_pipe

            # Step 2: 配管が容量を超えたら先頭（最古）から排出（ロボットが消費）
            while pipe_total > pipe_capacity + 0.01 and batches_pipe:
                overflow = pipe_total - pipe_capacity
                batch_vol, batch_ts = batches_pipe[0]
                if batch_vol <= overflow + 0.01:
                    pipe_total -= batch_vol
                    batches_pipe.popleft()
                else:
                    batches_pipe[0] = (batch_vol - overflow, batch_ts)
                    pipe_total -= overflow

        # === 年齢計算 ===
        # タンク内の加重平均年齢
        tank_total = sum(b[0] for b in batches_tank)
        if tank_total > 0:
            tank_avg_age = sum(
                b[0] * (ts - b[1]).total_seconds() / 3600 for b in batches_tank
            ) / tank_total
        else:
            tank_avg_age = 0.0

        # 配管内の加重平均年齢
        pipe_vol_total = sum(b[0] for b in batches_pipe)
        if pipe_vol_total > 0:
            pipe_avg_age = sum(
                b[0] * (ts - b[1]).total_seconds() / 3600 for b in batches_pipe
            ) / pipe_vol_total
        else:
            pipe_avg_age = 0.0

        # ロボット到達点の年齢（配管先頭 = 最古バッチ）
        if batches_pipe:
            robot_age = (ts - batches_pipe[0][1]).total_seconds() / 3600
        else:
            robot_age = 0.0

        # 全体（タンク + 配管）の加重平均年齢
        total_vol = tank_total + pipe_vol_total
        if total_vol > 0:
            system_avg_age = (tank_avg_age * tank_total + pipe_avg_age * pipe_vol_total) / total_vol
        else:
            system_avg_age = 0.0

        results.append({
            "timestamp": ts.isoformat(),
            "level": new_level_pct,
            "tank_avg_age": round(tank_avg_age, 2),
            "pipe_avg_age": round(pipe_avg_age, 2),
            "robot_age": round(robot_age, 2),
            "system_avg_age": round(system_avg_age, 2),
            "tank_batches": len(batches_tank),
            "pipe_batches": len(batches_pipe),
            "pipe_fill_pct": round((pipe_vol_total / pipe_capacity) * 100, 1) if pipe_capacity > 0 else 0,
        })

        current_level_l = new_level_l

    # 移動平均（5ポイント）
    window = 5
    for i in range(len(results)):
        start = max(0, i - window + 1)
        avg = sum(r["robot_age"] for r in results[start:i + 1]) / (i - start + 1)
        results[i]["robot_age_ma"] = round(avg, 2)

    return results


# === キャッシュ ===
_cached_data = None


def get_all_data():
    """全系統の計算済みデータを取得（キャッシュ付き）"""
    global _cached_data
    if _cached_data is None:
        csv_data = read_csv_data()
        _cached_data = {}
        for line_id, sensor in csv_data.items():
            _cached_data[line_id] = calculate_paint_age_2stage(sensor)
    return _cached_data


# === API エンドポイント ===

@app.get("/api/lines")
async def get_lines():
    """利用可能な系統一覧を返す"""
    all_data = get_all_data()
    lines = []
    for line_id in sorted(all_data.keys()):
        data = all_data[line_id]
        latest = data[-1] if data else {}
        lines.append({
            "line_id": line_id,
            "name": LINE_NAMES.get(line_id, f"ライン {line_id}"),
            "current_robot_age": latest.get("robot_age", 0),
            "current_level": latest.get("level", 0),
        })
    return JSONResponse(content=lines)


@app.get("/api/paint-age")
async def get_paint_age(
    line_id: int = Query(1, description="配管系統ID"),
    hours: float = Query(6, description="取得する時間範囲 [H]"),
):
    """指定系統・時間範囲の塗料年齢データを返す"""
    pg = await get_pg_pool()

    if pg:
        async with pg.acquire() as conn:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            rows = await conn.fetch(
                """
                SELECT timestamp, level
                FROM sensor_readings
                WHERE line_id = $1 AND timestamp >= $2
                ORDER BY timestamp
                """,
                line_id, cutoff,
            )
            sensor = [
                {"timestamp": row["timestamp"], "level": float(row["level"])}
                for row in rows
            ]
            if sensor:
                return JSONResponse(content=calculate_paint_age_2stage(sensor))
            return JSONResponse(content=[])
    else:
        all_data = get_all_data()
        line_data = all_data.get(line_id, [])
        if not line_data:
            return JSONResponse(content=[])

        last_ts = datetime.fromisoformat(line_data[-1]["timestamp"])
        cutoff = (last_ts - timedelta(hours=hours)).isoformat()
        filtered = [d for d in line_data if d["timestamp"] >= cutoff]
        return JSONResponse(content=filtered)


@app.get("/api/overview")
async def get_overview():
    """全系統の最新状態サマリー"""
    all_data = get_all_data()
    overview = []
    for line_id in sorted(all_data.keys()):
        data = all_data[line_id]
        if not data:
            continue
        latest = data[-1]
        overview.append({
            "line_id": line_id,
            "name": LINE_NAMES.get(line_id, f"ライン {line_id}"),
            "robot_age": latest["robot_age"],
            "pipe_avg_age": latest["pipe_avg_age"],
            "tank_avg_age": latest["tank_avg_age"],
            "level": latest["level"],
            "pipe_fill_pct": latest["pipe_fill_pct"],
        })
    return JSONResponse(content=overview)


@app.get("/api/time-range")
async def get_time_range(line_id: int = Query(1)):
    """指定系統のデータ時間範囲を返す"""
    all_data = get_all_data()
    line_data = all_data.get(line_id, [])
    if not line_data:
        return JSONResponse(content={"start": None, "end": None})
    return JSONResponse(content={
        "start": line_data[0]["timestamp"],
        "end": line_data[-1]["timestamp"],
    })


# === 静的ファイル ===

@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/style.css")
async def css():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "style.css"),
        media_type="text/css",
    )


@app.get("/main.js")
async def js():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "main.js"),
        media_type="application/javascript",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)