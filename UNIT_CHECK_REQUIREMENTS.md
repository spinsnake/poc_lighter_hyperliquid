# ข้อมูลที่ต้องใช้เพื่อตอบ 2 คำถามเรื่อง Unit: Funding Rate และ Contract Size

## เป้าหมาย

เอกสารนี้ใช้ตอบ 2 คำถาม:

1. Funding rate ของ Hyperliquid กับ Lighter ใช้หน่วยตรงกันหรือไม่
2. Contract size ของสอง exchange ใช้หน่วยเดียวกันหรือไม่

เอกสารนี้เน้นว่า "ต้องใช้ข้อมูลอะไร" และ "ต้องเช็คอย่างไร" ไม่ใช่สรุปผลสุดท้ายล่วงหน้า

## สรุปสั้นที่สุด

ถ้าจะตอบ 2 คำถามนี้ให้มั่นใจ ต้องมีข้อมูล 3 ชั้น:

- docs / contract specifications
- API fields หรือ websocket fields ที่ใช้จริง
- ตัวอย่าง position / funding payment / notional จริง เพื่อเช็คย้อนหลังเชิง empirical

## คำถามที่ 1: Funding Rate ใช้หน่วยตรงกันไหม

### สิ่งที่ต้องยืนยัน

- rate ที่แต่ละ venue ส่งมาเป็นหน่วยอะไร
- rate นั้นเป็น "ต่อชั่วโมง", "ต่อ funding interval", หรือ "สูตร 8 ชั่วโมงแต่จ่ายรายชั่วโมง"
- funding payment จริงคำนวณจากราคาอะไร
- funding payment จริงคำนวณจาก position size แบบไหน

### ข้อมูลจาก Lighter ที่ต้องใช้

#### A. Docs / spec

- [ ] หน้า funding ของ Lighter
- [ ] หน้า websocket market stats ของ Lighter
- [ ] หน้า contract specifications ของ Lighter

#### B. Fields ที่ต้องดึง

จาก `market_stats` websocket:

- [ ] `symbol`
- [ ] `market_id`
- [ ] `index_price`
- [ ] `mark_price`
- [ ] `current_funding_rate`
- [ ] `funding_rate`
- [ ] `funding_timestamp`

จาก funding/account history:

- [ ] `rate`
- [ ] `change`
- [ ] `position_size`
- [ ] `position_side`
- [ ] `timestamp`

จาก position data:

- [ ] `position`
- [ ] `avg_entry_price`
- [ ] `position_value`

#### C. ทำไมข้อมูลชุดนี้จำเป็น

- `current_funding_rate` ใช้ดู upcoming funding estimate
- `funding_rate` ใช้ดู funding รอบล่าสุด
- `funding_timestamp` ใช้จับคู่กับ settlement จริง
- `rate + change + position_size` ใช้คำนวณย้อนกลับว่า rate field อยู่ในหน่วยเดียวกับ funding payment จริงหรือไม่
- `mark_price` และ `index_price` ใช้เช็คว่า funding ใช้ mark/index logic ตาม docs จริง

### ข้อมูลจาก Hyperliquid ที่ต้องใช้

#### A. Docs / spec

- [ ] หน้า funding ของ Hyperliquid
- [ ] หน้า perpetuals info endpoint
- [ ] หน้า contract specifications ของ Hyperliquid

#### B. Fields ที่ต้องดึง

จาก `metaAndAssetCtxs`:

- [ ] `funding`
- [ ] `oraclePx`
- [ ] `markPx`
- [ ] `midPx`
- [ ] `impactPxs`
- [ ] `openInterest`

จาก `fundingHistory`:

- [ ] `coin`
- [ ] historical funding rate ต่อช่วงเวลา
- [ ] `startTime`
- [ ] `endTime`

จาก `userFunding`:

- [ ] `delta.type`
- [ ] `delta.fundingRate`
- [ ] `delta.szi`
- [ ] `delta.usdc`
- [ ] `time`

จาก position/account summary (`clearinghouseState`):

- [ ] `szi`
- [ ] `positionValue`
- [ ] margin summary ที่เกี่ยวข้อง

จาก predicted funding endpoint:

- [ ] raw response ของ `predictedFundings`
- [ ] predicted rate field(s) ที่ได้จริงจาก response

หมายเหตุ:

- docs ของ Hyperliquid ระบุ endpoint `predictedFundings` แต่ response schema ที่เปิดเผยในหน้าหลักไม่ละเอียดเท่า endpoint อื่น
- ดังนั้นควรเก็บ raw response เต็ม ๆ ของ `predictedFundings` ตั้งแต่รอบแรก

