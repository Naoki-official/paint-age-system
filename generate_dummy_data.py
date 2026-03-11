"""
20系統 × 30日分のダミーセンサーデータを生成するスクリプト。
各系統（line_id）ごとにタンク液面レベル(%)を15分間隔で記録。
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

# === パラメータ ===
START_DATE = datetime(2025, 2, 1, 0, 0, 0)
END_DATE = datetime(2025, 3, 3, 0, 0, 0)
INTERVAL_MINUTES = 15
NUM_LINES = 20  # 配管系統数

# 各系統のパラメータ（多様なパターンを生成）
LINE_CONFIGS = []
for i in range(NUM_LINES):
    LINE_CONFIGS.append({
        'initial_level': random.uniform(70, 100),
        'consumption_min': 0.3 + (i % 5) * 0.15,   # 系統ごとに消費速度が異なる
        'consumption_max': 1.5 + (i % 5) * 0.3,
        'refill_threshold': random.uniform(20, 40),
        'refill_min': 75.0,
        'refill_max': 100.0,
        'op_start': 6 + (i % 3),    # 稼働開始時間に若干のばらつき
        'op_end': 20 + (i % 3),
    })


def is_operating_hour(dt: datetime, config: dict) -> bool:
    return config['op_start'] <= dt.hour < config['op_end']


def generate_line_data(line_id: int, config: dict):
    """1系統分のデータを生成"""
    data = []
    current_time = START_DATE
    current_level = config['initial_level']

    data.append((line_id, current_time, round(current_level, 2)))
    current_time += timedelta(minutes=INTERVAL_MINUTES)

    while current_time <= END_DATE:
        if is_operating_hour(current_time, config):
            if current_level <= config['refill_threshold'] and random.random() < 0.7:
                refill_target = random.uniform(config['refill_min'], config['refill_max'])
                current_level = round(refill_target, 2)
            else:
                consumption = random.uniform(
                    config['consumption_min'], config['consumption_max']
                )
                if 8 <= current_time.hour <= 17:
                    consumption *= random.uniform(1.0, 1.5)
                current_level = max(5.0, current_level - consumption)
                current_level = round(current_level, 2)
        else:
            noise = random.uniform(-0.1, 0.1)
            current_level = max(5.0, min(100.0, current_level + noise))
            current_level = round(current_level, 2)

        data.append((line_id, current_time, current_level))
        current_time += timedelta(minutes=INTERVAL_MINUTES)

    return data


def write_csv(all_data, filepath='sensor_data.csv'):
    """CSVファイルに書き出し"""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['line_id', 'timestamp', 'level'])
        for line_id, ts, level in all_data:
            writer.writerow([line_id, ts.strftime('%Y-%m-%d %H:%M:%S'), level])


if __name__ == '__main__':
    all_data = []
    for i in range(NUM_LINES):
        line_data = generate_line_data(i + 1, LINE_CONFIGS[i])
        all_data.extend(line_data)
        print(f"Line {i+1:2d}: {len(line_data)} records, "
              f"consumption range: {LINE_CONFIGS[i]['consumption_min']:.2f}-{LINE_CONFIGS[i]['consumption_max']:.2f}")

    # タイムスタンプでソート
    all_data.sort(key=lambda x: (x[1], x[0]))
    write_csv(all_data)

    print(f"\nTotal: {len(all_data)} records ({NUM_LINES} lines)")
    print(f"Period: {START_DATE} ~ {END_DATE}")
