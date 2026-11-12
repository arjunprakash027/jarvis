---
name: ego-browser
description: Use the installed ego-browser CLI for Cineworld browser actions; no other browser tools.
---

# Browser CLI

Before any browser action run `ego-browser skill` with bash. Read its entire output, including the final `[ego-browser:skill] end of guide` line; if truncated save it in this task's folder and read in parts. Follow that installed guide as the API authority. Do not install, upgrade, start another browser, or import Playwright. Report an unavailable CLI as a blocker.

Scripts run with `ego-browser nodejs` through bash, for example:

```sh
ego-browser nodejs <<'EOF'
const task = await taskSpace("movies-unique-task-id");
console.log({ spaceId: task.spaceId });
const page = task.page("p1");
await page.goto("https://www.cineworld.ie");
console.log(await page.snapshot());
EOF
```

Record the returned numeric space ID in the task log and use `taskSpace(id)` in later invocations. One space per task, one existing page reused; never touch other tasks' spaces. Variables do not persist between scripts. Node scripts use absolute paths for artifacts. Use current snapshot refs or semantic/CSS selectors. For offscreen controls blocked by the fixed footer, inspect state and scroll over the main content, never force-click. Wait for observable state changes before another action. Only the methods documented by `ego-browser skill` exist.

For current-state screenshots call `page.screenshot({path: absoluteTaskPath})` and read the image before using coordinates. Prefer snapshots/DOM attributes when sufficient. Save only non-sensitive evidence. On sign-in, personal data, human verification, user control or permission prompts stop and report; optional Continue as guest is approved. Use `task.handOff()` when the user must act and resume that same space only after confirmation. At successful completion call `task.finish({keep:[]})` exactly once. No payment or card page, even if a gate says yes.