#### C. ทำไมข้อมูลชุดนี้จำเป็น

- `funding` จาก asset context ใช้ดู current funding field ที่ระบบเห็นสด
- `fundingHistory` ใช้ดูค่าที่ settle แล้ว
- `userFunding.delta.fundingRate + delta.szi + delta.usdc` ใช้คำนวณย้อนกลับว่า funding payment ตรงกับ field rate หรือไม่
- `oraclePx` สำคัญเพราะ docs ระบุว่า funding payment ใช้ oracle price ไม่ใช่ mark price

### วิธีเช็ค funding unit แบบ empirical

- [ ] เลือก 1 settlement window ที่มี position จริง
- [ ] ดึง funding rate ของรอบนั้น
- [ ] ดึง position size ของรอบนั้น
- [ ] ดึงราคาที่ venue ใช้ใน funding formula
- [ ] ดึง funding payment จริง
- [ ] คำนวณกลับ:

`implied_rate = funding_payment / (position_size * reference_price)`

- [ ] เปรียบเทียบ `implied_rate` กับ field funding ที่ venue ส่งมา
- [ ] ทำซ้ำหลายรอบ หลาย symbol

### ผลลัพธ์ที่ต้องได้สำหรับคำถามนี้

- [ ] ระบุได้ว่า field ไหนคือ upcoming funding
- [ ] ระบุได้ว่า field ไหนคือ settled funding
- [ ] ระบุได้ว่าแต่ละ venue สื่อ rate ในหน่วยต่อชั่วโมงหรือไม่
- [ ] ระบุได้ว่าต้อง normalize เพิ่มหรือไม่ก่อนนำไปเทียบกัน

## คำถามที่ 2: Contract Size ใช้หน่วยเดียวกันไหม

### สิ่งที่ต้องยืนยัน

- size 1 หน่วยบนแต่ละ venue หมายถึงอะไร
- size field เป็น "contracts", "base asset units", หรือหน่วยอื่น
- notional ควรคำนวณจาก `size * price` ได้ตรงกับ value จริงหรือไม่

### ข้อมูลจาก Lighter ที่ต้องใช้

#### A. Docs / spec

- [ ] หน้า contract specifications ของ Lighter
- [ ] หน้า orderBooks / orderBookDetails ของ Lighter
- [ ] หน้า Get Started ของ Lighter API

#### B. Fields ที่ต้องดึง

จาก market spec / order book metadata:

- [ ] `Price Step`
- [ ] `Amount Step`
- [ ] `min base amount`
- [ ] `supported size decimals`
- [ ] `supported price decimals`

จาก order / trade / position:

- [ ] `base_amount`
- [ ] `price`
- [ ] `position`
- [ ] `avg_entry_price`
- [ ] `position_value`
- [ ] `filled_base_amount`
- [ ] `filled_quote_amount`

#### C. ทำไมข้อมูลชุดนี้จำเป็น

- `Amount Step` ใช้บอก precision ของ size
- `base_amount` ใช้บอกว่า order ถูกส่งในหน่วย base asset
- `position` และ `position_value` ใช้เช็คว่า `position * price` ให้ notional ตรงกับ value หรือไม่

### ข้อมูลจาก Hyperliquid ที่ต้องใช้

#### A. Docs / spec

- [ ] หน้า contract specifications ของ Hyperliquid
- [ ] หน้า tick and lot size
- [ ] หน้า perpetuals info endpoint

#### B. Fields ที่ต้องดึง

จาก `meta` หรือ `metaAndAssetCtxs`:

- [ ] `name`
- [ ] `szDecimals`
- [ ] `maxLeverage`

จาก position / account summary:

- [ ] `szi`
- [ ] `positionValue`

จาก public market context:

- [ ] `markPx`
- [ ] `oraclePx`
- [ ] `midPx`

จาก order / fill data:

- [ ] order size (`sz`)
- [ ] fill size
- [ ] fill price

#### C. ทำไมข้อมูลชุดนี้จำเป็น

- Hyperliquid docs ระบุว่า perp contract คือ `1 unit of underlying spot asset`
- `szDecimals` ใช้บอก precision ของ size
- `szi` เป็น position size จริงที่ใช้เช็ค notional
- `positionValue` และ price fields ใช้ยืนยันว่า `szi * price` สอดคล้องกับมูลค่าจริง

### วิธีเช็ค contract size แบบ empirical

- [ ] เลือก symbol เดียวกันบนทั้งสอง venue
- [ ] ดึง position size และราคาในเวลาใกล้กัน
- [ ] คำนวณ notional ทั้งสองฝั่ง:

