# แผนการเก็บข้อมูลสำหรับ POC: Lighter x Hyperliquid Funding Spread Arbitrage

## วิธีอ่านเอกสารนี้

- [x] หมายถึง ตอนนี้มี script สำหรับเก็บข้อมูลชุดนี้แล้ว
- [ ] หมายถึง ตอนนี้ยังไม่มี script สำหรับเก็บข้อมูลชุดนี้
- ถ้ามี script แล้วแต่ยังเก็บได้แค่บางส่วน จะระบุคำว่า `partial`

## เป้าหมาย

- [ ] เก็บข้อมูลให้พอสำหรับหา `entry/exit rule`
- [ ] เก็บข้อมูลให้พอสำหรับพิสูจน์ `execution realism`
- [ ] เก็บข้อมูลให้พอสำหรับประเมินว่า scale ไปถึง `1M USD` ได้หรือไม่

## Script ที่มีอยู่ตอนนี้

- [x] `src/collectors/non_live/collect_reference_data.py`
- [x] `src/collectors/non_live/collect_lighter_funding_history.py`
- [x] `src/collectors/non_live/collect_hyperliquid_funding_history.py`
- [x] `src/collectors/non_live/collect_hyperliquid_user_funding.py`
- [x] `src/collectors/non_live/collect_all_non_live.py`
- [x] `src/collectors/non_live/unit_check.py`
- [x] `src/collectors/non_live/README.md`
- [x] `src/collectors/live/collect_all_live.py`
- [x] `src/collectors/live/README.md`
- [x] `start_live_collect.ps1`

## 1. Reference Data

ข้อมูลชุดนี้ใช้สำหรับ normalize markets, mapping symbols, และตรวจ unit/spec ของแต่ละ venue

### สิ่งที่ต้องเก็บ

- [x] symbol mapping ระหว่าง Lighter และ Hyperliquid
- [x] contract spec บางส่วน
- [x] contract size / size decimals
- [x] tick size / price decimals
- [x] lot size / min order size
- [x] leverage limits
- [x] margin table / margin mode บางส่วน
- [x] public maker/taker fee จาก market metadata
- [x] open interest summary จาก public metadata
- [x] daily volume summary จาก public metadata
- [ ] fee tier ของ account จริง
- [ ] account-specific limits
- [ ] venue-specific trading config ที่ต้อง auth

### Script ที่ใช้ตอนนี้

- [x] `src/collectors/non_live/collect_reference_data.py`
- [x] `src/collectors/non_live/collect_all_non_live.py`

### เก็บไว้ที่ไหน

- [x] `data/reference/shared_markets_latest.csv`
- [x] `data/reference/shared_markets_latest.json`
- [x] `data/reference/lighter_reference_latest.json`
- [x] `data/reference/hyperliquid_reference_latest.json`
- [x] `data/raw/lighter/rest/date=YYYY-MM-DD/reference_bundle_*.json`
- [x] `data/raw/hyperliquid/rest/date=YYYY-MM-DD/reference_bundle_*.json`

### ความถี่ที่ควรเก็บ

- [x] ตอนเริ่มระบบ
- [x] refresh รายวัน
- [x] refresh เมื่อ market metadata เปลี่ยน

### ระยะเวลาที่ควรเก็บ

- [x] เก็บถาวรตลอดอายุโปรเจค

## 2. Funding Data

ข้อมูลชุดนี้ใช้สำหรับหาสัญญาณ funding spread และตรวจว่า unit ของ funding ตรงกันหรือไม่

### สิ่งที่ต้องเก็บ

- [x] Hyperliquid settled funding history
- [x] Hyperliquid current funding snapshot แบบ non-live
- [x] Hyperliquid predicted fundings raw payload
- [x] Hyperliquid user funding ledger แบบย้อนหลัง ถ้ามี address
- [x] Lighter current funding snapshot
- [ ] Lighter predicted funding snapshot
- [x] Lighter settled funding history
- [ ] Lighter user funding ledger / account funding history

