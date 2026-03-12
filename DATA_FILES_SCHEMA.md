# โครงสร้างไฟล์และ Schema สำหรับเก็บข้อมูล

## เป้าหมาย

เอกสารนี้สรุปว่า:

- ควรสร้างไฟล์อะไรบ้าง
- แต่ละไฟล์ควรอยู่ path ไหน
- แต่ละไฟล์เก็บข้อมูลระดับไหน
- แต่ละไฟล์ควรมีคอลัมน์อะไรบ้าง

เอกสารนี้อิงจาก [DATA_COLLECTION_REQUIREMENTS.md](D:/git/poc_lighter_hyperliquid/DATA_COLLECTION_REQUIREMENTS.md)

## แนวคิดการออกแบบ

- แยก `reference`, `raw`, `processed`, `derived`, `logs`
- ใช้ `Parquet` เป็นค่าเริ่มต้นสำหรับ table หลัก
- ใช้ `UTC` ทุกไฟล์
- เก็บ `raw` แบบ append-only
- เก็บ `processed` และ `derived` แบบ regenerate ได้
- แยก `event-driven` กับ `snapshot` ออกจากกัน

## จำนวนไฟล์ที่แนะนำ

### ชุดขั้นต่ำสำหรับเริ่ม POC

10 logical files

### ชุดมาตรฐานสำหรับ POC เต็ม

16 logical files

### ชุดเต็มสำหรับประเมิน scale ถึง 1M USD

20 logical files

## โครงสร้าง path ที่แนะนำ

```text
data/
  reference/
  raw/
    lighter/
      funding/
      orderbook/
      trades/
      oi/
      account/
    hyperliquid/
      funding/
      orderbook/
      trades/
      oi/
      account/
  processed/
  derived/
logs/
  strategy/
  execution/
  risk/
  recovery/
reports/
```

## ชุดขั้นต่ำ 10 ไฟล์

### 1. `data/reference/shared_markets.parquet`

หน้าที่:
- เก็บ symbol mapping ระหว่าง Lighter และ Hyperliquid

grain:
- 1 row ต่อ shared symbol pair

คอลัมน์หลัก:
- `symbol_canonical`
- `symbol_lighter`
- `symbol_hyperliquid`
- `base_asset`
- `quote_asset`
- `is_active`
- `created_at_utc`
- `updated_at_utc`

### 2. `data/reference/instrument_metadata.parquet`

หน้าที่:
- เก็บ market metadata ที่ใช้ normalize และ execute

grain:
- 1 row ต่อ venue ต่อ symbol

คอลัมน์หลัก:
- `venue`
- `symbol`
- `contract_size`
- `tick_size`
- `lot_size`
- `min_order_size`
- `quote_currency`
- `max_leverage`
- `margin_mode`
- `funding_interval_minutes`
- `maker_fee_bps`
- `taker_fee_bps`
- `oi_cap`
- `rate_limit_note`
- `as_of_utc`

### 3. `data/processed/funding_snapshots.parquet`

หน้าที่:
- เก็บ funding snapshots ที่ใช้สร้าง spread signal

grain:
- 1 row ต่อ venue ต่อ symbol ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `symbol`
- `predicted_funding_rate`
- `current_funding_rate`
- `settled_funding_rate`
- `predicted_funding_bps_h`
- `current_funding_bps_h`
- `settled_funding_bps_h`
- `next_funding_time_utc`
- `snapshot_age_ms`
- `ingested_at_utc`

### 4. `data/processed/book_snapshots.parquet`

หน้าที่:
- เก็บ BBO และ depth buckets สำหรับคำนวณ slippage และ capacity

grain:
- 1 row ต่อ venue ต่อ symbol ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `symbol`
- `best_bid_px`
- `best_ask_px`
- `mid_px`
- `spread_bps`
- `depth_bid_10k_usd`
- `depth_ask_10k_usd`
- `depth_bid_25k_usd`
- `depth_ask_25k_usd`
- `depth_bid_50k_usd`
- `depth_ask_50k_usd`
- `depth_bid_100k_usd`
- `depth_ask_100k_usd`
- `book_levels_count`
- `ingested_at_utc`

### 5. `data/processed/balance_snapshots.parquet`

หน้าที่:
- เก็บยอดเงินและ collateral ต่อ venue

grain:
- 1 row ต่อ venue ต่อ account ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `account_id`
- `equity_usd`
- `cash_usd`
- `collateral_usd`
- `free_collateral_usd`
- `unrealized_pnl_usd`
- `margin_used_usd`
- `margin_usage_pct`

### 6. `data/processed/position_snapshots.parquet`