`notional ≈ size * reference_price`

- [ ] เปรียบเทียบกับ value field ที่ venue รายงาน
- [ ] เช็คว่า size 1 หน่วยให้ความหมายใกล้กันหรือไม่

### ผลลัพธ์ที่ต้องได้สำหรับคำถามนี้

- [ ] ระบุได้ว่า Lighter size เป็นหน่วย base asset หรือไม่
- [ ] ระบุได้ว่า Hyperliquid size เป็นหน่วย base asset หรือไม่
- [ ] ระบุได้ว่าต้องทำ conversion multiplier หรือไม่ก่อน hedge ข้าม venue
- [ ] ระบุได้ว่า hedge ratio ควรคำนวณจาก size ตรง ๆ หรือจาก notional

## ชุดข้อมูลขั้นต่ำที่ต้องเก็บ

ถ้าจะตอบสองคำถามนี้แบบเร็วที่สุด ควรเก็บอย่างน้อย:

### Lighter

- [ ] contract specifications
- [ ] orderBooks / orderBookDetails metadata
- [ ] market_stats websocket snapshots
- [ ] funding history ของ account
- [ ] position snapshots
- [ ] order/fill ตัวอย่างจริง

### Hyperliquid

- [ ] contract specifications
- [ ] metaAndAssetCtxs
- [ ] fundingHistory
- [ ] userFunding
- [ ] clearinghouseState
- [ ] order/fill ตัวอย่างจริง

## ชุดข้อมูลที่แนะนำให้เก็บเพิ่ม

- [ ] predicted funding raw payload ของทั้งสอง venue
- [ ] execution timestamps เพื่อจับ funding round ให้ตรง
- [ ] raw responses ของทุก endpoint ที่ใช้ตรวจ unit
- [ ] ตัวอย่างหลาย symbol ไม่ใช่ดูแค่ BTC/ETH

## Output ที่ควรทำหลังเก็บข้อมูล

- [ ] ตาราง `funding_unit_check.csv`
- [ ] ตาราง `contract_size_check.csv`
- [ ] โน้ตสรุป `unit_check_summary.md`

### ตัวอย่างคอลัมน์สำหรับ `funding_unit_check.csv`

- `venue`
- `symbol`
- `settlement_time_utc`
- `reported_funding_rate`
- `position_size`
- `reference_price`
- `funding_payment`
- `implied_rate`
- `rate_matches_flag`
- `notes`

### ตัวอย่างคอลัมน์สำหรับ `contract_size_check.csv`

- `venue`
- `symbol`
- `reported_size`
- `reference_price`
- `reported_position_value`
- `implied_notional`
- `size_unit_guess`
- `size_matches_base_asset_flag`
- `conversion_needed_flag`
- `notes`

## สิ่งที่ยังไม่ควร assume ล่วงหน้า

- [ ] อย่าสมมติว่า funding field ของทั้งสอง venue เทียบกันตรง ๆ ได้ทันที
- [ ] อย่าสมมติว่า size field ของทั้งสอง venue ใช้หน่วยเดียวกันเพียงเพราะ symbol ชื่อเหมือนกัน
- [ ] อย่าสมมติว่า mark price คือราคาที่ใช้คิด funding ทั้งสองฝั่ง
- [ ] อย่าสมมติว่า predicted funding endpoint ส่ง schema คงที่โดยไม่เก็บ raw payload

## แหล่งข้อมูลทางการที่ต้องอ้างอิง

- Lighter funding docs: https://docs.lighter.xyz/trading/funding
- Lighter contract specifications: https://docs.lighter.xyz/trading/contract-specifications
- Lighter WebSocket market stats: https://apidocs.lighter.xyz/docs/websocket-reference
- Lighter order books metadata: https://apidocs.lighter.xyz/reference/orderbooks
- Lighter get started: https://apidocs.lighter.xyz/docs/get-started
- Hyperliquid funding docs: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- Hyperliquid contract specifications: https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications
- Hyperliquid perpetuals info endpoint: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- Hyperliquid tick and lot size: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/tick-and-lot-size
- Hyperliquid rate limits: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits

## สรุป

ถ้าจะตอบ 2 คำถามนี้ให้จบแบบเชื่อถือได้ ต้องมี:

- spec ของแต่ละ venue
- field ที่ใช้จริงจาก market/account endpoints
- ตัวอย่าง funding payment จริง
- ตัวอย่าง position / notional จริง

ถ้าขาดอย่างใดอย่างหนึ่ง จะตอบได้แค่เชิงเอกสาร แต่ยังไม่พอสำหรับเอาไป hedge ข้าม venue อย่างมั่นใจ
