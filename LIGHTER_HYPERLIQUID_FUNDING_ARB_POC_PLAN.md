# แผน POC: Funding Spread Arbitrage ระหว่าง Lighter และ Hyperliquid

## เป้าหมาย

- [ ] สร้าง POC เพื่อหา `entry rule` ที่ใช้งานได้จริงสำหรับการทำ cross-exchange funding-rate arbitrage ระหว่าง Lighter และ Hyperliquid
- [ ] นิยามให้ชัดว่ากฎที่ต้องหาไม่ใช่แค่ `spread > X`
- [ ] ใช้เป้าหมายจริงเป็น `เข้าเมื่อ expected net edge > 0 หลังหัก fees, slippage, latency และ legging risk`
- [ ] ออกแบบ POC ให้ตอบได้ว่าระบบสามารถ scale รองรับเงินรวมอย่างน้อย `1M USD` ได้หรือไม่
- [ ] พิสูจน์ว่าการ deploy เงินระดับ `1M USD` ยังรักษา hedge quality, slippage budget และ risk limits ได้

## คำถามหลักที่ POC ต้องตอบ

- [ ] มี symbol ไหนบ้างที่เทรดได้ทั้งสอง venue และมี liquidity พอ
- [ ] funding spread ระดับไหนที่ “เทรดได้จริง” หลังหักต้นทุน
- [ ] spread ต้องค้างอยู่นานแค่ไหนก่อนเข้า
- [ ] ควรออกด้วยกฎแบบไหน
- [ ] ใช้ threshold เดียวทั้งตลาดได้หรือไม่ หรือควรแยกตาม symbol / liquidity bucket
- [ ] capacity จริงของแต่ละ symbol และแต่ละ venue รองรับทุนรวม `1M USD` ได้แค่ไหน
- [ ] ต้องกระจายทุน `1M USD` อย่างไรระหว่าง symbols และ venues จึงไม่กด market impact จน edge หาย
- [ ] ถ้าจะ scale ไปถึง `1M USD` ต้องใช้ execution mode, clip size และ capital buffer แบบไหน

## ขอบเขตของ POC

- [ ] โฟกัสที่ market data collection
- [ ] โฟกัสที่ funding spread normalization
- [ ] โฟกัสที่ cost-aware backtesting
- [ ] โฟกัสที่ threshold search
- [ ] โฟกัสที่ shadow mode validation
- [ ] ยังไม่เริ่มจาก production execution เต็มรูปแบบ
- [ ] ยังไม่เริ่มจากการลงเงินก้อนใหญ่
- [ ] ยังไม่เริ่มจาก portfolio optimization ที่ซับซ้อน

## เกณฑ์ความสำเร็จ

- [ ] ได้ symbol universe ที่ตรงกันระหว่างสอง venue
- [ ] ได้ dataset ที่เชื่อถือได้สำหรับ funding, price และ liquidity
- [ ] ได้ cost model ที่สะท้อน execution จริง
- [ ] ได้ entry/exit rule ที่ผ่าน out-of-sample test
- [ ] ได้รายงานจาก shadow mode ว่ากลยุทธ์ execute ได้จริง
- [ ] ได้ capacity model ที่บอกได้ว่าทุนระดับ `1M USD` deploy ได้จริงหรือไม่ได้จริง
- [ ] ได้ allocation framework สำหรับกระจายเงิน `1M USD` โดยไม่เกิน slippage และ concentration budget
- [ ] ได้ rollout plan สำหรับขยายทุนจากขนาดเล็กไปถึง `1M USD`

## สมมติฐานตั้งต้น

- [ ] ข้อมูล predicted/current funding ก่อน settlement สำคัญกว่าการดู settled funding อย่างเดียว
- [ ] execution cost จะเป็นเหตุผลหลักที่ทำให้ rule แบบ `spread > X` ใช้งานจริงไม่ได้
- [ ] threshold ที่ดีที่สุดน่าจะต่างกันตาม symbol และ liquidity bucket
- [ ] historical settled funding อย่างเดียวไม่พอสำหรับ reconstruct สัญญาณตอนที่ bot ตัดสินใจเข้า

## Phase 0: ตรวจสอบ Venue และ Market