### Script ที่ใช้ตอนนี้

- [x] `src/collectors/non_live/collect_reference_data.py`
  - coverage: Hyperliquid `metaAndAssetCtxs` และ `predictedFundings`, Lighter `funding-rates`
- [x] `src/collectors/non_live/collect_lighter_funding_history.py`
- [x] `src/collectors/non_live/collect_hyperliquid_funding_history.py`
- [x] `src/collectors/non_live/collect_hyperliquid_user_funding.py`
- [x] `src/collectors/non_live/collect_all_non_live.py`
- [x] `src/collectors/non_live/unit_check.py`

### เก็บไว้ที่ไหน

- [x] Hyperliquid funding history raw:
  - `data/raw/hyperliquid/rest/funding_history/date=YYYY-MM-DD/coin=..._*.json`
- [x] Hyperliquid funding history latest:
  - `data/processed/hyperliquid_funding_history_latest.csv`
  - `data/processed/hyperliquid_funding_history_latest.json`
- [x] Hyperliquid user funding raw:
  - `data/raw/hyperliquid/rest/user_funding/date=YYYY-MM-DD/user=..._*.json`
- [x] Hyperliquid user funding latest:
  - `data/processed/hyperliquid_user_funding_latest.csv`
  - `data/processed/hyperliquid_user_funding_latest.json`
- [x] Hyperliquid current/predicted funding raw snapshot:
  - `data/reference/hyperliquid_reference_latest.json`
  - `data/raw/hyperliquid/rest/date=YYYY-MM-DD/reference_bundle_*.json`
- [x] Lighter funding history raw:
  - `data/raw/lighter/rest/fundings/date=YYYY-MM-DD/market_id=..._*.json`
- [x] Lighter funding history latest:
  - `data/processed/lighter_funding_history_latest.csv`
  - `data/processed/lighter_funding_history_latest.json`
- [x] Lighter current funding raw snapshot:
  - `data/reference/lighter_reference_latest.json`
  - `data/raw/lighter/rest/date=YYYY-MM-DD/reference_bundle_*.json`
- [x] Unit check reports:
  - `data/reports/funding_unit_check_latest.csv`
  - `data/reports/contract_size_check_latest.csv`
  - `data/reports/unit_check_report_latest.md`
  - `data/reports/unit_check_report_latest.json`

### ความถี่ที่ควรเก็บ

- [x] Hyperliquid funding history: run เป็นรอบ เช่น รายวัน
- [x] Hyperliquid user funding: run เป็นรอบเมื่อมี address
- [x] Lighter funding history: run เป็นรอบ เช่น รายวัน
- [x] partial: current/predicted funding แบบใช้งานจริงมี live collector แล้ว
  - path:
    - `data/raw/lighter/ws/market_stats/...`
    - `data/raw/hyperliquid/rest/live_info/...`
    - `data/processed/live_funding_snapshots_latest.csv`

### ระยะเวลาที่ควรเก็บ

- [x] ขั้นต่ำสำหรับ POC แรก: 14-30 วัน
- [x] แนะนำสำหรับงานวิจัย: 30 วัน
- [ ] ถ้าจะประเมิน scale ถึง `1M USD` ควรเก็บ 60-90 วัน

## 3. Price / BBO / Order Book Depth

ข้อมูลชุดนี้ใช้วัด execution feasibility, slippage, และ capacity

### สิ่งที่ต้องเก็บ

- [x] partial: mark price แบบต่อเนื่อง
- [x] partial: index price แบบต่อเนื่อง
- [x] partial: mid price แบบต่อเนื่อง
- [x] partial: best bid
- [x] partial: best ask
- [x] partial: top-of-book spread
- [x] partial: order book depth หลายระดับ
- [x] partial: depth buckets ตาม notional เช่น 10k / 25k / 50k / 100k / 250k USD
- [ ] 500k / 1M USD aggregated capacity view