หน้าที่:
- เก็บ position state ต่อ symbol

grain:
- 1 row ต่อ venue ต่อ account ต่อ symbol ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `account_id`
- `symbol`
- `position_qty`
- `position_side`
- `entry_px`
- `mark_px`
- `notional_usd`
- `unrealized_pnl_usd`
- `leverage`
- `liquidation_px`
- `liquidation_buffer_bps`

### 7. `logs/execution/order_events.parquet`

หน้าที่:
- เก็บ lifecycle ของ order แบบ event-driven

grain:
- 1 row ต่อ order event

คอลัมน์หลัก:
- `event_time_utc`
- `venue`
- `account_id`
- `symbol`
- `local_order_id`
- `venue_order_id`
- `event_type`
- `side`
- `price`
- `qty`
- `filled_qty`
- `remaining_qty`
- `status`
- `reject_reason`
- `client_tag`

### 8. `logs/execution/fill_events.parquet`

หน้าที่:
- เก็บ fills ที่เกิดขึ้นจริง

grain:
- 1 row ต่อ fill

คอลัมน์หลัก:
- `fill_time_utc`
- `venue`
- `account_id`
- `symbol`
- `local_order_id`
- `venue_order_id`
- `trade_id`
- `side`
- `fill_px`
- `fill_qty`
- `fill_notional_usd`
- `fee_usd`
- `liquidity_role`

### 9. `logs/strategy/strategy_decisions.parquet`

หน้าที่:
- เก็บว่า strategy ตัดสินใจอะไรและทำไม

grain:
- 1 row ต่อ decision event

คอลัมน์หลัก:
- `decision_time_utc`
- `symbol`
- `signal_type`
- `lighter_side`
- `hyperliquid_side`
- `raw_diff_bps_h`
- `net_edge_bps_h`
- `enter_threshold_bps_h`
- `exit_threshold_bps_h`
- `confirm_time_sec`
- `target_notional_usd`
- `clip_notional_usd`
- `decision`
- `reason_code`
- `reason_text`

### 10. `logs/risk/venue_health_snapshots.parquet`

หน้าที่:
- เก็บ venue health และข้อมูล freshness

grain:
- 1 row ต่อ venue ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `ws_lag_ms`
- `data_stale_flag`
- `seq_gap_count`
- `api_error_rate`
- `reject_rate`
- `cancel_rate`
- `venue_degraded_flag`
- `note`

## ชุดมาตรฐานสำหรับ POC เต็ม 16 ไฟล์

ไฟล์ 1-10 จากชุดขั้นต่ำ และเพิ่มดังนี้

### 11. `data/processed/trade_tape.parquet`

หน้าที่:
- เก็บ trade tape สำหรับใช้ดู short-term microstructure

grain:
- 1 row ต่อ public trade

คอลัมน์หลัก:
- `trade_time_utc`
- `venue`
- `symbol`
- `trade_id`
- `price`
- `size`
- `side_aggressor`

### 12. `data/processed/open_interest_snapshots.parquet`

หน้าที่:
- เก็บ OI และ venue stats ที่ใช้ประเมิน crowding

grain:
- 1 row ต่อ venue ต่อ symbol ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `symbol`
- `open_interest_usd`
- `open_interest_native`
- `oi_change_1h`
- `oi_change_24h`

### 13. `data/processed/margin_snapshots.parquet`

หน้าที่:
- แยกข้อมูล margin ระดับบัญชีที่ใช้สำหรับ risk engine

grain:
- 1 row ต่อ venue ต่อ account ต่อ snapshot time

คอลัมน์หลัก:
- `ts_utc`
- `venue`
- `account_id`
- `equity_usd`
- `margin_used_usd`
- `free_margin_usd`
- `maintenance_margin_usd`
- `initial_margin_usd`
- `margin_ratio`

### 14. `logs/risk/risk_events.parquet`

หน้าที่:
- เก็บ risk events และ guardrail actions

grain:
- 1 row ต่อ risk event

คอลัมน์หลัก:
- `event_time_utc`
- `scope`
- `venue`
- `symbol`
- `event_type`
- `severity`
- `metric_name`
- `metric_value`
- `threshold_value`
- `action_taken`
- `action_status`

### 15. `logs/recovery/recovery_events.parquet`

หน้าที่:
- เก็บ reconcile และ recovery flows

grain:
- 1 row ต่อ recovery event

คอลัมน์หลัก:
- `event_time_utc`
- `venue`
- `symbol`
- `recovery_type`
- `mismatch_type`
- `local_value`
- `venue_value`
- `action_taken`
- `resolved_flag`
- `resolved_time_utc`