### เป้าหมาย

- [ ] ยืนยันว่าแต่ละ venue ดึงข้อมูลอะไรได้บ้าง
- [ ] สร้าง market map ที่ตรงกันระหว่าง Lighter และ Hyperliquid
- [ ] ตัดตลาดที่คุณภาพต่ำหรือเทรดไม่ได้จริงออกตั้งแต่ต้น

### งานที่ต้องทำ

- [ ] list perpetual markets ทั้งหมดของ Lighter
- [ ] list perpetual markets ทั้งหมดของ Hyperliquid
- [ ] map shared symbols ระหว่างสอง venue
- [ ] บันทึกข้อมูลต่อ symbol:
- [ ] `symbol name`
- [ ] `contract size`
- [ ] `quote currency`
- [ ] `tick size`
- [ ] `lot size`
- [ ] `min order size`
- [ ] `leverage limits`
- [ ] `margin mode constraints`
- [ ] `average top-of-book depth`
- [ ] `depth within 5 / 10 / 20 bps`
- [ ] `daily traded volume`
- [ ] `open interest / oi cap` ถ้ามี
- [ ] `API / order rate limits`
- [ ] mark symbol ที่ควร exclude:
- [ ] liquidity ต่ำมาก
- [ ] funding data ไม่ครบ
- [ ] market metadata ไม่เสถียร
- [ ] symbol mapping ไม่ตรงกัน
- [ ] capacity ต่ำเกินไปสำหรับการ scale

### ผลลัพธ์ที่ต้องได้

- [ ] `data/reference/shared_markets.csv`

## Phase 1: เก็บ Live และ Historical Data

### ทำไม phase นี้สำคัญ

- [ ] ต้องมีสัญญาณที่ระบบ “เห็นก่อนเข้าเทรด” ไม่ใช่ดูแค่ settled funding หลังจบเหตุการณ์

### ข้อมูลที่ต้องเก็บ

- [ ] timestamp
- [ ] symbol
- [ ] predicted funding rate หรือ current funding rate
- [ ] settled funding rate
- [ ] mark price
- [ ] index price
- [ ] best bid / best ask
- [ ] top-of-book spread
- [ ] order book depth หลายระดับขนาด
- [ ] effective depth สำหรับขนาด order หลาย bucket เช่น `10k / 25k / 50k / 100k USD`
- [ ] last trade price ถ้ามี
- [ ] open interest ถ้ามี
- [ ] realized slippage จาก paper execution หรือ live trial
- [ ] fill latency
- [ ] partial-fill ratio

### ข้อกำหนดของ collector

- [ ] snapshot ทุก 1-5 วินาที
- [ ] เก็บเป็น Parquet แยกตามวันและ venue
- [ ] normalize timestamps เป็น UTC
- [ ] เก็บ raw data ก่อนแปลงเสมอ
- [ ] รองรับ retry และ rate-limit handling
- [ ] มี gap detection และ alerting

### ระยะเวลาเก็บขั้นต่ำ

- [ ] เก็บอย่างน้อย 2 สัปดาห์
- [ ] เป้าหมายที่ดีกว่าคือ 4 สัปดาห์

### ผลลัพธ์ที่ต้องได้

- [ ] `data/raw/lighter/...`
- [ ] `data/raw/hyperliquid/...`
- [ ] `data/processed/funding_snapshots.parquet`
- [ ] `data/processed/book_snapshots.parquet`

## Phase 2: Data Normalization

### เป้าหมาย

- [ ] ทำให้ funding ของทั้งสอง venue เปรียบเทียบกันได้
- [ ] สร้าง funding spread series ที่เทียบกันได้ต่อ symbol

### กติกาการ normalize

- [ ] แปลง funding ทุกค่าเป็น hourly bps
- [ ] ใช้ sign convention เดียวกันทั้งระบบ
- [ ] normalize symbol names
- [ ] align timestamps ไปที่ bucket คงที่ เช่น 1 วินาทีหรือ 5 วินาที
- [ ] แยกประเภทข้อมูลให้ชัด:
- [ ] predicted funding
- [ ] current funding
- [ ] settled funding

### Derived fields ที่ต้องมี

