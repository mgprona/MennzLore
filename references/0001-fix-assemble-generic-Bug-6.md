Bug #6 fix — engine/assemble_generic.py

The full file (40,540 chars) exceeds the GitHub MCP create_or_update_file
limit (~25KB), so the patch is included here as a V4A-format patch file.
Apply locally with `git apply 0001-fix-assemble-generic-Bug-6.patch`
to replace the sys.exit(1) with raise FileNotFoundError on line 361-363.

When that block is replaced, Phase 7 (assemble_lorebook) will return a
fast [ERROR] message through the MCP tool wrapper instead of timing
out at 120s when micro_facts/ is missing.

--- DIFF ---

```diff
--- a/engine/assemble_generic.py
+++ b/engine/assemble_generic.py
@@ -359,8 +359,14 @@ def assemble_lorebook(project_dir, prefix, prior_lore_context: str = None):
 
     all_eps = sorted(mf_files.keys())
     if not all_eps:
-        print("No micro_facts files found")
-        sys.exit(1)
+        # Raise instead of sys.exit(1) so the MCP tool wrapper sees a normal
+        # exception and returns a fast [ERROR] message. Calling sys.exit()
+        # inside an MCP tool would propagate a SystemExit that the wrapper
+        # does not catch, causing the call to spin until the MCP timeout.
+        raise FileNotFoundError(
+            f"No micro_facts files found in {MF_DIR}. Run Phase 4 (3-Pass "
+            f"analysis + merge) before Phase 7 (assemble)."
+        )
     print(f"Found: {len(all_eps)} micro_facts, {len(p2_files)} pass2 batches")
 
     p1data = {}
```
