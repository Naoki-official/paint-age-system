-- ============================================================
-- 塗料年齢管理システム — テーブル定義 & データインポート
-- 20系統対応版
-- ============================================================

-- ============================================================
-- 1. テーブル定義
-- ============================================================

DROP TABLE IF EXISTS sensor_readings CASCADE;

CREATE TABLE sensor_readings (
    id          SERIAL PRIMARY KEY,
    line_id     INTEGER NOT NULL,            -- 配管系統ID (1-20)
    timestamp   TIMESTAMPTZ NOT NULL,
    level       NUMERIC(6, 2) NOT NULL       -- タンク液面レベル (%)
);

-- インデックス
CREATE INDEX idx_sensor_line_timestamp ON sensor_readings(line_id, timestamp);
CREATE INDEX idx_sensor_timestamp ON sensor_readings(timestamp);

-- ============================================================
-- 2. 系統マスタ（任意）
-- ============================================================

DROP TABLE IF EXISTS pipe_lines CASCADE;

CREATE TABLE pipe_lines (
    line_id         INTEGER PRIMARY KEY,
    line_name       VARCHAR(50) NOT NULL,
    tank_capacity   NUMERIC(8, 2) DEFAULT 50.0,    -- タンク容量 (L)
    pipe_capacity   NUMERIC(8, 2) DEFAULT 200.0,   -- 配管容量 (L)
    color_name      VARCHAR(50),                    -- 塗料の色名
    description     TEXT
);

-- 20系統のマスタデータ挿入
INSERT INTO pipe_lines (line_id, line_name, tank_capacity, pipe_capacity, color_name) VALUES
( 1, 'ライン 1',  50, 200, 'ホワイト'),
( 2, 'ライン 2',  50, 200, 'ブラック'),
( 3, 'ライン 3',  50, 200, 'シルバー'),
( 4, 'ライン 4',  50, 200, 'レッド'),
( 5, 'ライン 5',  50, 200, 'ブルー'),
( 6, 'ライン 6',  50, 200, 'グレー'),
( 7, 'ライン 7',  50, 200, 'ホワイトパール'),
( 8, 'ライン 8',  50, 200, 'ブラックメタリック'),
( 9, 'ライン 9',  50, 200, 'ダークブルー'),
(10, 'ライン 10', 50, 200, 'ワインレッド'),
(11, 'ライン 11', 50, 200, 'ベージュ'),
(12, 'ライン 12', 50, 200, 'グリーン'),
(13, 'ライン 13', 50, 200, 'オレンジ'),
(14, 'ライン 14', 50, 200, 'イエロー'),
(15, 'ライン 15', 50, 200, 'ブラウン'),
(16, 'ライン 16', 50, 200, 'ライトブルー'),
(17, 'ライン 17', 50, 200, 'ピンク'),
(18, 'ライン 18', 50, 200, 'パープル'),
(19, 'ライン 19', 50, 200, 'クリア'),
(20, 'ライン 20', 50, 200, 'プライマー');

-- ============================================================
-- 3. CSVデータのインポート
-- ============================================================
-- \copy sensor_readings(line_id, timestamp, level) FROM 'sensor_data.csv' DELIMITER ',' CSV HEADER;
