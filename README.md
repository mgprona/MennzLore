# MennzLore

ระบบสกัด **lore** จากนิยาย/ซีรีส์ → โครงสร้างข้อมูลที่ค้นหา วัด และเรนเดอร์เป็นแผนที่ได้

> นิยาม: เปลี่ยน raw text (transcript / e-book) ให้กลายเป็น *surveyable fictional world* — 
> master lorebook, character arc, timeline, foreshadowing, image prompts, และแผนที่ภูมิศาสตร์

---

## ฟีเจอร์หลัก (Key Features)

1. **Clean/Refactored Canonical Engine:** โค้ดทั้งหมดได้รับการ Refactor ให้แยกส่วนและเป็นระเบียบตามหลัก PEP-8 ย้ายฟังก์ชันย่อยที่ซ้ำซ้อนมารวมกันที่ `engine/utils.py` เพื่อการบำรุงรักษาง่ายในอนาคต
2. **Phase 3.2 Name Verification:** เครื่องมือสแกนตรวจสอบความสอดคล้องสะกดชื่อใน Name Map กับเนื้อเรื่องดิบเพื่อหาตัวละครที่ไม่มีอยู่จริง ป้องกันความผิดพลาดของ LLM
3. **Model Context Protocol (MCP) Server:** แปลงระบบสกัด Lore ทั้งหมดให้อยู่ในรูปของ **MCP Server** พัฒนาขึ้นโดยใช้ `fastmcp` ทำให้ AI Client (เช่น Claude Desktop หรือ Cursor) สามารถเรียกใช้งานเครื่องมือวิเคราะห์และเข้าถึงทรัพยากร (Schemas/Examples) ของระบบได้โดยตรง

---

## โครงสร้างโฟลเดอร์ (Directory Structure)

```text
MennzLore/
├── engine/                       # Python deterministic — canonical
│   ├── utils.py                  # ฟังก์ชันตัวช่วยส่วนกลาง (JSON, Name/Location normalization)
│   ├── lore_models.py            # Pydantic schemas + cross-field validation (กัน hallucination)
│   ├── verify_names.py           # Phase 3.2 — ตรวจสอบความถูกต้องและสอดคล้องของชื่อตัวละคร
│   ├── merge_to_micro_facts.py   # Phase 4 — รวม 3-pass output → micro_facts/*.json
│   ├── assemble_generic.py       # Phase 7 — ประกอบ master_lorebook_full.md
│   ├── assemble_production_generic.py  # Phase 9 — image prompts + shot list
│   └── chart_render_generic.py   # Phase 10 — แผนที่ SVG + route network
├── mcp_server/                   # ระบบเชื่อมต่อ Model Context Protocol (MCP)
│   └── server.py                 # FastMCP Server ลงทะเบียนเครื่องมือ คำสั่ง และทรัพยากรทั้งหมด
├── prompts/                      # แกน LLM (Phase 1-6)
│   ├── pass11_architect_prompt.md    # ฉาก + เหตุการณ์หลัก
│   ├── pass12_profiler_prompt.md     # ตัวละคร + พฤติกรรม + ไอเทม + บทสนทนา
│   ├── pass13_chronicler_prompt.md   # เชื่อมข้ามตอน + lore discoveries
│   ├── pass2_sliding_window_prompt.md
│   ├── sa_combined_prompt.md
│   └── sa_lore_prompt.md
├── schemas/                      # JSON Schema (gen จาก lore_models) — สำหรับ Structured Outputs API
│   ├── architect.schema.json
│   ├── profiler.schema.json
│   ├── chronicler.schema.json
│   └── micro_facts_final.schema.json
├── templates/                    # goal templates สำหรับ delegate_task (sub-agent)
├── examples/                     # ตัวอย่าง output จริง (1 ตอน) เป็น reference
└── docs/
    ├── PIPELINE.md               # playbook ทีละ phase (Phase 1-10)
    ├── ENGINE.md                 # CLI reference ของ engine scripts
    └── MCP_DESIGN.md             # แผนแปลง pipeline → MCP server
```