### 16. `data/derived/normalized_funding_panel.parquet`

หน้าที่:
- เป็น table หลักสำหรับงานวิจัยและ backtest

grain:
- 1 row ต่อ canonical symbol ต่อ timestamp bucket

คอลัมน์หลัก:
- `ts_utc`
- `symbol_canonical`
- `funding_lighter_bps_h`
- `funding_hyperliquid_bps_h`
- `raw_diff_bps_h`
- `diff_direction`
- `mark_basis_bps`
- `book_spread_bps_lighter`
- `book_spread_bps_hyperliquid`
- `depth_at_target_size_lighter`
- `depth_at_target_size_hyperliquid`
- `prediction_age_sec_lighter`
- `prediction_age_sec_hyperliquid`
- `capacity_score`

## ชุดเต็มสำหรับ scale ถึง 1M USD: เพิ่มอีก 4 ไฟล์

### 17. `data/derived/prediction_error_panel.parquet`

หน้าที่:
- วัด error ระหว่าง predicted funding กับ settled funding

grain:
- 1 row ต่อ venue ต่อ symbol ต่อ settlement window

คอลัมน์หลัก:
- `venue`
- `symbol`
- `settlement_time_utc`
- `prediction_time_utc`
- `time_to_settlement_sec`
- `predicted_bps_h`
- `settled_bps_h`
- `error_bps_h`
- `abs_error_bps_h`

### 18. `data/derived/capacity_curve_by_symbol.parquet`

หน้าที่:
- เก็บ capacity curve ราย symbol

grain:
- 1 row ต่อ symbol ต่อ capital bucket

คอลัมน์หลัก:
- `symbol_canonical`
- `capital_bucket_usd`
- `expected_slippage_bps`
- `expected_market_impact_bps`
- `expected_fill_time_sec`
- `expected_hedge_lag_sec`
- `net_edge_after_impact_bps_h`
- `capacity_pass_flag`

### 19. `data/derived/capacity_curve_by_venue.parquet`

หน้าที่:
- เก็บ capacity curve ระดับ venue

grain:
- 1 row ต่อ venue ต่อ capital bucket

คอลัมน์หลัก:
- `venue`
- `capital_bucket_usd`
- `deployable_notional_usd`
- `avg_depth_usd`
- `expected_impact_bps`
- `margin_utilization_pct`
- `concentration_pct`
- `capacity_pass_flag`

### 20. `data/derived/allocation_simulations.parquet`

หน้าที่:
- เก็บผล simulation ของการกระจายทุนสำหรับพอร์ตใหญ่

grain:
- 1 row ต่อ simulation run ต่อ symbol allocation

คอลัมน์หลัก:
- `run_id`
- `run_time_utc`
- `portfolio_target_usd`
- `symbol_canonical`
- `venue_pair`
- `allocated_usd`
- `weight_pct`
- `expected_net_edge_bps_h`
- `expected_slippage_bps`
- `expected_concentration_pct`
- `expected_margin_usage_pct`

## Partition ที่แนะนำ

สำหรับไฟล์ snapshot และ event ขนาดใหญ่ ควร partition อย่างน้อยด้วย:

- `date`
- `venue`
- `symbol` สำหรับไฟล์ที่ใหญ่เป็นพิเศษ

ตัวอย่าง:

```text
data/processed/funding_snapshots/date=2026-03-12/venue=lighter/part-000.parquet
data/processed/book_snapshots/date=2026-03-12/venue=hyperliquid/part-000.parquet
logs/execution/fill_events/date=2026-03-12/venue=lighter/part-000.parquet
```

## คำแนะนำเชิงปฏิบัติ

ถ้าจะเริ่มลงมือทันที:

1. สร้างก่อน 10 ไฟล์ในชุดขั้นต่ำ
2. เมื่อ collector และ strategy log เสถียร ค่อยเพิ่มชุดมาตรฐานให้ครบ 16 ไฟล์
3. เมื่อเริ่มตอบเรื่อง capacity และ scale-up จริง ค่อยเพิ่ม 4 ไฟล์ในชุด `derived` สำหรับ `1M USD`

## สรุป

จำนวนไฟล์ที่ควรสร้างมี 3 ระดับ:

- 10 ไฟล์ สำหรับเริ่ม POC
- 16 ไฟล์ สำหรับ POC เต็ม
- 20 ไฟล์ สำหรับประเมิน scale ถึง `1M USD`

ถ้าจะให้ระบบตอบได้ทั้ง signal, execution, risk และ capacity ควรตั้งเป้าสุดท้ายไว้ที่ 20 logical files