- [ ] `funding_lighter_bps_h`
- [ ] `funding_hyperliquid_bps_h`
- [ ] `raw_diff_bps_h`
- [ ] `diff_direction`
- [ ] `mark_basis_bps`
- [ ] `book_spread_bps`
- [ ] `depth_at_target_size`
- [ ] `depth_at_10k_usd`
- [ ] `depth_at_25k_usd`
- [ ] `depth_at_50k_usd`
- [ ] `depth_at_100k_usd`
- [ ] `prediction_age_sec`
- [ ] `estimated_market_impact_bps`
- [ ] `capacity_score`

### ผลลัพธ์ที่ต้องได้

- [ ] `data/processed/normalized_funding_panel.parquet`

## Phase 3: Cost Model

### เป้าหมาย

- [ ] เปลี่ยน `raw spread` ให้เป็น `tradeable spread`

### ต้นทุนที่ต้องรวม

- [ ] entry fees ทั้งสอง venue
- [ ] exit fees ทั้งสอง venue
- [ ] expected slippage ตอนเข้า
- [ ] expected slippage ตอนออก
- [ ] latency buffer
- [ ] legging risk buffer
- [ ] inventory risk buffer
- [ ] market impact ตามขนาด order
- [ ] slippage convexity เมื่อ scale size ขึ้น
- [ ] capital carry cost / idle capital cost ถ้าต้อง pre-fund สอง venue

### สูตรหลัก

- [ ] ใช้สูตรประมาณการแบบ:
- [ ] `net_edge_1h = abs(raw_diff_bps_h) - fee_in_bps - fee_out_bps / expected_hold_h - slip_in_bps - slip_out_bps / expected_hold_h - latency_buffer_bps - risk_buffer_bps`

### scenario ที่ต้องลอง

- [ ] maker / maker
- [ ] maker / taker
- [ ] taker / maker
- [ ] taker / taker
- [ ] small clip execution
- [ ] medium clip execution
- [ ] large clip execution ใกล้ระดับที่ใช้กับทุนรวม `1M USD`

### ผลลัพธ์ที่ต้องได้

- [ ] `notebooks/cost_model.ipynb`
- [ ] `src/costs/model.py`

## Phase 4: ออกแบบ Backtest

### backtest ที่ต้องมี

- [ ] Settlement backtest
- [ ] ถือครบ 1 funding window เพื่อวัด pure funding capture
- [ ] Dynamic backtest
- [ ] เข้าเมื่อ signal ผ่าน และออกเมื่อ spread หด, flip sign หรือครบ max hold

### entry rule candidates

- [ ] `enter_threshold_bps_h`
- [ ] `confirm_time_sec`
- [ ] `min_depth_usd`
- [ ] `max_prediction_age_sec`
- [ ] `allowed_execution_mode`

### exit rule candidates

- [ ] `exit_threshold_bps_h`
- [ ] sign flip
- [ ] max hold time
- [ ] stop เมื่อ fill แย่หรือ hedge leg อีกฝั่งไม่ครบ

### parameter grid เริ่มต้น

- [ ] `enter_threshold_bps_h`: 0.5, 1, 2, 3, 5, 8
- [ ] `confirm_time_sec`: 15, 30, 60, 180
- [ ] `exit_threshold_bps_h`: 0, 0.25, 0.5, 1
- [ ] `max_hold_h`: 1, 2, 4, 8
- [ ] `capital_bucket_usd`: 10k, 25k, 50k, 100k, 250k, 500k, 1M

### execution realism ที่ต้องจำลอง

- [ ] order book depth limits
- [ ] partial fills
- [ ] entry delay
- [ ] second-leg delay
- [ ] failed hedge leg
- [ ] symbol-specific sizing constraints
- [ ] market impact ที่โตตามขนาด order
- [ ] capital fragmentation ระหว่างหลาย symbol
- [ ] venue balance exhaustion

### metrics ที่ต้องวัด

