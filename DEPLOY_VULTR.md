# Deploy บน Vultr

เอกสารนี้สรุปวิธี deploy collector ของโปรเจคนี้ขึ้น Vultr และสรุปค่าใช้จ่ายสำหรับรัน 30 วัน

อ้างอิงราคา ณ วันที่ `2026-03-12`

## สเปกที่เหมาะกับโปรเจคนี้

สำหรับ collector นี้ เป้าหมายคือ:

- รัน `all shared symbols`
- เก็บ `parquet`
- อัปโหลดขึ้น R2
- ไม่เปิด execution/account collectors

### ขั้นต่ำที่พอใช้จริง

- `Cloud Compute High Performance`
- `2 vCPU`
- `2 GB RAM`
- ราคา `USD 18 / เดือน`

### สเปกที่แนะนำ

- `Cloud Compute High Performance`
- `2 vCPU`
- `4 GB RAM`
- ราคา `USD 24 / เดือน`

### ถ้าจะประหยัดสุด

- `Cloud Compute High Performance`
- `1 vCPU`
- `2 GB RAM`
- ราคา `USD 12 / เดือน`

ใช้ได้สำหรับการทดลอง แต่ไม่ใช่ตัวที่ผมแนะนำถ้าจะปล่อยเก็บข้อมูลยาว ๆ

## ค่าใช้จ่าย 30 วัน

จากหน้า pricing ของ Vultr:

- `1 vCPU / 2 GB` = `USD 12 / เดือน`
- `2 vCPU / 2 GB` = `USD 18 / เดือน`
- `2 vCPU / 4 GB` = `USD 24 / เดือน`

จาก docs ของ Vultr:

- server คิดเงินแบบ `hourly`
- server ที่ `stopped` แล้วยังไม่ `destroyed` ยังคิดเงินต่อ

ดังนั้นถ้ารัน 30 วันแบบปล่อยต่อเนื่อง:

- แบบประหยัดสุด: `USD 12 / 30 วัน`
- ขั้นต่ำที่พอใช้จริง: `USD 18 / 30 วัน`
- แบบแนะนำ: `USD 24 / 30 วัน`

## ค่า R2 เพิ่มเท่าไหร่

ถ้าใช้ config collector ปัจจุบัน:

- ทุก shared symbols
- `parquet + zstd`
- ไม่มี raw ระยะยาว

ประมาณการ R2:

- storage ประมาณ `35 GB / 30 วัน`
- free `10 GB-month`
- billable ประมาณ `25 GB`
- ค่าใช้จ่ายประมาณ `USD 0.38 / 30 วัน`

## สรุปรวมค่าใช้จ่าย

- `1 vCPU / 2 GB + R2` ประมาณ `USD 12.38 / 30 วัน`
- `2 vCPU / 2 GB + R2` ประมาณ `USD 18.38 / 30 วัน`
- `2 vCPU / 4 GB + R2` ประมาณ `USD 24.38 / 30 วัน`

## ถ้าดูจากเครดิตในภาพของคุณ

ในภาพมี `Remaining Credit = USD 250`

ถ้าใช้งานที่ระดับนี้:

- `1 vCPU / 2 GB` อยู่ได้ประมาณ `20 เดือน`
- `2 vCPU / 2 GB` อยู่ได้ประมาณ `13 เดือน`
- `2 vCPU / 4 GB` อยู่ได้ประมาณ `10 เดือน`

ตัวเลขนี้เป็นการหารแบบหยาบจากเครดิตกับ monthly price
และยังไม่รวมค่าใช้งานอื่นที่อาจเพิ่มเข้ามา

## สิ่งที่ต้องเตรียม

- Vultr account
- SSH public key
- GitHub access
- Cloudflare R2 bucket
- ค่าใน `config.yaml`

## ขั้นตอน deploy

### 1. สร้าง instance

ใน Vultr Console:

1. กด `Deploy`
2. เลือก `Cloud Compute`
3. เลือก region ใกล้คุณ เช่น `Singapore`
4. เลือก image: `Ubuntu 24.04`
5. เลือก plan:
   - แนะนำ: `2 vCPU / 4 GB`
   - ประหยัด: `2 vCPU / 2 GB`
6. ใส่ `SSH key`
7. กด deploy

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

ใส่ค่า R2 ของคุณลงใน `config.yaml`

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

### 8. รัน collector

```bash
python -m src.collectors.live.collect_all_live --all-shared --write-r2
```

### 9. รันแบบไม่หลุดตอนปิด SSH

```bash
tmux new -s funding
cd ~/poc_lighter_hyperliquid
source .venv/bin/activate
python -m src.collectors.live.collect_all_live --all-shared --write-r2
```

detach:

```bash
Ctrl+B แล้วกด D
```

กลับเข้า session:

```bash
tmux attach -t funding
```

## ข้อควรระวัง

- Vultr คิดเงินรายชั่วโมง
- ถ้า `stop` instance แต่ไม่ `destroy` ยังคิดเงินต่อ
- ถ้าจะหยุดค่าใช้จ่าย ต้อง `destroy` instance

## คำแนะนำสุดท้าย

ถ้าจะเริ่ม deploy ตอนนี้:

- แนะนำ `2 vCPU / 4 GB`
- ถ้าจะกดต้นทุนก่อน ใช้ `2 vCPU / 2 GB`

สำหรับเครดิต `USD 250` ในภาพนี้ คุณมีเหลือพอมากสำหรับรัน collector นี้เกิน 1 เดือนสบาย

## Sources

- Vultr pricing: https://www.vultr.com/pricing/
- Vultr billing model: https://docs.vultr.com/support/platform/billing/how-am-i-billed-for-my-servers
- Vultr SSH connection: https://docs.vultr.com/products/compute/cloud-compute/connection/openssh
- Vultr provisioning guide: https://docs.vultr.com/products/compute/cloud-compute/provisioning
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
