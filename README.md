# 📚 MennzLore: Fictional Lore Extraction Engine & MCP Server

> **MennzLore** คือระบบสกัดและวิเคราะห์ **Lore** (ตำนาน ประวัติศาสตร์ พจนานุกรม และความสัมพันธ์) จากงานประพันธ์ประเภท นิยาย บทภาพยนตร์ หรือซีรีส์ดิบ แปลงให้อยู่ในรูปของโครงสร้างข้อมูล (Structured Data) ที่สามารถค้นหา วิเคราะห์จุดเชื่อมโยง (Foreshadowing) และเรนเดอร์ออกมาเป็น **แผนที่ SVG ทางภูมิศาสตร์การเดินทาง** รวมถึง **ชุดคิวกล้องถ่ายทำ (Shot List)** และ **Image Prompts** ได้อย่างเป็นระบบ

---

## 🛠️ โครงสร้างทางสถาปัตยกรรม (System Architecture)

ระบบแยกส่วนการทำงานออกเป็น 3 ชั้น เพื่อความสะอาดและสะดวกรวมศูนย์ (Single Source of Truth) ดังนี้:

*   **1. Deterministic Engine (`engine/`):** สคริปต์ Python ที่ใช้ประมวลผลข้อมูล ดึงพจนานุกรม จัดระเบียบสถานที่ วาดแผนที่ และประกอบเป็นสรุปรวมเล่ม Markdown
*   **2. LLM Core (`prompts/` & `schemas/`):** ชุดคำสั่งที่ใช้จัดระเบียบความคิดของ AI และ JSON Schemas สำหรับควบคุม Structured Outputs ป้องกันการป้อนข้อมูลที่หลุดกรอบ
*   **3. Communication Bridge (`mcp_server/`):** ตัวเซิร์ฟเวอร์เชื่อมโยงการทำงานผ่านโปรโตคอล **Model Context Protocol (MCP)** เพื่อคุยกับ AI Client

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
| **Phase 10** | Spatial Render | **Engine (spatial)** | `output/spatial/` (แผนที่เส้นทางเดินตัวละคร SVG & Coords) |

---

## 💎 จุดเด่นที่ได้รับการปรับปรุงใหม่ (Clean Refactoring Highlights)

1.  **รวมศูนย์ฟังก์ชันตัวช่วย (`engine/utils.py`):** ย้าย Logic ซ้ำซ้อนเกี่ยวกับการอ่าน-เขียนไฟล์ JSON และตัวกรองคำอ่านชื่อตัวละคร/สถานที่ (`normalize_name`, `normalize_location`) ไปอยู่จุดเดียว
2.  **แก้บั๊ก Unicode Crash บน Windows (CP874 Thai):** ลบสัญลักษณ์ขีดกรอบลายเส้น Unicode (`\u2500` หรือ `─`) ในการแสดงผล log ออกทั้งหมด และเปลี่ยนมาใช้ขีด ASCII มาตรฐาน (`---`, `===`) ทำให้สคริปต์ไม่แครชบนระบบปฏิบัติการ Windows ที่ใช้การแสดงภาษาไทย
3.  **การป้องกันข้อมูลลวงตา (Hallucination Control):** ใช้การตรวจรับข้อมูลแบบ Cross-field validation บน Pydantic V2 ใน `engine/lore_models.py` โดยระบบจะบล็อกทันทีหากตรวจพบว่า AI ป้อนรหัสฉาก (`in_scene_id`) อ้างอิงไปยังฉากที่ไม่มีอยู่จริงในตอนนั้น ๆ

---

## 🚀 Model Context Protocol (MCP) Server Playbook

ระบบมาพร้อมเซิร์ฟเวอร์ MCP ที่ช่วยแปลงระบบวิเคราะห์วรรณกรรมให้กลายเป็น **เครื่องมือสำหรับ AI Client** (เช่น Claude Desktop หรือ Cursor) สามารถเรียกประมวลผลเนื้อหาได้จากห้องแชต

### วิธีติดตั้งลงใน Claude Desktop
แก้ไขไฟล์ตั้งค่าคอนฟิก `claude_desktop_config.json` (พิกัดปกติอยู่ที่ `%APPDATA%/Claude/` บน Windows):

```json
{
  "mcpServers": {
    "mennz-lore": {
      "command": "python",
      "args": [
        "C:/Users/mennz/.gemini/antigravity/scratch/MennzLore/mcp_server/server.py"
      ]
    }
  }
}
```

### รายการเครื่องมือที่พร้อมให้บริการ (Exposed Tools)

