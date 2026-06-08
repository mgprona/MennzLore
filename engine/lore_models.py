"""
Lore Pipeline Pydantic Models (V2)
====================================
Three Pass models + Final Merge model with cross-field validation.
Use .model_json_schema() to generate JSON Schema for Structured Outputs API.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


# =====================================================================
# PASS 1.1: THE ARCHITECT
# =====================================================================

class KeyPlotPoint(BaseModel):
    point_id: str = Field(..., description="รหัสเหตุการณ์ เช่น KPP-001")
    order: int = Field(..., description="ลำดับของเหตุการณ์ในตอน")
    description: str = Field(..., description="สรุปเหตุการณ์สั้นๆ ว่าเกิดอะไรขึ้น")
    characters_involved: List[str] = Field(..., description="รายชื่อตัวละครที่มีส่วนร่วมในเหตุการณ์นี้")
    in_scene_id: str = Field(..., description="รหัสฉากที่เกิดเหตุการณ์นี้ เช่น SC-001")


class SceneDetail(BaseModel):
    scene_id: str = Field(..., description="รหัสฉาก เช่น SC-001")
    order: int = Field(..., description="ลำดับของฉากในตอน")
    location: str = Field(..., description="สถานที่เกิดเหตุ")
    description: str = Field(..., description="สรุปว่าเกิดอะไรขึ้นในฉากนี้")
    visual_details: Optional[str] = Field(None, description="รายละเอียดสภาพแวดล้อม แสง สี หรือสิ่งของรอบๆ")
    mood: str = Field(..., description="โทนอารมณ์ของฉาก เช่น ตึงเครียด, ตลก, ลึกลับ")
    characters_present_in_scene: List[str] = Field(..., description="ตัวละครทั้งหมดที่ปรากฏตัวในฉากนี้")


class ArchitectOutput(BaseModel):
    """Schema สำหรับ Pass 1.1: เน้นจับโครงสร้างฉากและเหตุการณ์หลักเท่านั้น"""
    chapter_id: str = Field(..., description="รหัสตอน เช่น EP002")
    chapter_title: str = Field(..., description="ชื่อตอน")
    key_plot_points: List[KeyPlotPoint]
    scene_details: List[SceneDetail]


# =====================================================================
# PASS 1.2: THE PROFILER
# =====================================================================

class CharacterBehavior(BaseModel):
    character: str = Field(..., description="ชื่อตัวละคร")
    behavior: str = Field(..., description="พฤติกรรมหรือการกระทำที่เด่นชัดในฉาก")
    behavior_type: str = Field(..., description="ประเภทพฤติกรรม เช่น speech, action, reaction, thought")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")


class ItemOfInterest(BaseModel):
    item: str = Field(..., description="ชื่อสิ่งของ/ไอเทมที่น่าสนใจ")
    description: str = Field(..., description="รายละเอียดหรือคุณสมบัติของสิ่งของ")
    role_in_chapter: str = Field(..., description="บทบาทของสิ่งของนี้ในตอน")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")
    owner: Optional[str] = Field(None, description="ผู้ครอบครองสิ่งของนี้ในฉาก (ถ้ามี)")
    location: Optional[str] = Field(None, description="สถานที่ตั้งของสิ่งของนี้ในฉาก (ถ้ามี)")


class CharacterState(BaseModel):
    character: str = Field(..., description="ชื่อตัวละคร")
    state: str = Field(..., description="สถานะของตัวละครในฉาก เช่น active, injured, missing, deceased, transformed")
    description: str = Field(..., description="คำอธิบายสั้นๆ ของสถานะในฉากนี้")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")


class DialogueSummary(BaseModel):
    dialogue_id: str = Field(..., description="รหัสบทสนทนา เช่น DLG-001")
    participants: List[str] = Field(..., description="ผู้ร่วมสนทนา")
    topic: str = Field(..., description="หัวข้อที่คุยกัน")
    summary: str = Field(..., description="สรุปสาระสำคัญของบทสนทนา")
    key_quotes: List[str] = Field(..., description="ประเด็นคำพูดเด็ดๆ หรือเบาะแสที่หลุดมาจากปากตัวละคร")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")


class ProfilerOutput(BaseModel):
    """Schema สำหรับ Pass 1.2: สกัด Data เชิงลึกโดยอิง scene_id จาก Pass 1.1"""
    characters_present: List[str] = Field(..., description="รายชื่อตัวละครทั้งหมดที่พบในตอนนี้ (รวมทุกคน)")
    character_behaviors: List[CharacterBehavior]
    items_of_interest: List[ItemOfInterest]
    character_states: List[CharacterState] = Field(default_factory=list, description="สถานะตัวละครในแต่ละฉาก")
    dialogue_summaries: List[DialogueSummary]


# =====================================================================
# PASS 1.3: THE CHRONICLER
# =====================================================================

class CrossChapterConnection(BaseModel):
    connection_id: str = Field(..., description="รหัสความเชื่อมโยง เช่น CON-001")
    from_entity: str = Field(..., description="เอนทิตีต้นทาง (ตัวละคร/สถานที่/องค์กร)")
    to_entity: str = Field(..., description="เอนทิตีปลายทาง")
    connection_type: str = Field(..., description="ความสัมพันธ์ เช่น meeting, reference, rivalry, object_transfer")
    description: str = Field(..., description="อธิบายความเชื่อมโยงหรือการอ้างอิงข้ามตอน")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")


class LoreDiscovery(BaseModel):
    discovery_id: str = Field(..., description="รหัสการค้นพบ เช่น DSC-001")
    description: str = Field(..., description="ข้อมูลตำนาน เกร็ดประวัติศาสตร์ หรือความลับของโลกที่ถูกเปิดเผย")
    source: str = Field(..., description="แหล่งที่มาของข้อมูล เช่น Chapter text, Character statement")
    evidence_quote: str = Field(..., description="ข้อความในเนื้อเรื่องที่ใช้เป็นหลักฐานประกอบการค้นพบ")
    in_scene_id: str = Field(..., description="ผูกกับรหัสฉากจาก Pass 1.1")


class ChroniclerOutput(BaseModel):
    """Schema สำหรับ Pass 1.3: เชื่อมโยงข้อมูลตอนปัจจุบันเข้ากับ Global Lore"""
    cross_chapter_connections: List[CrossChapterConnection]
    lore_discoveries: List[LoreDiscovery]


# =====================================================================
# PASS 1.4: FINAL MERGED SCHEMA with CROSS-FIELD VALIDATION
# =====================================================================

class MicroFactsFinal(BaseModel):
    """โครงสร้างสมบูรณ์แบบที่รวมทุกอย่างเข้าด้วยกัน พร้อม @model_validator"""
    chapter_id: str = Field(..., description="รหัสตอน เช่น EP002")
    chapter_title: str = Field(..., description="ชื่อตอน")
    key_plot_points: List[KeyPlotPoint]
    scene_details: List[SceneDetail]
    characters_present: List[str]
    character_behaviors: List[CharacterBehavior]
    items_of_interest: List[ItemOfInterest]
    character_states: List[CharacterState] = Field(default_factory=list)
    dialogue_summaries: List[DialogueSummary]
    cross_chapter_connections: List[CrossChapterConnection]
    lore_discoveries: List[LoreDiscovery]
    tags: List[str] = Field(default_factory=list)
    total_events_count: int = Field(default=0, ge=0)
    total_scenes_count: int = Field(default=0, ge=0)
    total_dialogues_count: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def validate_scene_references(self):
        """Cross-field validation: every in_scene_id must reference a real scene.
           Catches hallucinated scene references from LLM output."""
        existing_scenes = {scene.scene_id for scene in self.scene_details}

        for kpp in self.key_plot_points:
            if kpp.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: {kpp.point_id} references scene "
                    f"{kpp.in_scene_id} which doesn't exist. "
                    f"Valid scenes: {existing_scenes}"
                )
        for beh in self.character_behaviors:
            if beh.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: behavior '{beh.character}: {beh.behavior[:30]}' "
                    f"references scene {beh.in_scene_id}"
                )
        for item in self.items_of_interest:
            if item.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: item '{item.item}' references scene {item.in_scene_id}"
                )
        for cs in self.character_states:
            if cs.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: character state '{cs.character}: {cs.state}' "
                    f"references scene {cs.in_scene_id}"
                )
        for dlg in self.dialogue_summaries:
            if dlg.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: dialogue {dlg.dialogue_id} references scene {dlg.in_scene_id}"
                )
        for con in self.cross_chapter_connections:
            if con.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: connection {con.connection_id} references scene {con.in_scene_id}"
                )
        for disc in self.lore_discoveries:
            if disc.in_scene_id not in existing_scenes:
                raise ValueError(
                    f"HALLUCINATION: discovery {disc.discovery_id} references scene {disc.in_scene_id}"
                )
        return self


# =====================================================================
# Helpers: JSON schemas for API
# =====================================================================

def get_architect_schema() -> dict:
    return ArchitectOutput.model_json_schema()

def get_profiler_schema() -> dict:
    return ProfilerOutput.model_json_schema()

def get_chronicler_schema() -> dict:
    return ChroniclerOutput.model_json_schema()
