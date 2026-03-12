# Deploy บน Hetzner

เอกสารนี้สรุปวิธี deploy collector ของโปรเจคนี้ขึ้น Hetzner Cloud และสรุปค่าใช้จ่าย 30 วัน

อ้างอิงราคา ณ วันที่ `2026-03-12`

- Hetzner ปรับราคามีผล `2026-04-01`
- ราคาของ Hetzner ด้านล่างเป็น `ไม่รวม VAT`
- ค่า R2 คิดแยกจาก Hetzner

## สเปกที่แนะนำ

### ตัวเลือกที่แนะนำ

- `CPX22`
- `Ubuntu 24.04`
- `Primary IPv4 + IPv6`

เหตุผล:

- พอสำหรับรัน collector นี้แบบ `all shared`
- มี headroom มากกว่า plan เล็ก
- ราคายังคุมได้

### ตัวเลือกประหยัด

- `CX23`
- ใช้ได้ถ้าจะกดต้นทุนสุด
- เหมาะกับงานเก็บข้อมูลอย่างเดียว
- แต่ margin น้อยกว่า `CPX22`

## ค่าใช้จ่าย 30 วัน

### ราคาจาก Hetzner

จาก docs ของ Hetzner:

- `CX23` ตอนนี้ `€2.99/เดือน` และหลัง `2026-04-01` เป็น `€3.99/เดือน`
- `CPX22` ตอนนี้ `€5.99/เดือน` และหลัง `2026-04-01` เป็น `€7.99/เดือน`
- `Cloud Primary IPv4` = `€0.50/เดือน`

### ถ้าสร้างวันนี้และรัน 30 วัน

เพราะวันนี้คือ `2026-03-12` การใช้งาน 30 วันจะข้ามช่วงปรับราคา

ประมาณการแบบง่าย:

- `CX23 + IPv4`
  - ช่วงก่อน `2026-04-01`: ใช้ราคาเก่า
  - ช่วงหลัง `2026-04-01`: ใช้ราคาใหม่
  - รวมประมาณ `€3.82 / 30 วัน`

- `CPX22 + IPv4`
  - ช่วงก่อน `2026-04-01`: ใช้ราคาเก่า
  - ช่วงหลัง `2026-04-01`: ใช้ราคาใหม่
  - รวมประมาณ `€7.16 / 30 วัน`

### ถ้าสร้างหลัง `2026-04-01`

- `CX23 + IPv4` ประมาณ `€4.49 / 30 วัน`
- `CPX22 + IPv4` ประมาณ `€8.49 / 30 วัน`

### ค่า R2 เพิ่มเท่าไหร่

ถ้าใช้ config collector ปัจจุบัน:

- เก็บ `Parquet + zstd`
- ทุก shared symbols
- ไม่มี raw ระยะยาว

ประมาณการ storage บน R2 อยู่ราว `35 GB / 30 วัน`

R2 ให้ฟรี `10 GB-month` และเก็บเพิ่ม `USD 0.015 / GB-month`

ดังนั้น:

- billable storage ประมาณ `25 GB`
- ค่า R2 ประมาณ `USD 0.38 / 30 วัน`

### สรุปค่าใช้จ่ายรวม

ถ้าเริ่มวันนี้:

- `CX23 + R2` ประมาณ `€3.82 + USD 0.38 / 30 วัน`
- `CPX22 + R2` ประมาณ `€7.16 + USD 0.38 / 30 วัน`

ถ้าจะเอาแบบใช้งานจริง:

- แนะนำ `CPX22`
- ถ้าจะกดต้นทุนให้ต่ำสุด ใช้ `CX23`

## สิ่งที่ต้องเตรียม

- Hetzner Cloud account
- SSH public key
- GitHub access สำหรับ clone repo
- Cloudflare R2 bucket
- ค่าใน `config.yaml`
  - `bucket`
  - `account_id`
  - `access_key_id`
  - `secret_access_key`
  - `endpoint_url`

## ขั้นตอน deploy

### 1. สร้าง server

ใน Hetzner Console:

1. ไป `Servers`
2. กด `Add Server`
3. เลือก:
   - Location: `FSN1` หรือ `NBG1`
   - Image: `Ubuntu 24.04`
   - Type: `CPX22` หรือ `CX23`
   - Networking: เปิด `IPv4` และ `IPv6`
   - SSH key: ใส่ public key ของคุณ
4. กดสร้าง server

### 2. SSH เข้าเครื่อง

```bash
ssh root@YOUR_SERVER_IP
```

### 3. ติดตั้ง software ที่ต้องใช้

```bash
apt update
apt install -y git python3 python3-venv tmux
```

### 4. clone repo และติดตั้ง dependencies

```bash
git clone git@github.com:spinsnake/poc_lighter_hyperliquid.git
cd poc_lighter_hyperliquid
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. สร้าง `config.yaml`

สร้างไฟล์ `config.yaml` บน server โดยใช้ค่า R2 ของคุณ

ดูตัวอย่างจาก:

- [config.example.yaml](/d:/git/poc_lighter_hyperliquid/config.example.yaml)

### 6. ทดสอบ R2

```bash
python -m src.storage.test_r2_connection --upload-test --cleanup
```

### 7. generate reference data

```bash
python -m src.collectors.non_live.collect_reference_data
```

ต้องมีไฟล์นี้ก่อน:

- `data/reference/shared_markets_latest.csv`

### 8. รัน collector

แบบ foreground:

```bash
python -m src.collectors.live.collect_all_live --all-shared --write-r2
```

### 9. รันให้ค้างหลังปิด SSH

ใช้ `tmux`

```bash
tmux new -s funding
cd ~/poc_lighter_hyperliquid
source .venv/bin/activate
python -m src.collectors.live.collect_all_live --all-shared --write-r2
```

detach ออก:

```bash
Ctrl+B แล้วกด D
```

กลับเข้า session:

```bash
tmux attach -t funding
```

## output ที่จะได้

บน local disk:

- `data/processed/live/funding_snapshots/date=YYYY-MM-DD/*.parquet`
- `data/processed/live/book_snapshots/date=YYYY-MM-DD/*.parquet`
- `data/processed/live/trade_aggregates/date=YYYY-MM-DD/*.parquet`

ถ้าเปิด raw:

- `data/raw/.../*.jsonl`

บน R2:

- `live/funding_snapshots/date=YYYY-MM-DD/*.parquet`
- `live/book_snapshots/date=YYYY-MM-DD/*.parquet`
- `live/trade_aggregates/date=YYYY-MM-DD/*.parquet`

## คำแนะนำสุดท้าย

- ถ้าจะเริ่มรอบแรก: ใช้ `CPX22`
- ถ้าจะทดลองลดต้นทุน: ใช้ `CX23`
- ถ้าจะเก็บยาว 30 วันจริง ผมยังเลือก `CPX22` มากกว่า เพราะโอกาสชน limit น้อยกว่า

## Sources

- Hetzner price adjustment: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
- Hetzner IPv4 pricing: https://docs.hetzner.com/general/infrastructure-and-availability/ipv4-pricing/
- Hetzner create server: https://docs.hetzner.com/cloud/servers/getting-started/creating-a-server/
- Hetzner connect via SSH: https://docs.hetzner.com/cloud/servers/getting-started/connecting-to-the-server/
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
