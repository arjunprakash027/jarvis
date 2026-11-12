---
name: clean-space
description: Inspect Mac disk usage and move explicitly approved old Downloads to Trash with journaled Finder restoration.
---

# Clean space

Inherit base rules and module CLAUDE.md. Use only the predefined session. Engine dispatches nodes and owns gates: never answer, simulate or skip approval. Never use rm, empty Trash or mutate live caches.

## Runtime plan

Use harness task id and absolute task directory as RUN. Check `git check-ignore` accepts every runtime path before writing inventories, original locations, errors, DAGs or journals there. Never commit personal filenames/documents. Write this DAG before execution; validate with `jarvis.dag.check_dag(dag, ['confirm-trash'])` from the repository environment:

```json
{
 "task":"Inspect disk usage and move approved old Downloads to Trash",
 "nodes":[
  {"id":"scan","type":"step","do":"Read-only scan, report coverage and freeze eligible Downloads paths, sizes and identities in ignored inventory.","needs":[]},
  {"id":"show","type":"step","do":"Show informational caches/Finder Trash, permission skips, exact proposed Downloads names/sizes and total; distinguish moved bytes from free space.","needs":["scan"]},
  {"id":"confirm-trash","type":"gate","do":"Move only the exact frozen Downloads candidates shown above to Trash? Caches stay untouched, Trash is not emptied and moving does not immediately reclaim disk space.","needs":["show"]},
  {"id":"trash","type":"step","do":"Revalidate frozen inventory and identities; journal and move only unchanged approved paths using trash.","needs":["confirm-trash"],"undo":"Restore only confirmed journaled moves through Finder to recorded original locations; stop on ambiguity or conflicts, never overwrite."},
  {"id":"verify","type":"test","do":"Verify original disappearance and exact journaled Finder Trash presence; fail on unresolved moves. Report moved bytes separately from independently measured free space.","needs":["scan","trash"],"on_fail":"scan"}
 ]
}
```

Failure returns through engine undo to scan and fresh presentation/approval. Declined gate means no moves; zero candidates does not permit skipping a required gate.

## Read-only scan

Default eligibility: top-level Downloads older than 30 days. Validate any requested replacement age as a nonnegative integer. Reject symlink roots using Python os.lstat. Never follow symlinks, including ancestors, candidate directories or mounts outside the root device. Caches are informational only, never candidates.

```sh
df -k "$HOME"
/usr/bin/find -P "$HOME/Library/Caches" -mindepth 1 -maxdepth 1 -type d -exec /usr/bin/du -skP {} \;
/usr/bin/find -P "$HOME/Downloads" -mindepth 1 -maxdepth 1 -mtime +30 -print0
/usr/bin/osascript -e 'tell application "Finder" to get count of items of trash'
/usr/bin/osascript -e 'tell application "Finder" to get physical size of every item of trash'
```

Capture commands, stdout, stderr and statuses in ignored task files. NUL-delimited paths must never be split on whitespace/newlines. **find can exit zero when nested du fails**; inspect stderr and each measurement. Scan every readable folder; record each inaccessible folder explicitly as `skipped: no permission`, with its path only in runtime reports. Reconcile traversal errors and attempted measurements; do not silently omit subtrees. Show top ten measured cache folders in allocated KiB; partially measured entries are lower bounds, not complete sizes. Unknown size is never zero. Permission skips are honest partial coverage, not a reason to require full cache access. Unexplained errors or unreported omissions still fail. Do not broaden permissions or suppress diagnostics.

Finder Trash count and size are informational. Sum numeric physical sizes; missing values mean unknown entries and a lower-bound total. Never read ~/.Trash with terminal tools. Missing tools or Finder access prevents required reporting and fails tests.

Build manifest using Python os.scandir/os.lstat and os.walk(..., followlinks=False), with onerror collection (never silent traversal errors). Exclude symlink candidates, directories containing symlinks, mounted volumes and unreadable/incompletely measured candidate trees. Record absolute original path, basename, original parent identity, device/inode, mode/type, size, mtime_ns, ctime_ns and equivalent metadata for every directory entry. Sum allocated st_blocks * 512, deduplicating hard links; directory eligibility uses top-level mtime and proposes the entire directory. Record scan timestamp, cutoff, exclusions and permission skips. No caches/Trash may enter candidate list.

Freeze inventory.json and its SHA-256 before the gate:

```sh
shasum -a 256 "$RUN/inventory.json"
```

Show exact escaped names, sizes, total and coverage gaps alongside separate informational cache/Trash groups. Any changed path, metadata, identity or proposed selection requires a new scan/show and fresh engine approval. Never silently add paths or rewrite an approved inventory.

## Finder lookup and trash

Pass filenames as argv, not interpolated AppleScript. Require zero matching Trash basenames before moving; duplicate candidate basenames or existing matches block mutation. After moving require exactly one matching item and record its exact Finder path. Never guess automatic renames.

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

Before any mutation verify digest, all frozen candidate trees, nonsymlink ancestors, parent identities and age eligibility. Recheck immediately before each move; keep sources quiescent. Metadata checks cannot atomically protect against concurrent mutation: if safe association cannot be established, stop. Persist a pending journal record with original path/parent, original identity and expected basename, then:

```sh
/usr/bin/trash "$APPROVED_ABSOLUTE_PATH"
```

Check exit status, original absence using os.path.lexists and exact Finder Trash presence. Record exact Finder Trash path and Finder-visible name, kind, size and modification date; validate association with original metadata, without requiring unchanged ctime after a move. Mark moved only when verified. Interrupted/failed commands may already have moved the item: reconcile pending records before retry or undo. If ambiguity remains, stop for reconciliation rather than guess. No terminal reads of Trash.

## Finder restore undo

Restore only confirmed journaled moves, reverse order. Verify original parent identity and no symlink ancestors; original destination must be absent by os.path.lexists. Check recorded Finder path/properties identify exactly one unchanged item. Ambiguous/missing/changed items or destination conflicts stop rollback and subsequent cleanup. Never restore unrelated Trash items or overwrite.

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

Never add replacing yes or use put away. Journal restored state and verify original location/content. Preserve logs and pending entries on failure.

## Verify and report

Require every approved original absent and exact recorded Finder Trash item present unambiguously. Unresolved pending or partial moves fail verification and trigger engine rollback to scan. Measure df independently. Report moved count/allocated bytes separately from measured free space and partial coverage. Files remain restorable in Trash; moving does not immediately reclaim blocks, and this module never empties Trash.

## Build tests

Run actual read-only reporting for caches, Downloads and Finder Trash. Reconcile every readable folder and explicitly list every inaccessible folder as `skipped: no permission`, including nested du failures despite find exit zero. A test passes with protected folders only when readable coverage and all skips are accounted for. Missing tools, Finder permissions, unexplained errors/unreported omissions fail; do not weaken other tests.

For mutation tests use only a unique disposable fixture in a dedicated mktemp -d directory. Record bytes/hash, original identity and parent; ensure zero Finder Trash name matches. Exercise actual lookup/trash/restore commands above. Verify original disappearance, exact Finder Trash presence, restored original path and unchanged contents/hash, then zero matching Trash items. Leave fixture restored or trash only test-owned leftovers; never empty Trash. Record paths/results only in ignored task files. Never execute real cleanup, move personal Downloads/live caches, simulate a gate or overwrite restore conflicts during build tests.
