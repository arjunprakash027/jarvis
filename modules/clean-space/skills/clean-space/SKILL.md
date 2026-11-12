---
name: clean-space
description: Inspect Mac disk usage and move only approved old Downloads to Trash with safe Finder restoration.
---

# Clean space

Inherit base rules and CLAUDE.md. Use only the configured single session. Engine owns every gate; never answer, skip or simulate approval. Never use rm or empty Trash. Caches are informational only, not cleanup candidates.

## Runtime DAG and records

Use the harness task id. Keep all inventories, original paths, metadata, errors and move journals in ignored `tasks/<id>/` files. Confirm each file is ignored with `git check-ignore` before storing personal paths; never commit local inventories/documents. Write the DAG before execution and validate it with `jarvis.dag.check_dag(dag, ['confirm-trash'])` from the repository environment. Write spec.md too for long tasks.

```json
{
  "task":"Inspect disk usage and move approved old Downloads to Trash",
  "nodes":[
    {"id":"scan","type":"step","do":"Read-only scan; freeze eligible paths, sizes, identities, coverage errors in ignored task inventory.","needs":[]},
    {"id":"show","type":"step","do":"Show informational caches and Finder Trash, exact proposed Downloads names/sizes and total, coverage gaps and no immediate reclaimed space.","needs":["scan"]},
    {"id":"confirm-trash","type":"gate","do":"Move only the frozen Downloads candidates shown above to Trash? No caches will move, Trash will not be emptied, and this does not immediately free disk blocks.","needs":["show"]},
    {"id":"trash","type":"step","do":"Revalidate frozen manifest and identities, journal moves, use /usr/bin/trash only for approved unchanged paths.","needs":["confirm-trash"],"undo":"Restore only confirmed journaled moved items through Finder; stop on ambiguity or destination conflicts; never overwrite."},
    {"id":"verify","type":"test","do":"Verify original absence and exact Finder Trash presence for all approved items, reconcile pending moves, report moved bytes separately from free space; fail on unresolved results.","needs":["scan","trash"],"on_fail":"scan"}
  ]
}
```

Failure requires engine undo then new scan/show and fresh approval. No new paths after approval. Changed identities require a fresh manifest and gate. Declined gate means no moves; zero candidates never authorizes skipping a gate.

## Read-only scan

Use macOS commands below, after rejecting symlinked Downloads/Caches roots using `os.lstat`. Set RUN to the absolute harness task folder. Default age is 30 days; validate requested ages as nonnegative integers before replacing +30. Never follow symlinks.

```sh
df -k "$HOME"
/usr/bin/find -P "$HOME/Library/Caches" -mindepth 1 -maxdepth 1 -type d -exec /usr/bin/du -skP {} \;
/usr/bin/find -P "$HOME/Downloads" -mindepth 1 -maxdepth 1 -mtime +30 -print0
/usr/bin/osascript -e 'tell application "Finder" to get count of items of trash'
/usr/bin/osascript -e 'tell application "Finder" to get physical size of every item of trash'
```

Capture each stdout/stderr and status in ignored files. **find can exit zero while an invoked du fails. Inspect stderr, not just outer exit status.** Permission/size errors mean partial/unknown coverage, never zero bytes. Show largest ten measured cache folders, labelled allocated KiB, informational only. NUL-delimited Downloads paths must not be split on whitespace/newlines. Sum numeric Finder physical sizes; missing values mean a lower bound with unknown entries. Do not access ~/.Trash from the terminal. Missing required tools or permissions fail build tests; retain cache permission failures even if the outer find exits zero. Do not suppress errors, reduce test scope or claim permissions were fixed by changing instructions.

Create a JSON manifest using Python `os.scandir`, `os.lstat`, and `os.walk(..., followlinks=False)`. Only old top-level Downloads are eligible. Exclude symlink candidates, candidates containing nested symlinks, mounted volumes, unreadable trees and unknown measurements. Record original absolute path and parent identity, basename, device/inode, mode/type, size, mtime_ns, ctime_ns and equivalent metadata for every tree entry. Sum allocated st_blocks * 512, avoiding hard-link double counting; note directory candidates move as a whole and eligibility uses their top-level mtime. Record timestamp, cutoff, errors and exclusions.