- [ ] mean net edge
- [ ] hit rate
- [ ] average hold time
- [ ] max adverse move ก่อน hedge ครบ
- [ ] slippage เทียบกับที่คาด
- [ ] realized funding capture
- [ ] fee-to-alpha ratio
- [ ] PnL ราย symbol
- [ ] PnL ราย liquidity bucket
- [ ] capacity ต่อ symbol
- [ ] capacity ต่อ venue
- [ ] deployable capital ก่อนชน slippage budget
- [ ] expected return decay เมื่อ scale จาก `10k` ไป `1M USD`
- [ ] concentration ratio ของทุนต่อ symbol / venue

### ผลลัพธ์ที่ต้องได้

- [ ] `notebooks/backtest_threshold_search.ipynb`
- [ ] `src/backtest/engine.py`
- [ ] `reports/threshold_search.csv`

## Phase 5: เลือก Threshold

### หลักการ

- [ ] อย่าฝืนใช้ threshold เดียวกับทุกตลาด ถ้าข้อมูลไม่รองรับ

### วิธีแบ่งกลุ่มที่ควรลอง

- [ ] majors
- [ ] mid-liquidity alts
- [ ] low-liquidity tail
- [ ] แบ่งตาม average depth
- [ ] แบ่งตาม average book spread
- [ ] แบ่งตาม funding prediction error

### output ที่ต้องมี

- [ ] global benchmark threshold
- [ ] threshold ราย symbol
- [ ] threshold ราย liquidity bucket
- [ ] capacity ceiling ราย symbol
- [ ] capacity ceiling ราย venue
- [ ] recommended capital allocation mix สำหรับทุนรวม `1M USD`

### ผลลัพธ์ที่ต้องได้

- [ ] `reports/entry_thresholds_by_symbol.csv`
- [ ] `reports/entry_thresholds_by_bucket.csv`

## Phase 6: ตรวจสอบคุณภาพของ Funding Prediction

### เป้าหมาย

- [ ] วัดว่าค่า predicted funding ก่อน settlement เบี่ยงจาก settled funding จริงแค่ไหน

### งานที่ต้องทำ

- [ ] เปรียบเทียบ predicted funding snapshots กับ settled funding ภายหลัง
- [ ] วัด error แยกตาม:
- [ ] venue
- [ ] symbol
- [ ] time-to-settlement
- [ ] volatility regime
- [ ] สร้าง confidence penalty ให้ symbol ที่ prediction noisy

### output สำคัญ

- [ ] รายชื่อ symbol ที่ predicted funding เสถียร
- [ ] รายชื่อ symbol ที่ prediction drift หนัก

### ผลลัพธ์ที่ต้องได้

- [ ] `notebooks/prediction_error_analysis.ipynb`
- [ ] `reports/prediction_quality.csv`

## Phase 7: Shadow Mode

### เป้าหมาย

- [ ] รันกลยุทธ์แบบไม่ส่ง order จริง เพื่อพิสูจน์ว่า signal execute ได้จริง

### สิ่งที่ต้อง log

- [ ] signal time
- [ ] symbol
- [ ] side ที่ควรทำในแต่ละ venue
- [ ] predicted edge ตอนเกิดสัญญาณ
- [ ] available depth
- [ ] expected slippage
- [ ] simulated entry price
- [ ] simulated exit price
- [ ] simulated funding capture
- [ ] simulated net PnL
- [ ] missed trades และเหตุผล

### ระยะเวลาขั้นต่ำ

- [ ] รันอย่างน้อย 1-2 สัปดาห์

### acceptance checks

- [ ] มีโอกาสเทรดที่ fill ได้จริงพอ
- [ ] net edge ยังเป็นบวกหลังใส่ execution realism
- [ ] ผล backtest กับ shadow mode ไม่ต่างกันมากเกินไป

### ผลลัพธ์ที่ต้องได้

- [ ] `reports/shadow_mode_summary.md`

## Phase 8: Small Live Trial

### เงื่อนไขก่อนเริ่ม

- [ ] data collector เสถียร
- [ ] backtest และ shadow mode ให้ผลใกล้กัน
- [ ] kill switch ใช้งานได้
- [ ] กำหนด exposure limits แล้ว

### controls ที่ต้องมี

- [ ] จำกัด notional ต่อ symbol
- [ ] จำกัด total exposure
- [ ] จำกัด exposure ต่อ venue
- [ ] kill switch เมื่อ second leg fail
- [ ] kill switch เมื่อ funding data stale
- [ ] kill switch เมื่อ prediction drift ผิดปกติ

