# 📚 MennzLore: Fictional Lore Extraction Engine & MCP Server

> **MennzLore** คือระบบสกัดและวิเคราะห์ **Lore** (ตำนาน ประวัติศาสตร์ พจนานุกรม และความสัมพันธ์) จากงานประพันธ์ประเภท นิยาย บทภาพยนตร์ หรือซีรีส์ดิบ แปลงให้อยู่ในรูปของโครงสร้างข้อมูล (Structured Data) ที่สามารถค้นหา วิเคราะห์จุดเชื่อมโยง (Foreshadowing) และเรนเดอร์ออกมาเป็น **แผนที่ SVG ทางภูมิศาสตร์การเดินทาง** รวมถึง **ชุดคิวกล้องถ่ายทำ (Shot List)** และ **Image Prompts สำหรับการสร้างภาพคีย์เฟรมและแผนที่ภาพโบราณ** ได้อย่างเป็นระบบ

---

## 🛠️ โครงสร้างทางสถาปัตยกรรม (System Architecture)

ระบบแยกส่วนการทำงานออกเป็น 3 ชั้น เพื่อความสะอาดและสะดวกรวมศูนย์ (Single Source of Truth) ดังนี้:

*   **1. Deterministic Engine (`engine/`):** สคริปต์ Python ที่ใช้ประมวลผลข้อมูล ดึงพจนานุกรม จัดระเบียบสถานที่ วาดแผนที่ และประกอบเป็นสรุปรวมเล่ม Markdown
*   **2. LLM Core (`prompts/` & `schemas/`):** ชุดคำสั่งที่ใช้จัดระเบียบความคิดของ AI และ JSON Schemas สำหรับควบคุม Structured Outputs ป้องกันการป้อนข้อมูลที่หลุดกรอบ
*   **3. Communication Bridge (`mcp_server/`):** ตัวเซิร์ฟเวอร์เชื่อมโยงการทำงานผ่านโปรโตคอล **Model Context Protocol (MCP)** เพื่อสื่อสารกับ AI Client
*   **4. Visual Web Dashboard (`dashboard/`):** หน้าเว็บอินเตอร์เฟสสำหรับการสำรวจประวัติศาสตร์ไทม์ไลน์ และแผนที่เดินทางปฏิสัมพันธ์

---

## 🔄 กระบวนการทำงาน 10 เฟส (The 10-Phase Pipeline)

ระบบสกัดข้อมูลผ่านขั้นตอนอย่างเป็นลำดับขั้น เพื่อความแม่นยำสูงสุด:

| เฟส (Phase) | ชื่อขั้นตอน (Name) | ประเภทการทำงาน | ผลผลิตที่ได้ (Output) |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Acquire | External (ดิบ) | `raw/*.txt` (ไฟล์นิยายดิบรายตอน) |
| **Phase 2** | Clean | LLM / Text Clean | `clean/*.txt` (ไฟล์ผ่านการล้างข้อมูลขยะ) |
| **Phase 3.1** | Global Lore & Name Map | LLM (ภาพรวมเล่ม) | `verification/name_map.json`, `global_lore.json` |
| **Phase 3.2** | Auto-Verify | **Engine (verify_names)** | รายงานสแกนเปรียบเทียบชื่อในข้อความดิบ (กันชื่อปลอม) |
| **Phase 4-P1** | Micro-Facts (3-Pass) | LLM (รายตอน) | `micro_facts/*_micro_facts.json` (ข้อมูลรวม 3-Pass) |
| **Phase 4-P2** | Sliding Window | LLM (กลุ่มตอน) | `analysis/pass2/batch_*.json` (สรุปข้อมูลข้ามตอน) |
| **Phase 5-6** | Validate & Link | Engine / LLM | ตรวจสอบการลวงข้อมูลจุดปริศนา (Foreshadowing) |
| **Phase 7** | Assemble | **Engine (assemble)** | `output/master_lorebook_full.md` (สารานุกรมรวมเล่ม) |
| **Phase 8** | Finalize | Engine | อัปเดตข้อมูลสถิติ ขนาดตัวหนังสือ และประมวลผล Metadata |
| **Phase 9** | Production Render | **Engine (production)** | `output/production/` (Image Prompts & Cinematography) |
| **Phase 10** | Spatial Render | **Engine (spatial)** | `output/spatial/` (แผนที่ SVG & พรอมต์แผนที่ภาพโบราณ) |