### Script ที่ใช้ตอนนี้

- [x] `collect_reference_data.py` มี metadata บางส่วน เช่น last trade price, open interest, daily volume
- [x] partial: `src/collectors/live/collect_all_live.py`
- [x] partial: `start_live_collect.ps1`

### เก็บไว้ที่ไหน

- [x] `data/raw/lighter/ws/orderbook/...`
- [x] `data/raw/hyperliquid/ws/l2_book/...`
- [x] `data/processed/live_book_snapshots_latest.csv`
- [x] `data/processed/live/book_snapshots/...jsonl`
- [ ] `data/processed/book_snapshots.parquet`

### ความถี่ที่ควรเก็บ

- [x] partial: live collector ตอนนี้ flush ทุก 1-5 วินาทีได้

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 14 วัน
- [ ] แนะนำ 30 วัน
- [ ] สำหรับ `1M USD` ควรเก็บ 60-90 วัน

## 4. Public Trades Tape / Market Microstructure

### สิ่งที่ต้องเก็บ

- [ ] public trades
- [ ] trade price
- [ ] trade size
- [ ] aggressor side ถ้ามี

### Script ที่ใช้ตอนนี้

- [ ] ยังไม่มี

### เก็บไว้ที่ไหน

- [ ] path ที่ควรใช้:
  - `data/raw/lighter/ws/trades/...`
  - `data/raw/hyperliquid/ws/trades/...`
  - `data/processed/trade_tape.parquet`

### ความถี่ที่ควรเก็บ

- [ ] event-driven

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 14 วัน
- [ ] แนะนำ 30 วัน
- [ ] สำหรับ `1M USD` ควรเก็บ 60-90 วัน

## 5. Open Interest / Venue Stats

### สิ่งที่ต้องเก็บ

- [x] open interest summary บางส่วนจาก reference data
- [ ] open interest snapshots ต่อเนื่อง
- [ ] venue stats ต่อเนื่อง

### Script ที่ใช้ตอนนี้

- [x] `collect_reference_data.py` เก็บ OI summary แบบ snapshot non-live บางส่วน
- [ ] ยังไม่มี OI collector แบบ time series

### เก็บไว้ที่ไหน

- [x] `data/reference/lighter_reference_latest.json`
- [x] `data/reference/hyperliquid_reference_latest.json`
- [ ] path ที่ควรใช้สำหรับ time series:
  - `data/processed/open_interest_snapshots.parquet`

### ความถี่ที่ควรเก็บ

- [ ] ทุก 10-60 วินาที

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 14 วัน
- [ ] แนะนำ 30 วัน
- [ ] สำหรับ `1M USD` ควรเก็บ 60-90 วัน

## 6. Account / Position / Execution Data

ข้อมูลชุดนี้ใช้ตอบว่า signal ที่ดูดี "ทำได้จริงไหม"

### สิ่งที่ต้องเก็บ

- [ ] account balance ต่อ venue
- [ ] collateral / free collateral
- [ ] margin usage
- [ ] positions ต่อ symbol
- [ ] leverage ต่อ symbol
- [ ] liquidation price / buffer
- [ ] order submit / ack / amend / cancel / reject
- [ ] fill events
- [ ] filled qty / remaining qty / avg fill price / fee จริง

### Script ที่ใช้ตอนนี้

- [x] `collect_hyperliquid_user_funding.py` เก็บได้บางส่วนของ funding ledger ระดับ account
- [ ] ยังไม่มี script สำหรับ balances / positions / orders / fills

### เก็บไว้ที่ไหน

- [x] `data/processed/hyperliquid_user_funding_latest.csv`
- [x] `data/processed/hyperliquid_user_funding_latest.json`
- [ ] path ที่ควรใช้เมื่อมี collector:
  - `data/processed/balance_snapshots.parquet`
  - `data/processed/position_snapshots.parquet`
  - `data/processed/margin_snapshots.parquet`
  - `logs/execution/order_events.parquet`
  - `logs/execution/fill_events.parquet`

