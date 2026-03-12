# คำสั่งรันที่ใช้บ่อย

## เริ่มเก็บ live data

### เก็บทุก shared symbols

```powershell
.\start_live_collect.ps1
```

ค่า default ตอนนี้คือ:

- `flush-sec = 1`
- `hyperliquid-poll-sec = 1`
- `parquet-batch-sec = 60`
- ไม่เขียน raw `JSONL` ถ้าไม่ได้ใส่ `-WriteRaw`
- ไม่เขียน `CSV` แล้ว เหลือแค่ `parquet` และ `jsonl`

### เก็บทุก shared symbols และอัปโหลด processed outputs ขึ้น R2

```powershell
.\start_live_collect.ps1 -WriteR2
```

ก่อนรัน:

- ใส่ค่าใน `config.yaml` ให้ครบ
- ต้องมี `data\reference\shared_markets_latest.csv`
- ถ้ายังไม่มี ให้รัน:

```powershell
.\.venv\Scripts\python.exe -m src.collectors.non_live.collect_reference_data
```

โครงสร้างบน R2 ตอนนี้จะเป็น:

- `live/funding_snapshots/...parquet`
- `live/book_snapshots/...parquet`
- `live/trade_aggregates/...parquet`

### เก็บเฉพาะ 20 เหรียญที่แนะนำ

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA
```

### เก็บเฉพาะ 20 เหรียญที่แนะนำ เป็นเวลา 30 นาที

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA -DurationSec 1800
```

### เก็บแบบเดียวกัน แต่เปิด raw JSONL สำหรับ debug

```powershell
.\start_live_collect.ps1 -Symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA -DurationSec 1800 -WriteRaw
```

## รันแบบ foreground

### ทดสอบแบบ all shared 5 นาที

```powershell
.\.venv\Scripts\python.exe -m src.collectors.live.collect_all_live --all-shared --duration-sec 300
```

### ทดสอบเฉพาะ 20 เหรียญที่แนะนำ 5 นาที

```powershell
.\.venv\Scripts\python.exe -m src.collectors.live.collect_all_live --symbols BTC,ETH,SOL,XRP,DOGE,BNB,LINK,HYPE,SUI,AVAX,AAVE,LTC,TRX,PAXG,ZEC,ENA,APT,DOT,SEI,ADA --duration-sec 300
```

### ทดสอบ R2 ที่ local

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.storage.test_r2_connection
.\.venv\Scripts\python.exe -m src.storage.test_r2_connection --upload-test --cleanup
```

## เช็กสถานะ

### ดู run info ล่าสุด

```powershell
Get-Content .\logs\collectors\live_collect_latest.json
```

### ดู parquet ล่าสุด

```powershell
Get-ChildItem .\data\processed\live\funding_snapshots -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,Length,LastWriteTime
Get-ChildItem .\data\processed\live\book_snapshots -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,Length,LastWriteTime
Get-ChildItem .\data\processed\live\trade_aggregates -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name,Length,LastWriteTime
```

### ดู raw JSONL ล่าสุด

```powershell
Get-ChildItem .\data\raw -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 10 FullName,Length,LastWriteTime
```

## หยุดการเก็บข้อมูล

### หยุดจาก PID ล่าสุด

```powershell
$run = Get-Content .\logs\collectors\live_collect_latest.json | ConvertFrom-Json
Stop-Process -Id $run.pid
```

## output หลัก

- `data/processed/live/funding_snapshots/...parquet`
- `data/processed/live/book_snapshots/...parquet`
- `data/processed/live/trade_aggregates/...parquet`
- `data/raw/lighter/ws/...jsonl`
- `data/raw/hyperliquid/ws/...jsonl`
- `data/raw/hyperliquid/rest/live_info/...jsonl`