---

## 💎 จุดเด่นที่ได้รับการปรับปรุงใหม่ (Latest Updates)

1.  **ตัวติดตั้งอัตโนมัติ (`install.py`):** เพิ่มสคริปต์ติดตั้งระบบเบ็ดเสร็จในคำสั่งเดียว ช่วยดาวน์โหลดแพ็กเกจ สำรองข้อมูล และเชื่อมต่อไฟล์ตั้งค่าเข้ากับแอปพลิเคชัน AI ให้เองทันที
2.  **ระบบพรอมต์แผนที่จำลองแฟนตาซี (Antique Cartography Prompt):** ใน Phase 10 ระบบจะคำนวณและสกัดพิกัดภูมิศาสตร์ออกมาสร้างเป็น **Map Generation Prompts** สำหรับส่งต่อไปยัง AI Image Generators (เช่น Midjourney/Stable Diffusion) เพื่อสร้างแผนที่โบราณสไตล์กระดาษอาร์ตย้อนยุค
3.  **แก้บั๊ก Unicode Crash บน Windows:** ลบสัญลักษณ์ขีดกรอบลายเส้น Unicode (`\u2500` หรือ `─`) ในการแสดงผล log ออกทั้งหมด และเปลี่ยนมาใช้ขีด ASCII มาตรฐาน (`---`, `===`) ทำให้สคริปต์รันบนระบบปฏิบัติการ Windows ภาษาไทยได้โดยไม่แครช
4.  **การควบคุมอารมณ์และสไตล์ของภาพ (Art Direction Control):** ระบบจำแนกประเภทวรรณกรรมอัตโนมัติ (เช่น ไซไฟย้อนยุค, แฟนตาซีมิติมืด, ตำนานเทพปรัมปรา) เพื่อสร้างแนวทางควบคุมมุมกล้อง โทนสี แสง และเลนส์ถ่ายทำภาพยนตร์ที่เหมาะสมของแต่ละตอน
5.  **ระบบมัลติ-วอลลุ่ม (Multi-Volume Saga Mode):** เอนจินรองรับการรันและสืบทอดข้อมูลข้ามเล่ม (Cross-Volume Handoff) ส่งต่อข้อมูลความจริง พจนานุกรม และความสัมพันธ์เพื่อใช้เป็นบริบทวิเคราะห์เล่มต่อๆ ไป พร้อมกับระบบค้นหาจุดไม่สอดคล้องกันของบทย้อนหลัง (Consistency Audit & Flagging)

---

## 🚀 วิธีติดตั้งและใช้งาน MCP Server (Playbook)

คุณสามารถนำ **MennzLore MCP Server** ไปเชื่อมต่อใช้งานกับแอปแชทและโปรแกรมเขียนโค้ดต่างๆ (เช่น Claude Desktop, Claude Code CLI, Cursor, หรือ Windsurf) ได้ง่ายๆ ด้วยขั้นตอนด้านล่างนี้:

### 1. ติดตั้งแบบอัตโนมัติ (One-liner Installation)
เปิดโปรแกรม **PowerShell** ในเครื่องคอมพิวเตอร์ของคุณ แล้วคัดลอกคำสั่งนี้ไปรัน:
```powershell
python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mgprona/MennzLore/master/install.py').read())"
```
*สคริปต์จะดาวน์โหลดแพ็กเกจที่จำเป็น และเขียนพาธลงในไฟล์คอนฟิก `claude_desktop_config.json` ในเครื่องคุณให้อัตโนมัติทันที*

### 2. ติดตั้งแบบกำหนดเอง (Manual Configuration)
หากต้องการตั้งค่าพาธด้วยตัวเอง ให้ใส่ข้อมูลนี้ลงในไฟล์ตั้งค่า MCP Server ของแอปพลิเคชันของคุณ:
```json
{
  "mcpServers": {
    "mennzlore": {
      "command": "python",
      "args": [
        "C:/Users/mennz/.gemini/antigravity/scratch/MennzLore/mcp_server/server.py"
      ],
      "env": {
        "OPENROUTER_API_KEY": "YOUR_OPENROUTER_API_KEY_HERE"
      }
    }
  }
}
```