---

## Model Context Protocol (MCP) Integration

ระบบได้รับการติดตั้งเซิร์ฟเวอร์สื่อสาร MCP ผ่าน `fastmcp` ซึ่งเตรียมคำสั่ง (Prompts), แหล่งอ้างอิง (Resources) และเครื่องมือ (Tools) สำหรับให้ AI นำไปวิเคราะห์งานประพันธ์ได้อัตโนมัติ

### เครื่องมือที่ให้บริการ (Exposed Tools)
*   `verify_character_names(project_dir, prefix)`: ตรวจสอบรายชื่อตัวละครใน Name Map เทียบกับข้อความดิบ
*   `merge_micro_facts(prefix, ep_num, base_dir)`: รวมผลลัพธ์การดึงข้อมูล 3-Pass (Architect, Profiler, Chronicler) เข้าเป็นไฟล์เดียวต่อ 1 ตอน พร้อมเช็กความเข้ากันของข้อมูลด้วย Pydantic
*   `assemble_lorebook_tool(project_dir, prefix)`: รวบรวมข้อมูลไมโครแฟกต์ทุกตอนมาสร้างสารานุกรมรวมเล่ม Markdown ไฟล์เดียว
*   `render_production_tool(project_dir, prefix)`: เจนชุดข้อมูลคิวกล้อง มุมถ่ายภาพยนต์ และ Image Prompts สำหรับสร้างสื่อต่อยอด
*   `render_map_tool(project_dir, prefix)`: คำนวณพิกัดจำลองและสร้างไฟล์แผนที่เส้นทางการเดินทางของตัวละครในรูปแบบไฟล์เวกเตอร์ SVG

### โครงสร้างควบคุมความถูกต้อง (Exposed Resources)
*   `schema://architect`: โครงสร้างข้อมูลสกัดฉากหลัก
*   `schema://profiler`: โครงสร้างข้อมูลสกัดพฤติกรรมตัวละครและวัตถุเด่น
*   `schema://chronicler`: โครงสร้างข้อมูลเชื่อมข้ามตอน
*   `schema://micro_facts_final`: สคีมาควบคุมความถูกต้องของไฟล์ไมโครแฟกต์สมบูรณ์
*   `example://micro_facts`: ตัวอย่างไฟล์ผลลัพธ์ที่เป็นรูปธรรม

### ชุดคำสั่งวิเคราะห์ (Exposed Prompts)
*   `analyze_architect`, `analyze_profiler`, `analyze_chronicler`
*   `synthesize_window`, `sa_combined`, `sa_lore`

---

## วิธีการติดตั้งและรันใช้งาน (Installation & Usage)

### 1. ติดตั้งความต้องการของระบบ
ให้ติดตั้งไลบรารี Python ในสภาพแวดล้อมเสมือนของคุณ (Virtual Environment):
```bash
pip install -r requirements.txt
```

### 2. นำไปเชื่อมต่อกับ Claude Desktop
เปิดไฟล์ตั้งค่าคอนฟิกูเรชันของ Claude Desktop (`%APPDATA%/Claude/claude_desktop_config.json`) และเพิ่มตั้งค่า MCP Server นี้เข้าไป:
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
*(หมายเหตุ: ให้เปลี่ยน Absolute Path ให้ตรงกับพิกัดโฟลเดอร์จริงบนเครื่องของคุณ)*

### 3. รันระบบแบบ CLI ทั่วไป
คุณยังสามารถรัน Engine ต่าง ๆ แบบ deterministic ผ่าน CLI ได้เช่นเดิม:
```bash
python engine/verify_names.py                <project_dir> [prefix]
python engine/assemble_generic.py            <project_dir> [prefix]
python engine/assemble_production_generic.py <project_dir> [prefix]
python engine/chart_render_generic.py        <project_dir> [prefix]
```

---

*Maintained by @mgprona — private*
