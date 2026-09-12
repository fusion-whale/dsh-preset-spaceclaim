/**
 * Smoke test for the bundled dsh-plugin-spaceclaim package.
 *
 * Structural checks always run: exports, tool definition shape, YAML validity.
 * With --live it also drives the tool for real (one SpaceClaim build + verify).
 *
 *   node test/smoke.mjs [--live]
 */
import { mkdirSync, copyFileSync, rmSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const BUNDLE = resolve(HERE, "..");
const PLUGIN_ENTRY = join(BUNDLE, "spaceclaim", "plugin", "lib", "index.js");

let failures = 0;
function check(label, condition, detail) {
	console.log(`${condition ? "  ok  " : "  FAIL"}  ${label}${detail !== undefined ? `  -> ${detail}` : ""}`);
	if (!condition) failures += 1;
}

console.log("== bund" + "le layout ==");
for (const rel of [
	"spaceclaim/preset.yml",
	"spaceclaim/agent.cordis.yml",
	"spaceclaim/install.ps1",
	"spaceclaim/plugin/package.json",
	"spaceclaim/plugin/lib/index.js",
	"spaceclaim/plugin/scripts/Invoke-Scdm.ps1",
	"spaceclaim/plugin/scripts/scdm_lib.py",
	"spaceclaim/plugin/scripts/verify_model.py",
	"spaceclaim/skills/spaceclaim-modeling/SKILL.md"
]) {
	check(rel, existsSync(join(BUNDLE, rel)));
}

console.log("== YAML validity ==");
const yaml = await import(pathToFileURL(join(BUNDLE, "spaceclaim", "node_modules", "js-yaml", "index.js")).href)
	.catch(() => null);
if (yaml === null) {
	check("js-yaml available (needs the node_modules junction)", false, "run install.ps1 first");
} else {
	const { readFileSync } = await import("node:fs");
	// The composition uses the harness's custom `!!js` tag for disabled-gate
	// expressions; plain js-yaml has no such type, so teach it one that keeps the
	// scalar as a string instead of failing the whole document.
	const harnessSchema = yaml.DEFAULT_SCHEMA.extend([
		new yaml.Type("tag:yaml.org,2002:js", { kind: "scalar", construct: (data) => data })
	]);
	for (const rel of ["spaceclaim/preset.yml", "spaceclaim/agent.cordis.yml"]) {
		try {
			const doc = yaml.load(readFileSync(join(BUNDLE, rel), "utf8"), { schema: harnessSchema });
			const rows = Array.isArray(doc) ? doc.length : 0;
			check(`${rel} parses`, true, Array.isArray(doc) ? `${rows} rows` : "mapping");
			if (rel.endsWith("agent.cordis.yml")) {
				const mine = doc.filter((row) => row && row.id === "tool-spaceclaim");
				check("composition carries the tool-spaceclaim row", mine.length === 1,
					mine.length === 1 ? mine[0].name : "missing");
				if (mine.length === 1) {
					// A row name starting with "." is kind=preset: resolved against the preset directory.
					const resolved = join(BUNDLE, "spaceclaim", mine[0].name);
					check("row specifier resolves inside the preset", existsSync(resolved), mine[0].name);
				}
			}
		} catch (error) {
			check(`${rel} parses`, false, String(error.message ?? error));
		}
	}
}

console.log("== plugin module ==");
const plugin = await import(pathToFileURL(PLUGIN_ENTRY).href);
check("exports name", plugin.name === "tool-spaceclaim", plugin.name);
check("exports inject", Array.isArray(plugin.inject) && plugin.inject.includes("tools"), JSON.stringify(plugin.inject));
check("exports apply", typeof plugin.apply === "function");

let captured;
plugin.apply({ tools: { register(tool) { captured = tool; } } });
check("registers exactly one tool", captured !== undefined);
if (captured) {
	check("tool name", captured.name === "scdm_build", captured.name);
	check("has description", typeof captured.description === "string" && captured.description.length > 100,
		`${captured.description?.length ?? 0} chars`);
	check("parameters is an object schema", captured.parameters?.type === "object");
	// defineTool compiles the implicit property map into raw JSON Schema, where
	// requiredness becomes an array on the object rather than `required: true`
	// on each property.
	check("script is required", captured.parameters?.required?.includes("script") === true,
		JSON.stringify(captured.parameters?.required));
	check("out is required", captured.parameters?.required?.includes("out") === true);
	check("verify is optional boolean", captured.parameters?.properties?.verify?.type === "boolean");
	check("timeout_sec is optional integer", captured.parameters?.properties?.timeout_sec?.type === "integer");
	check("output schema present", captured.output?.schema?.type === "object");
	check("output render is callable", typeof captured.output?.render === "function");
	check("execute is callable", typeof captured.execute === "function");
}

if (process.argv.includes("--live") && captured) {
	console.log("== live run (spaceclaim build + verify) ==");
	const scratch = join(BUNDLE, "_smoke_run");
	rmSync(scratch, { recursive: true, force: true });
	mkdirSync(scratch, { recursive: true });
	const script = join(scratch, "selftest_box.py");
	copyFileSync(join(BUNDLE, "spaceclaim", "skills", "spaceclaim-modeling", "tests", "selftest_box.py"), script);
	const out = join(scratch, "selftest_box.scdocx");

	const started = Date.now();
	const value = await captured.execute({ script, out, verify: true }, { signal: undefined });
	const seconds = ((Date.now() - started) / 1000).toFixed(1);
	console.log(`  (took ${seconds}s, exit_code=${value.exit_code})`);
	console.log(value.output.split("\n").map((line) => `      ${line}`).join("\n"));

	check("status ok", value.status === "ok", value.status);
	check("artifact reported", typeof value.artifact === "string" && value.artifact.endsWith(".scdocx"), value.artifact);
	check("artifact on disk", existsSync(out));
	check("verify report captured", typeof value.verify_report === "string" &&
		value.verify_report.includes("body[0] size = 6.000 x 5.000 x 20.000 mm"));
	check("named selections read back", typeof value.verify_report === "string" &&
		value.verify_report.includes("inlet") && value.verify_report.includes("wall"));
}

console.log("");
console.log(failures === 0 ? "SMOKE: all checks passed" : `SMOKE: ${failures} check(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
