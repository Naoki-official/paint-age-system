-- ============================================================
-- 塗料年齢管理システム — ビュー定義（20系統対応版）
-- ============================================================

-- ============================================================
-- 1. v_level_changes — 系統別の液面変化ビュー
-- ============================================================
DROP VIEW IF EXISTS v_hourly_summary CASCADE;
DROP VIEW IF EXISTS v_paint_age CASCADE;
DROP VIEW IF EXISTS v_fill_events CASCADE;
DROP VIEW IF EXISTS v_level_changes CASCADE;

CREATE VIEW v_level_changes AS
SELECT
    id,
    line_id,
    timestamp,
    level,
    LAG(level) OVER (PARTITION BY line_id ORDER BY timestamp)            AS prev_level,
    level - LAG(level) OVER (PARTITION BY line_id ORDER BY timestamp)    AS level_diff,
    CASE
        WHEN level - LAG(level) OVER (PARTITION BY line_id ORDER BY timestamp) > 1.0  THEN 'REFILL'
        WHEN level - LAG(level) OVER (PARTITION BY line_id ORDER BY timestamp) < -0.5 THEN 'CONSUMPTION'
        ELSE 'IDLE'
    END AS event_type
FROM sensor_readings
ORDER BY line_id, timestamp;

-- ============================================================
-- 2. v_fill_events — 系統別の補充イベント一覧
-- ============================================================
CREATE VIEW v_fill_events AS
SELECT
    id,
    line_id,
    timestamp                                       AS refill_time,
    prev_level,
    level                                           AS new_level,
    level_diff                                      AS refill_amount
FROM v_level_changes
WHERE event_type = 'REFILL'
ORDER BY line_id, timestamp;

-- ============================================================
-- 3. v_paint_age — 系統別の塗料年齢ビュー
--    ※タンクからの経過時間（簡易版）
--    ※配管滞留時間を含む精密なFIFO計算はPython側で実施
-- ============================================================
CREATE VIEW v_paint_age AS
SELECT
    sr.id,
    sr.line_id,
    sr.timestamp,
    sr.level,
    lc.event_type,
    lc.level_diff,
    (
        SELECT MAX(fe.refill_time)
        FROM v_fill_events fe
        WHERE fe.line_id = sr.line_id
          AND fe.refill_time <= sr.timestamp
    ) AS last_refill_time,
    EXTRACT(EPOCH FROM (
        sr.timestamp - COALESCE(
            (SELECT MAX(fe.refill_time) FROM v_fill_events fe
             WHERE fe.line_id = sr.line_id AND fe.refill_time <= sr.timestamp),
            sr.timestamp
        )
    )) / 3600.0 AS hours_since_refill
FROM sensor_readings sr
JOIN v_level_changes lc ON sr.id = lc.id
ORDER BY sr.line_id, sr.timestamp;

-- ============================================================
-- 4. v_hourly_summary — 系統別 × 1時間ごとの集計ビュー
-- ============================================================
CREATE VIEW v_hourly_summary AS
SELECT
    line_id,
    date_trunc('hour', timestamp)     AS hour_bucket,
    AVG(level)                        AS avg_level,
    MIN(level)                        AS min_level,
    MAX(level)                        AS max_level,
    COUNT(*)                          AS reading_count,
    AVG(hours_since_refill)           AS avg_hours_since_refill,
    MAX(hours_since_refill)           AS max_hours_since_refill,
    BOOL_OR(event_type = 'REFILL')    AS had_refill
FROM v_paint_age
GROUP BY line_id, date_trunc('hour', timestamp)
ORDER BY line_id, hour_bucket;