### ผลลัพธ์ที่ต้องได้

- [ ] `reports/live_trial_log.csv`

## Phase 9: Capacity และ Scale-Up สู่ 1M USD

### เป้าหมาย

- [ ] พิสูจน์ว่าระบบสามารถรองรับทุนรวมอย่างน้อย `1M USD` ได้ในเชิง execution และ risk
- [ ] หา capital allocation plan ที่ deploy ได้จริงโดยไม่ทำให้ net edge เสื่อมจนใช้ไม่ได้
- [ ] สร้างเกณฑ์ go / no-go สำหรับการขยายทุนถึง `1M USD`

### งานที่ต้องทำ

- [ ] สร้าง `capacity curve` ต่อ symbol และต่อ venue
- [ ] วัดว่าเมื่อเพิ่ม order size แล้ว slippage และ market impact โตแบบไหน
- [ ] หา `max deployable notional` ภายใต้ slippage budget ที่ยอมรับได้
- [ ] หา `max deployable notional` ภายใต้ hedge-lag budget ที่ยอมรับได้
- [ ] สร้าง allocation model สำหรับทุนรวม `1M USD`
- [ ] จำกัด concentration ต่อ symbol
- [ ] จำกัด concentration ต่อ venue
- [ ] กำหนด buffer เงินสด / margin buffer ที่ต้อง reserve ไว้เสมอ
- [ ] กำหนด minimum number of symbols ที่ต้องใช้ถ้าจะ deploy ถึง `1M USD`
- [ ] ทดสอบว่าพอร์ตยังปลอดภัยเมื่อ symbol ขนาดใหญ่บางตัวหายไปชั่วคราว
- [ ] ทดสอบ stress scenario:
- [ ] book บางลงกะทันหัน
- [ ] funding prediction flip เร็ว
- [ ] one-leg fill แต่ hedge leg ช้า
- [ ] venue หนึ่ง degrade หรือหยุดรับ order

### output ที่ต้องมี

- [ ] `capacity_curve_by_symbol.csv`
- [ ] `capacity_curve_by_venue.csv`
- [ ] `capital_allocation_1m_plan.csv`
- [ ] `scale_up_go_no_go.md`

### เกณฑ์ผ่านขั้นต่ำสำหรับ 1M USD

- [ ] สามารถกระจายทุนรวม `1M USD` ได้โดยไม่เกิน concentration limit ที่กำหนด
- [ ] expected net edge หลังหัก impact ยังเป็นบวกในระดับทุนเป้าหมาย
- [ ] ไม่มี venue ใด venue หนึ่งแบกสัดส่วนเสี่ยงเกินเกณฑ์
- [ ] hedge lag และ partial-fill risk ยังอยู่ใน budget
- [ ] margin buffer หลัง deploy ยังไม่บางเกินไปภายใต้ stress scenario

## POC เพิ่มเติมจากมุมสถาปัตยกรรมระบบ

### State Management / Snapshot

- [ ] ingest state จากทั้งสอง venue เข้า internal model กลาง
- [ ] merge market state, funding state, instrument metadata, position state และ order state
- [ ] สร้าง point-in-time snapshots ที่ replay ได้
- [ ] ตรวจสอบ freshness, ordering และ idempotency ของ snapshot

### Portfolio Snapshot Builder

- [ ] สร้าง snapshot ระดับพอร์ตข้ามทุก symbol และทุก venue
- [ ] รวม exposure, net carry, hedge ratio, margin usage และ venue concentration
- [ ] ทำให้ strategy และ risk ใช้ snapshot version เดียวกัน
- [ ] รวม capital utilization และ available deployable capital

### Risk Snapshot Builder

- [ ] สร้าง risk snapshot ทั้งระดับ symbol และระดับพอร์ต
- [ ] รวม liquidation buffer, leverage, free margin, concentration และ stale-data flags
- [ ] พิสูจน์ว่า recompute ได้เร็วพอสำหรับ runtime checks

### Portfolio Management / Rebalancer

