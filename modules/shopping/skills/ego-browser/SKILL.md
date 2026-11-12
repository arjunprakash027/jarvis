---
name: ego-browser
description: Operate any shop website using the installed ego-browser CLI, without a browser MCP server or global skill.
---

# ego-browser CLI

Before browser work run `ego-browser skill` with bash and read its complete output (save to a temporary file and read in parts if truncated). It is the installed version's authoritative API guide. Do not install/upgrade anything without approval. Do not use Playwright or another browser.

Run scripts through bash:

```sh
ego-browser nodejs <<'EOF'
const task = await taskSpace("shopping task");
const page = task.page("p1");
await page.goto("https://www.example-shop.com");
console.log({spaceId: task.spaceId});
console.log(await page.snapshot({scope: "full_page"}));
EOF
```

Each invocation is a fresh Node process; browser space/page labels persist. Resume with `taskSpace(numericId)` in subsequent calls. Use exactly one space per request. Use snapshots for observed product names and refs; `page.click('@123')` or `page.click('loc=css:button[aria-label="exact label"]')` acts on a unique match. Wait for observed conditions with `waitForSelector` or `waitForFunction`, then inspect state before retrying. Browser DOM code belongs inside `page.evaluate`, not the Node script. Never print credentials, cookies, payment fields or tokens.

If login is needed, call `task.handOff()` and report the blocker. Do not enter credentials or reclaim user control without confirmation. After confirmed sign-in use `takeOverTaskSpace(id)` in that same space. On successful cleanup call `task.finish({keep:[]})` exactly once. Read the `shopping` skill for the process and the strict pre-payment boundary.
