# Clean Space Module

Inspect Mac disk usage and safely move explicitly approved old Downloads to Trash. Inherit every rule in modules/_base/CLAUDE.md; the engine owns all gates and this module uses its single predefined session.

## Folder map
- `module.toml`: router settings, session configuration and required confirm-trash gate.
- `skills/clean-space/SKILL.md`: scan, runtime DAG, approval, Trash verification and restoration instructions.
- `extensions/`: reserved for module extensions.
- `tasks/<id>/`: ignored runtime DAGs, inventories, original locations and logs; never commit these or personal filenames/documents.

## Safety rules
- Write each runtime DAG before execution, with a test node and the required engine-owned `confirm-trash` gate. Runtime order: scan -> show -> confirm-trash -> trash -> verify; test failure returns to scan after undo and requires fresh approval. Never answer, skip or simulate gates.
- Scan read-only: cache sizes are informational only; only eligible top-level Downloads older than 30 days by default may be proposed. Report Finder Trash count/size without modifying Trash. Never follow symlinks or touch live app caches. Report inaccessible or unmeasurable paths as partial coverage, never zero bytes.
- Freeze exact candidate paths, sizes and identities before approval. Show names, sizes and proposed total. Move only approved unchanged items; changed identities or additional paths require rescanning and fresh engine approval.
- Use `/usr/bin/trash`, never `rm`. Never empty Trash. Record each move and original location in the ignored task log. Verify approved items left their original locations and are identifiable in Finder Trash.
- Undo through Finder restores only recorded items to original locations. Never overwrite a destination or guess between ambiguous Trash names; stop on unresolved conflicts.
- Report moved bytes separately from measured free space. Moving to Trash does not reclaim disk blocks until Trash is emptied; never promise immediate recovered space.
- Build tests may move only uniquely named disposable fixtures, never personal Downloads or caches. Test actual Trash and Finder restore commands and check restored content and location. Missing tools or required permissions mean failure, not a simulated success.
