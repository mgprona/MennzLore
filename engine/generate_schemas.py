import os
import json
from lore_models import (
    get_architect_schema,
    get_profiler_schema,
    get_chronicler_schema,
    MicroFactsFinal
)

def main():
    schemas_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas")
    os.makedirs(schemas_dir, exist_ok=True)
    
    schemas = {
        "architect.schema.json": get_architect_schema(),
        "profiler.schema.json": get_profiler_schema(),
        "chronicler.schema.json": get_chronicler_schema(),
        "micro_facts_final.schema.json": MicroFactsFinal.model_json_schema()
    }
    
    for filename, schema in schemas.items():
        filepath = os.path.join(schemas_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)
        print(f"Generated and saved schema to: {filepath}")

if __name__ == "__main__":
    main()