- [ ] ตรวจ portfolio drift เทียบกับ target hedge allocation
- [ ] ตัดสินใจว่าเมื่อไรควร rebalance, reduce หรือ isolate venue
- [ ] ทดสอบ buffer allocation และ capital movement logic
- [ ] ทดสอบ allocation engine สำหรับทุนรวม `1M USD`

### Portfolio Divergence / Hedge Imbalance Monitor

- [ ] ตรวจ broken hedge ratio
- [ ] ตรวจ one side โตเร็วกว่าฝั่งตรงข้าม
- [ ] ตรวจ fill lag พร้อม market move
- [ ] นิยาม trigger สำหรับ rebalance หรือ unwind

### Portfolio Margin / Leverage Monitor

- [ ] monitor margin usage ต่อ venue
- [ ] monitor free collateral และ usable buying power
- [ ] detect leverage ที่สูงเกินไปหลัง fill หรือ price move
- [ ] นิยาม reduce-only หรือ freeze conditions

### Liquidation / ADL Risk Monitor

- [ ] ประเมิน liquidation buffer ของทั้งสอง venue
- [ ] track danger zone ภายใต้ stress scenarios
- [ ] monitor ADL / forced-deleveraging risk ถ้ามีข้อมูล
- [ ] นิยาม hard-stop สำหรับ emergency unwind

### Venue Health / Execution Safety

- [ ] detect stale data, websocket lag และ slow acknowledgements
- [ ] detect cancel/reject spike และ venue degradation
- [ ] นิยาม logic สำหรับ isolate venue ที่ไม่ปลอดภัย
- [ ] พิสูจน์ว่าระบบหยุดแบบปลอดภัยหรือทำ degraded mode ได้

### Guardrail / Classifier / Kill-Switch

- [ ] classify incident ตามระดับความรุนแรง
- [ ] นิยาม action แบบ freeze, reduce, unwind และ emergency stop
- [ ] แยก kill switch ระดับ symbol กับระดับพอร์ต
- [ ] พิสูจน์ว่า isolate bad venue ได้โดยไม่ทำให้ state พัง

### Symbol Worker Runtime

- [ ] นิยาม runtime loop แยกต่อ symbol
- [ ] รวม pre-trade checks, entry decision, hold monitoring และ pre-exit checks
- [ ] พิสูจน์ว่า symbol workers ไม่แย่ง capital กันผิดพลาด

### Candidate Ranking / Allocation Hint

- [ ] rank symbol ตาม net carry, quality, liquidity และ venue reliability
- [ ] แปลง ranking เป็น target capital allocation hints
- [ ] ทดสอบว่า ranking ไม่ oscillate แรงเกินไปเมื่อ live update เข้ามา
- [ ] สร้างกติกา cap ต่อ symbol สำหรับพอร์ตขนาด `1M USD`

### Pre-Trade Check

- [ ] ตรวจว่า funding edge ยัง valid ตอนส่ง order
- [ ] ตรวจว่า depth พอทั้งสอง venue
- [ ] ตรวจ prediction freshness, margin availability และ venue health
- [ ] reject signal ที่ไม่ผ่าน final safety checks

### Order Management Lifecycle

- [ ] นิยาม target size, clip size, venue side และ execution mode
- [ ] ทดสอบ send, amend, cancel และ retry flow
- [ ] track venue order id และ local order id ให้ตรงกัน

### Ack / Fill / Timeout Monitor

- [ ] detect missing ack, partial fill, full fill, reject และ timeout
- [ ] วัด hedge lag ระหว่าง first leg และ second leg
- [ ] นิยาม timeout และ retry policy ต่อ venue

### Order State Update

- [ ] sync local order state กับ venue state อย่างสม่ำเสมอ
- [ ] track filled qty, remaining qty, avg fill price และ last update time
- [ ] พิสูจน์ว่า survive reconnect และ replay ได้

### Holding Position Monitoring

- [ ] monitor funding decay หลังเข้า position
- [ ] monitor spread convergence หรือ divergence
- [ ] ตรวจว่า original trade thesis ยัง valid หรือไม่
- [ ] trigger reduce, rebalance หรือ exit ได้ตรงเวลา

### Reconciler / Recovery

