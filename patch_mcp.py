import os
import re

SERVER_PATH = r"C:\Users\mennz\MennzLore-fix\mcp_server\server.py"

with open(SERVER_PATH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add import asyncio if not exists
if "import asyncio" not in content:
    content = content.replace("import os\n", "import os\nimport asyncio\n")

# 2. Modify tool definitions to include **kwargs
# We will find all instances of `@mcp.tool()\ndef func_name(args) -> type:`
# and append `, **kwargs` to the arguments.
def inject_kwargs(match):
    full_def = match.group(0)
    if "**kwargs" in full_def:
        return full_def
    
    # Extract everything up to the last closing parenthesis before -> or :
    end_paren_idx = full_def.rfind(")")
    before_paren = full_def[:end_paren_idx]
    after_paren = full_def[end_paren_idx:]
    
    # If the function takes no arguments (e.g. def open_dashboard_tool()), add just **kwargs
    if before_paren.endswith("("):
        return before_paren + "**kwargs" + after_paren
    else:
        return before_paren + ", **kwargs" + after_paren

# Match @mcp.tool() followed by def ... (...)
pattern_kwargs = re.compile(r'@mcp\.tool\(\)\n(?:async )?def [a-zA-Z0-9_]+\([^\)]*\)', re.MULTILINE)
content = pattern_kwargs.sub(inject_kwargs, content)

# 3. For the specific merge_micro_facts tool, make it async and use to_thread to prevent blocking
if "def merge_micro_facts" in content and "async def merge_micro_facts" not in content:
    content = content.replace("def merge_micro_facts(", "async def merge_micro_facts(")
    content = content.replace("result = merge_to_micro_facts(prefix, ep_num, base_dir)", 
                              "result = await asyncio.to_thread(merge_to_micro_facts, prefix, ep_num, base_dir)")

# 4. Make save_global_lore async as well (since it saves files and validates)
if "def save_global_lore(" in content and "async def save_global_lore(" not in content:
    content = content.replace("def save_global_lore(", "async def save_global_lore(")
    content = content.replace("stats = write_global_lore_outputs(project_dir, prefix, result)",
                              "stats = await asyncio.to_thread(write_global_lore_outputs, project_dir, prefix, result)")

with open(SERVER_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("MCP Server patched successfully!")