### ความถี่ที่ควรเก็บ

- [ ] orders / fills: event-driven
- [ ] balances / positions / margin: ทุก 5-30 วินาที หรือเมื่อมี change event
- [ ] reconciliation snapshot: ทุก 1-5 นาที

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 30 วัน
- [ ] แนะนำ 90 วัน
- [ ] ถ้าเริ่ม live trial แล้ว: 1 ปีหรือถาวร

## 7. Latency Metrics

### สิ่งที่ต้องเก็บ

- [ ] signal -> send latency
- [ ] send -> ack latency
- [ ] ack -> first fill latency
- [ ] first leg -> second leg hedge latency
- [ ] fill complete latency

### Script ที่ใช้ตอนนี้

- [ ] ยังไม่มี

### เก็บไว้ที่ไหน

- [ ] path ที่ควรใช้:
  - `logs/execution/order_events.parquet`
  - `logs/execution/fill_events.parquet`
  - `data/derived/execution_latency_panel.parquet`

### ความถี่ที่ควรเก็บ

- [ ] event-driven ทุกครั้งที่มี order lifecycle

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 30 วัน
- [ ] แนะนำ 90 วัน

## 8. Strategy Decision Logs

### สิ่งที่ต้องเก็บ

- [ ] signal time
- [ ] symbol
- [ ] venue pair
- [ ] funding spread ตอนเกิดสัญญาณ
- [ ] net edge หลังหัก cost model
- [ ] threshold ที่ใช้
- [ ] side ที่จะเข้าแต่ละ venue
- [ ] target size / clip size
- [ ] execution mode
- [ ] เหตุผลที่ enter / skip / reduce / exit

### Script ที่ใช้ตอนนี้

- [ ] ยังไม่มี

### เก็บไว้ที่ไหน

- [ ] path ที่ควรใช้:
  - `logs/strategy/strategy_decisions.parquet`

### ความถี่ที่ควรเก็บ

- [ ] event-driven ทุกครั้งที่มี decision

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 90 วัน
- [ ] แนะนำเก็บถาวร

## 9. Risk / Venue Health / Recovery Logs

### สิ่งที่ต้องเก็บ

- [ ] stale data flag
- [ ] websocket lag
- [ ] dropped message / sequence gap
- [ ] API error rate
- [ ] cancel / reject spike
- [ ] venue degraded flag
- [ ] hedge imbalance
- [ ] exposure drift
- [ ] venue concentration
- [ ] symbol concentration
- [ ] liquidation risk flag
- [ ] ADL risk flag
- [ ] recovery trigger event
- [ ] reconcile mismatch event
- [ ] cancel-all / halt / drain event

### Script ที่ใช้ตอนนี้

- [ ] ยังไม่มี

### เก็บไว้ที่ไหน

- [ ] path ที่ควรใช้:
  - `logs/risk/venue_health_snapshots.parquet`
  - `logs/risk/risk_events.parquet`
  - `logs/recovery/recovery_events.parquet`

### ความถี่ที่ควรเก็บ

- [ ] health metrics: ทุก 1-5 วินาที
- [ ] risk snapshots: ทุก 5-30 วินาที
- [ ] recovery / incident logs: event-driven

### ระยะเวลาที่ควรเก็บ

- [ ] ขั้นต่ำ 90 วัน
- [ ] แนะนำเก็บถาวร

## 10. Derived / Research Data

### สิ่งที่ต้องมี

- [ ] normalized funding panel
- [ ] predicted vs settled funding error table
- [ ] book spread panel
- [ ] slippage model inputs
- [ ] market impact estimates
- [ ] capacity score ต่อ symbol
- [ ] capacity curve ต่อ venue
- [ ] capacity curve ต่อ symbol
- [ ] threshold sweep results
- [ ] allocation simulation results สำหรับพอร์ต `1M USD`

