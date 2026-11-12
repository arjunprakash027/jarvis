import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isEditToolResult, isWriteToolResult } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";
import * as fs from "node:fs";
import * as path from "node:path";

// Standard module path for every Jarvis module. Loaded from modules/_base/extensions by the harness.
// Task files live in <module>/tasks/<id>/: dag.json, nodes/<x>.json, log.md.

const MARKER = "Write your result JSON to ";

/** Split a path under <module>/tasks/<id>/ into its parts, or undefined if it is elsewhere. */
function taskParts(file: string): { module: string; taskDir: string; rest: string[] } | undefined {
  const parts = path.resolve(file).split(path.sep);
  const at = parts.lastIndexOf("tasks");
  if (at < 1 || at + 2 >= parts.length) return undefined;
  return { module: parts.slice(0, at).join(path.sep), taskDir: parts.slice(0, at + 2).join(path.sep), rest: parts.slice(at + 2) };
}

/** Repo root: the folder above modules/ that holds the module. */
function repoRoot(moduleDir: string): string {
  return path.dirname(path.dirname(moduleDir));
}

function firstSentenceWords(text: string): number {
  const end = text.search(/[.!?](\s|$)/);
  const sentence = end < 0 ? text : text.slice(0, end + 1);
  return sentence.split(/\s+/).filter((w) => w.length > 0).length;
}

/** Return problems with a node result file. */
function checkNode(file: string): string[] {
  let data: any;
  try { data = JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (error) { return [`${file}: not valid JSON (${String(error)})`]; }
  const problems: string[] = [];
  if (typeof data !== "object" || data === null) return [`${file}: must be a JSON object`];
  if (typeof data.ok !== "boolean") problems.push(`${file}: "ok" must be true or false`);
  if (typeof data.output !== "string") problems.push(`${file}: "output" must be a string`);
  else if (firstSentenceWords(data.output.trim()) > 10) problems.push(`${file}: the first sentence of "output" must be 10 words or less`);
  return problems;
}

/** Return problems with dag.json using the engine's own checker. */
function checkDag(file: string, moduleDir: string): string[] {
  const run = spawnSync("uv", ["run", "jarvis", "dag", "check", file], { cwd: repoRoot(moduleDir), encoding: "utf8" });
  if (run.status === 0) return [];
  return [`${file}: jarvis dag check failed:\n${(run.stdout + run.stderr).trim()}`];
}

function latestTask(moduleDir: string): string | undefined {
  const tasks = path.join(moduleDir, "tasks");
  if (!fs.existsSync(tasks)) return undefined;
  const dirs = fs.readdirSync(tasks, { withFileTypes: true }).filter((e) => e.isDirectory() && !e.name.startsWith("."));
  const sorted = dirs.map((e) => ({ name: e.name, time: fs.statSync(path.join(tasks, e.name)).mtimeMs })).sort((a, b) => b.time - a.time);
  return sorted.length ? path.join(tasks, sorted[0].name) : undefined;
}

/** Newest result file for the node (named <id>.json or <id>-<suffix>.json) decides: done, failed or waiting. */
function nodeStatus(taskDir: string, id: string): string {
  const dir = path.join(taskDir, "nodes");
  if (!fs.existsSync(dir)) return "waiting";
  const files = fs.readdirSync(dir)
    .filter((name) => name.endsWith(".json") && (name === `${id}.json` || name.startsWith(`${id}-`)))
    .map((name) => ({ file: path.join(dir, name), time: fs.statSync(path.join(dir, name)).mtimeMs }))
    .sort((x, y) => y.time - x.time);
  if (files.length === 0) return "waiting";
  try {
    const data = JSON.parse(fs.readFileSync(files[0].file, "utf8"));
    return data.ok === true ? "done" : data.ok === false ? "failed" : "waiting";
  } catch { return "waiting"; }
}

function whereReport(moduleDir: string): string {
  const lines = [`module: ${path.basename(moduleDir)}`, `module folder: ${moduleDir}`];
  const task = latestTask(moduleDir);
  if (task === undefined) return [...lines, "task folder: none yet"].join("\n");
  const dag = path.join(task, "dag.json");
  lines.push(`task folder: ${task}`, `dag.json: ${dag}${fs.existsSync(dag) ? "" : " (not written yet)"}`);
  if (fs.existsSync(dag)) {
    try {
      const nodes: any[] = JSON.parse(fs.readFileSync(dag, "utf8")).nodes ?? [];
      for (const node of nodes) lines.push(`  ${node.id}  ${node.type}  ${nodeStatus(task, String(node.id))}`);
    } catch (error) { lines.push(`  dag.json cannot be read: ${String(error)}`); }
  }
  lines.push(`log.md: ${path.join(task, "log.md")}`);
  return lines.join("\n");
}

export default function modulePath(pi: ExtensionAPI): void {
  let resultFile: string | undefined;
  let settleFired = false;

  pi.on("before_agent_start", async (event: any): Promise<void> => {
    settleFired = false;
    resultFile = undefined;
    const prompt: string = String(event.prompt ?? "");
    const at = prompt.indexOf(MARKER);
    if (at < 0) return;
    const rest = prompt.slice(at + MARKER.length);
    const end = rest.indexOf(".json");
    if (end >= 0) resultFile = rest.slice(0, end + 5);
  });

  pi.on("tool_result", async (event, ctx) => {
    if (event.isError || !(isWriteToolResult(event) || isEditToolResult(event))) return undefined;
    const file = path.resolve(ctx.cwd, String(event.input.path ?? ""));
    const where = taskParts(file);
    if (where === undefined) return undefined;
    let problems: string[] = [];
    if (where.rest.length === 1 && where.rest[0] === "dag.json") problems = checkDag(file, where.module);
    else if (where.rest.length === 2 && where.rest[0] === "nodes" && file.endsWith(".json")) problems = checkNode(file);
    if (problems.length === 0) return undefined;
    const report = `Module path check:\n${problems.join("\n")}\nFix this before finishing.`;
    if (ctx.hasUI) ctx.ui.notify(report, "warning");
    return { content: [...event.content, { type: "text" as const, text: report }] };
  });

  pi.on("agent_before_settle", async (event, _ctx) => {
    if (event.outcome !== "completed" || !event.context.canContinue || settleFired || resultFile === undefined) return undefined;
    if (fs.existsSync(resultFile)) return undefined;
    settleFired = true;
    return { continue: true, entries: [{ type: "custom_message" as const, customType: "module-path", display: true, content: `The result file ${resultFile} does not exist yet. Write it now: {"ok": true or false, "output": "short result"}.` }] };
  });

  pi.registerCommand("where", {
    description: "Show this module's task path: DAG, node statuses and files",
    handler: async (_args, ctx): Promise<void> => {
      const report = whereReport(path.resolve(ctx.cwd));
      if (ctx.hasUI) ctx.ui.notify(report, "info");
      pi.sendMessage({ customType: "module-path", display: true, content: report });
    },
  });
}