Freeze inventory.json and its digest (`shasum -a 256 "$RUN/inventory.json"`) before approval. Show escaped names, individual sizes, proposed total and all coverage gaps. Include cache/Trash informational groups separately. Never change the approved manifest or add candidates silently.

## Finder identity lookup

Use argv, never filename interpolation in AppleScript. This lookup returns exact matching Finder Trash paths. Require zero matches before moving a basename, exactly one afterward; multiple matches are a blocker, not a guess.

```sh
/usr/bin/osascript - "$NAME" <<'APPLESCRIPT'
on run argv
  set itemName to item 1 of argv
  tell application "Finder"
    set matches to every item of trash whose name is itemName
    set paths to {}
    repeat with entry in matches
      set end of paths to POSIX path of (entry as alias)
    end repeat
    return paths
  end tell
end run
APPLESCRIPT
```

Before any move verify frozen digest, all candidate tree identities, nonsymlink ancestors and current eligibility. Reject duplicate basenames or existing Trash name matches; never guess Finder rename behavior. Check again immediately before each move. Metadata checks are not atomic protection against concurrent changes: if the source cannot be kept quiescent, stop. Changes require new scan/show/approval.

Persist a write-ahead journal with original path, parent identity, original metadata and status pending. Then run:

```sh
/usr/bin/trash "$APPROVED_ABSOLUTE_PATH"
```

Check command status, original absence (`os.path.lexists`) and one exact new Finder Trash item. Record Finder POSIX Trash path and Finder-visible name/kind/size/modification date, status moved, and enough evidence to distinguish this item. Do not require unchanged ctime after a move. If Finder identity/content association cannot be verified, stop for reconciliation. Never inspect Trash with terminal tools. An interrupted or failing command may have moved the file: reconcile pending entries before retry or undo, never blindly repeat.

## Finder restore / undo

Restore confirmed journaled items only, reverse move order. Verify original parent identity, no symlink ancestors, and `os.path.lexists(original_path)` false. Check the exact recorded Finder Trash item still uniquely matches its saved properties; stop on ambiguity. Use original basename, recorded Trash path and original parent via argv:

```sh
/usr/bin/osascript - "$NAME" "$RECORDED_TRASH_PATH" "$ORIGINAL_PARENT" <<'APPLESCRIPT'
on run argv
  set itemName to item 1 of argv
  set expectedPath to item 2 of argv
  set parentPath to item 3 of argv
  tell application "Finder"
    set matches to every item of trash whose name is itemName
    if (count of matches) is not 1 then error "Ambiguous or missing Trash item"
    set targetItem to item 1 of matches
    if (POSIX path of (targetItem as alias)) is not expectedPath then error "Trash identity path changed"
    set destinationFolder to (POSIX file parentPath) as alias
    if exists item itemName of destinationFolder then error "Restore destination exists"
    move targetItem to destinationFolder
  end tell
end run
APPLESCRIPT
```

Never add replacing yes or use Finder put away. Never overwrite a destination, guess between names or restore unrelated items. Stop on conflicts and preserve logs; do not begin another cleanup while rollback is incomplete. Journal restoration and verify original location/content.

## Verification and reporting

Verify each approved original is absent and its exact recorded Finder Trash item is present. Missing/ambiguous or unresolved pending entries fail verification and trigger engine rollback to scan. Measure `df -k "$HOME"` independently. Report moved count and allocated bytes separately from measured free space and partial coverage. State that files remain restorable in Trash and moving them does not reclaim disk blocks until Trash is emptied; this module never empties it.

## Build-only tests

Run scan commands for real; report caches, Downloads and Finder Trash honestly. Missing required tools or permissions fail the test, including nested du permission errors. This build previously encountered cache permission denials: do not claim this skill rewrite resolves them or weaken the test.

Use only a unique disposable fixture under a dedicated `mktemp -d` directory for mutation tests. Record known bytes/hash, original identity/parent and preflight zero Finder Trash matches. Exercise the exact trash/lookup/restore commands above: original disappears, exact Finder Trash item appears, restore returns original path with unchanged content/hash, matching Trash item then disappears. Leave fixture restored or move only test-owned leftovers to Trash; never empty it. Record paths/results in ignored runtime files. Never execute real cleanup, simulate approval, move user Downloads/live caches or overwrite restore conflicts during build tests.