### Script ที่ใช้ตอนนี้

- [ ] ยังไม่มี derived pipeline

### เก็บไว้ที่ไหน

- [ ] path ที่ควรใช้:
  - `data/derived/normalized_funding_panel.parquet`
  - `data/derived/prediction_error_panel.parquet`
  - `data/derived/capacity_curve_by_symbol.parquet`
  - `data/derived/capacity_curve_by_venue.parquet`
  - `data/derived/allocation_simulations.parquet`
  - `reports/threshold_search.csv`

### ความถี่ที่ควรเก็บ

- [ ] batch ทุกชั่วโมงหรือทุกวัน
- [ ] rerun ทุกครั้งที่มี experiment สำคัญ

### ระยะเวลาที่ควรเก็บ

- [ ] เก็บอย่างน้อยจนจบ POC
- [ ] ผล experiment สำคัญควรเก็บถาวร

## 11. สรุปสถานะตอนนี้

### มี script พร้อมใช้แล้ว

- [x] Reference data พื้นฐานของ Lighter และ Hyperliquid
- [x] Shared markets mapping
- [x] Lighter funding history
- [x] Hyperliquid funding history
- [x] Hyperliquid user funding ledger
- [x] Launcher รวมตัวเดียวสำหรับ non-live collectors
- [x] partial: live collector สำหรับ funding / mark / index / mid / BBO / depth
- [x] background launcher แบบคำสั่งเดียวสำหรับ live collection

### มีแค่บางส่วน / partial

- [x] Hyperliquid current funding และ predicted funding
  - ตอนนี้เก็บผ่าน reference snapshot แบบ non-live
  - และตอนนี้มี live collector แบบ partial แล้ว
- [x] Open interest / daily volume / market metadata
  - เก็บได้จาก reference bundle
  - ยังไม่ใช่ time series
- [x] mark / index / best bid / best ask / top spread / depth summary
  - ตอนนี้มี live collector แบบ partial แล้ว
  - แต่ยังไม่มี trade tape และ Parquet pipeline

### ยังไม่มี script

- [x] Lighter funding collector
- [x] Unit check report สำหรับ funding unit และ contract size unit
- [x] partial: live BBO / depth collectors
- [ ] public trades tape collectors
- [ ] balances / positions / margin collectors
- [ ] orders / fills collectors
- [ ] strategy decision logger
- [ ] risk / recovery loggers
- [ ] derived research pipelines

## 12. ความถี่และระยะเวลาแนะนำแบบสรุป

- [x] Reference data: รายวัน / เมื่อมี change และเก็บถาวร
- [x] Hyperliquid funding history: รันเป็น batch รายวันได้ และควรเก็บอย่างน้อย 30 วัน
- [x] Lighter funding history: รันเป็น batch รายวันได้ และควรเก็บอย่างน้อย 30 วัน
- [ ] Funding / BBO / Mark / Index แบบ live: ควรเก็บทุก 1-5 วินาที อย่างน้อย 14 วัน
- [ ] Depth / market microstructure: ควรเก็บทุก 1-5 วินาที อย่างน้อย 30 วัน
- [ ] Orders / fills / positions / margin: event-driven + snapshots อย่างน้อย 30-90 วัน
- [ ] Strategy / risk / recovery logs: ควรเก็บอย่างน้อย 90 วัน
- [ ] ถ้าจะประเมิน `1M USD`: market + depth data ควรมี 60-90 วัน

## 13. คำแนะนำเชิงปฏิบัติ

- [x] เริ่มจาก `src/collectors/non_live/collect_all_non_live.py` ก่อน
- [x] ตรวจ output ใน `data/reference/` และ `data/processed/`
- [ ] งานถัดไปที่ควรทำคือขยาย live collectors ให้ครอบคลุม trade tape, positions, orders, fills และ risk logs
- [ ] หลังจากนั้นค่อยต่อด้วย positions / orders / fills / risk logs