1.  **`verify_character_names`**
    *   *หน้าที่:* เปรียบเทียบไฟล์ Name Map กับเนื้อเรื่องดิบเพื่อหาชื่อตัวละครที่สะกดผิดหรือไม่มีอยู่จริงในนิยาย
2.  **`merge_micro_facts`**
    *   *หน้าที่:* รวมไฟล์ผลลัพธ์จากการวิเคราะห์ 3-Pass (Architect, Profiler, Chronicler) ของตอนนั้น ๆ พร้อมรัน Pydantic เพื่อ Validate ความถูกต้องของความสัมพันธ์
3.  **`assemble_lorebook_tool`**
    *   *หน้าที่:* ประมวลผลจากโฟลเดอร์ผลลัพธ์รายตอนมาสร้างสารานุกรมรวมเล่ม Markdown เล่มเดี่ยว
4.  **`render_production_tool`**
    *   *หน้าที่:* สร้างช็อตกล้องถ่ายหนัง (Shot Lists) และ Prompt เจนภาพสวยงามสำหรับแต่ละฉากเด่น
5.  **`render_map_tool`**
    *   *หน้าที่:* สร้างพิกัดและวาดเส้นทางการเดินทางของตัวละครเป็นแผนที่เวกเตอร์กราฟิก (SVG)

---

## 📊 ตัวอย่างการใช้งานและทวนสอบจริง (Validation Showcase)

เราได้ทำการทดสอบระบบแบบ **ทีละขั้นตอน (Phase-by-Phase)** กับวรรณกรรมเรื่อง **"The Time Machine"** ของ **H. G. Wells** (ความยาวรวม 8 ตอน) สำเร็จลุล่วงอย่างไร้ข้อผิดพลาด:

### 1. โครงสร้างโฟลเดอร์ของโปรเจกต์งานเขียน (Project Layout)
เมื่อเราสร้างผลงานขึ้นมา ระบบจะจัดเก็บไฟล์อย่างเป็นระบบแยกจาก Repo หลัก ดังนี้:
```text
time-machine-project/
├── raw/                      # ไฟล์ต้นฉบับบทดิบ tm_EP001.txt - tm_EP008.txt
├── analysis/sa_raw/          # ข้อมูลวิเคราะห์ดิบ 3-Pass
├── micro_facts/              # ไฟล์ไมโครแฟกต์สมบูรณ์ (ผ่านการคัดกรอง Pydantic)
├── verification/             # ตัวสะกดชื่อตัวละครและแผนการดำเนินเนื้อเรื่อง
│   ├── tm_name_map.json
│   └── tm_global_lore.json
└── output/                   # ผลผลิตสุดท้าย
    ├── tm_master_lorebook_full.md  # สารานุกรมรวมเล่มสมบูรณ์
    ├── production/           # คิวกล้องและ Prompt รูปภาพ
    └── spatial/              # แผนที่ SVG และข้อมูลภูมิศาสตร์จำลอง
```

### 2. ผลการสแกนชื่อตัวละคร (verify_character_names):
ระบบสแกนเอกสารดิบทั้ง 8 ตอนเพื่อเทียบกับแผนผังรายชื่อ 11 คนหลักในทันที:
*   สแกนพบตัวละครครบถ้วน **(0 Missing Characters)**
*   รายงานพบความถี่การปรากฏตัวเด่นชัด เช่น *The Time Traveller* ปรากฏตัว 176 ครั้ง, *Weena* ปรากฏ 54 ครั้ง, และ *Hillyer* ปรากฏ 1 ครั้ง

### 3. ผลผลิตสำเร็จรูป (Generated Output):
*   **[Master Lorebook](file:///C:/Users/mennz/.gemini/antigravity/scratch/time-machine-project/output/tm_master_lorebook_full.md):** รวบรวมข้อมูลสรุป ตัวละคร เหตุการณ์ และรายละเอียดของสถานที่ ผลิตขึ้นมาเป็นเอกสารรวมเล่มขนาด 13.5 KB อย่างสวยงาม
*   **[แผนที่จำลองเดินทาง SVG](file:///C:/Users/mennz/.gemini/antigravity/scratch/time-machine-project/output/spatial/chart_map_skeleton.svg):** คำนวณความใกล้ไกลของฉากต่าง ๆ ในอนาคต (เช่น ห้องทดลอง Richmond, ลาน Sphinx, และแม่น้ำตื้น) วาดออกมาเป็นแผนที่เวกเตอร์ความละเอียดสูงพร้อมนำไปใช้งานต่อ

---

*พัฒนาและดูแลระบบโดย @mgprona — Private Repository*