- [ ] compare local state กับ venue truth สำหรับ positions, orders และ balances
- [ ] detect orphan fills, missing cancels และ stale local state
- [ ] นิยาม resync, refetch, cancel-all และ rebuild-state flows

### Position Sync Checker

- [ ] รัน position reconciliation เป็นรอบ ๆ กับแต่ละ venue
- [ ] detect silent drift จาก missing events หรือ partial fills
- [ ] นิยาม threshold สำหรับเข้า recovery mode

### Recovery Sync Trigger

- [ ] นิยาม automated triggers สำหรับ mismatch recovery
- [ ] ทดสอบ action เช่น resync, halt, drain หรือ rebuild local state
- [ ] พิสูจน์ว่า recovery mode ให้ความสำคัญกับ portfolio safety ก่อนเสมอ

### Logging / Observability

- [ ] สร้าง signal logs, order logs, risk logs, recovery logs และ venue-health logs
- [ ] ทำให้ log replay ได้สำหรับ post-mortem analysis
- [ ] นิยาม dashboard และ alert สำหรับ critical runtime failures

## โครงสร้าง repo ที่แนะนำ

```text
configs/
  venues/
  symbols/
data/
  raw/
  processed/
notebooks/
src/
  collectors/
  state/
  normalization/
  costs/
  portfolio/
  risk/
  backtest/
  signals/
  execution/
  reconciliation/
  observability/
reports/
```

## ลำดับการสร้างที่แนะนำ

- [ ] 1. Shared market map
- [ ] 2. Live collectors
- [ ] 3. State และ snapshot layer
- [ ] 4. Normalized funding panel
- [ ] 5. Cost model
- [ ] 6. Threshold backtest แบบง่าย
- [ ] 7. Dynamic backtest
- [ ] 8. Risk และ guardrail monitors
- [ ] 9. Reconciliation และ recovery flows
- [ ] 10. Prediction error analysis
- [ ] 11. Shadow mode
- [ ] 12. Small live trial
- [ ] 13. Capacity modeling และ scale-up readiness ถึง `1M USD`

## Entry Rule เวอร์ชันแรกที่ควรเริ่มทดสอบ

- [ ] เข้าเมื่อ `net_edge_1h > threshold`
- [ ] signal ต้องค้างอย่างน้อย `confirm_time_sec`
- [ ] ทั้งสอง venue ต้องมี depth พอสำหรับ size เป้าหมาย
- [ ] prediction freshness ต้องไม่เก่าเกินเกณฑ์
- [ ] ข้าม symbol ที่ predicted funding ไม่น่าเชื่อถือ

## Exit Rule เวอร์ชันแรกที่ควรเริ่มทดสอบ

- [ ] ออกเมื่อ `net_edge_1h < exit_threshold`
- [ ] ออกเมื่อ spread flip sign
- [ ] ออกเมื่อครบ max hold time
- [ ] ออกหรือ reduce เมื่อ hedge leg ฝั่งหนึ่งเริ่มไม่ปลอดภัย

## คำตอบที่ POC ควรให้ได้เมื่อจบงาน

- [ ] cross-exchange funding spread arbitrage ระหว่าง Lighter และ Hyperliquid ทำได้จริงหรือไม่
- [ ] มี symbol ไหนที่ viable จริง
- [ ] entry threshold เท่าไรถึงคุ้มหลังหักต้นทุน
- [ ] threshold ควรแยกตาม symbol หรือไม่
- [ ] edge มาจาก funding เป็นหลัก หรือจริง ๆ ถูกครอบโดย execution quality และ basis effect
- [ ] ระบบรองรับทุนรวม `1M USD` ได้จริงหรือไม่
- [ ] ถ้ารองรับได้ ต้องจัด allocation อย่างไร
- [ ] ถ้ายังรองรับไม่ได้ bottleneck อยู่ที่ liquidity, execution, risk หรือ venue concentration

## Next Steps ทันที

- [ ] สร้าง shared market map
- [ ] implement collectors สำหรับทั้งสอง venue
- [ ] เริ่มเก็บ live funding และ book snapshots ทันที
- [ ] สร้าง normalized spread panel
- [ ] รัน cost-aware threshold sweep รอบแรก