### 3. รายการเครื่องมือที่พร้อมให้บริการ (Exposed Tools)
เมื่อติดตั้งเสร็จ ตัวเอไอจะเข้าถึงเครื่องมือเหล่านี้ได้ทันทีในห้องแชท:
*   **`verify_character_names`:** ตรวจสอบความถูกต้องของคำสะกดตัวละครเทียบกับบทเนื้อเรื่องดิบ
*   **`merge_micro_facts`:** รวมและ Validate ไฟล์ข้อมูล 3-Pass รายตอน
*   **`assemble_lorebook_tool`:** สรุปรวบรวมไฟล์รายงานตอนทั้งหมดมาประกอบเข้าเล่มเดี่ยว
*   **`render_production_tool`:** สร้างคิวกล้อง Shot List และพรอมต์สตอรี่บอร์ดภาพยนตร์
*   **`render_map_tool`:** เรนเดอร์พิกัดภูมิศาสตร์ออกมาเป็นแผนที่เวกเตอร์ SVG
*   **`open_dashboard_tool`:** เปิดรันเซิร์ฟเวอร์หน้าเว็บแผนที่พิกัดที่ `http://localhost:8000`

---

## 📊 ตัวอย่างวรรณกรรมที่ใช้ทวนสอบจริง (Validation Showcases)

ระบบได้รับการยืนยันการทำงานและสกัดข้อมูลสำเร็จ 100% กับวรรณกรรมประวัติศาสตร์และตำนานโบราณ:

### 1. **The Time Machine** (วรรณกรรมไซไฟวิทยาศาสตร์ โดย H. G. Wells)
*   **ขนาดข้อมูล:** 8 ตอน (EP001 - EP008)
*   **ผลลัพธ์:** สกัดเหตุการณ์สำคัญ 24 เหตุการณ์, ตรวจพบตัวละคร 11 ตัวเด่นอย่างแม่นยำ (0 Missing Characters), สร้างแผนผังพิกัดอนาคตไกล และภาพร่างคีย์เฟรมการเดินทางข้ามเวลาสไตล์อุตสาหกรรม

### 2. **The Fates of the Princes of Dyfed** (ตำนานเวลส์ปรัมปรา โดย Kenneth Morris)
*   **ขนาดข้อมูล:** 9 ตอน (EP001 - EP009)
*   **ผลลัพธ์:** ตรวจพบตัวละครหลักและสถานที่โบราณ, สร้างแผนผังความสัมพันธ์ D3.js บน Dashboard, เรนเดอร์แผนที่ประวัติศาสตร์ของแคว้น Dyfed ในแบบจำลองโบราณ และสกัดพรอมต์ความละเอียดสูงสำหรับเจนแผนที่แฟนตาซีฉบับกระดาษเขียนสีโบราณ (Antique Cartography)

### 3. **The Poictesme Mythos** (วรรณกรรมแฟนตาซี โดย James Branch Cabell)
*   **ขนาดข้อมูล:** 2 เล่ม (Vol 1: Figures of Earth - 25 ตอน, Vol 2: The Silver Stallion - 20 ตอน)
*   **ผลลัพธ์:** นำร่องการรันแบบ Saga Mode ส่งต่อความทรงจำของ Dom Manuel และเหล่านักรบจากเล่ม 1 ไปตรวจหาความไม่สอดคล้องในการเล่าขานของตัวละครในเล่ม 2 (เช่น การมอง Manuel เป็น Swineherd vs Holy Redeemer)

### 4. **The Barsoom Series** (วรรณกรรมไซไฟคลาสสิก โดย Edgar Rice Burroughs)
*   **ขนาดข้อมูล:** 2 เล่ม (Vol 1: A Princess of Mars - 28 ตอน, Vol 2: The Gods of Mars - 22 ตอน)
*   **ผลลัพธ์:** ทวนสอบความแม่นยำของการแจ้งเตือนความขัดแย้งข้ามตอน (Consistency Flagging) ตรวจจับความผิดปกติของพล็อตเรื่องจำลอง เช่น การฟื้นคืนชีพของ James K. Powell (Resurrection) และความสัมพันธ์ของ Dejah Thoris ที่เปลี่ยนจากคนรักเป็นศัตรู (Relationship Anomaly)

---

*พัฒนาและดูแลระบบโดย @mgprona — Private Repository*
