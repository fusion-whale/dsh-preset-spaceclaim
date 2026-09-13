/**
 * dsh-plugin-spaceclaim — model-facing tools for headless Ansys SpaceClaim modelling.
 *
 * Registers one native tool, `scdm_build`, that runs the verified SpaceClaim
 * command-line path shipped in this package under `scripts/` and judges the run
 * by the runner's success sentinel rather than by an exit code.
 *
 * The tool shells out to PowerShell running `scripts/Invoke-Scdm.ps1`, which
 * composes the model script with `scripts/scdm_lib.py` and calls:
 *   SpaceClaim.exe /RunScript="<script.py>" /ScriptOutput="<log>" /Headless=True /ExitAfterScript=True
 *
 * @module dsh-plugin-spaceclaim
 */
import { defineTool } from "@deepseek-ai/dsh-tools";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

/** Cordis plugin name (row identity is the composition's `id`, not this). */
const name = "tool-spaceclaim";

/** Services this plugin consumes from the harness. */
const inject = ["tools"];

/** Package root: the directory holding `lib/` and `scripts/`. */
const PLUGIN_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SCRIPTS_DIR = join(PLUGIN_ROOT, "scripts");
const RUNNER = join(SCRIPTS_DIR, "Invoke-Scdm.ps1");

const DESCRIPTION =
	"Build a 3D model in Ansys SpaceClaim without the GUI, and name its boundary conditions. " +
	"Use this instead of driving SpaceClaim through a shell: it runs the verified headless path and verifies the result. " +
	"Workflow: (1) write a short IronPython model script using the helper functions documented by the `spaceclaim-modeling` skill " +
	"(`box`, `cylinder`, `tube`, `sphere`, `cone_frustum`, `profile_prisms`, `move`, `rotate`, `split_face_by_line`, `round_edges`, `chamfer_edges`, " +
	"`name_boundaries`, `name_faces_by_rules`, `finish`); the runner injects those helpers, " +
	"so never import them and never call SpaceClaim's own API directly unless you must; " +
	"(2) call this tool with the script path and the .scdocx path that the script's `finish(path)` saves to. " +
	"All geometry units are millimetres (the library converts to SpaceClaim's internal metres). " +
	"Named selections become boundary zones in Workbench / Mechanical / Fluent Meshing, so their names must be ASCII. " +
	"Success is judged by the runner's `<<<SCDM_OK>>>` sentinel, never by SpaceClaim's exit code; " +
	"with `verify` the saved file is re-opened in a fresh SpaceClaim session and its bounding box plus every named selection is read back from disk. " +
	"Requires Ansys SpaceClaim installed on this machine (auto-detected; override with the DSH_SCDM_EXE environment variable). " +
	"A full run takes roughly a minute because SpaceClaim starts once per build and once more for verification.";

/** Locate a PowerShell host: the env override, then pwsh 7, then Windows PowerShell 5.1. */
function resolvePowerShell() {
	const candidates = [
		process.env.DSH_SCDM_POWERSHELL,
		join(process.env.ProgramFiles ?? "C:\\Program Files", "PowerShell", "7", "pwsh.exe"),
		join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
	];
	for (const candidate of candidates) {
		if (candidate && existsSync(candidate)) return candidate;
	}
	return "powershell.exe";
}

/** Run the runner script and resolve with its captured output; never rejects. */
function runRunner(cliArgs, timeoutMs) {
	return new Promise((settle) => {
		let child;
		try {
			child = spawn(resolvePowerShell(), [
				"-NoProfile", "-ExecutionPolicy", "Bypass", "-File", RUNNER, ...cliArgs
			], { cwd: SCRIPTS_DIR, windowsHide: true });
		} catch (error) {
			settle({ code: -1, stdout: "", stderr: String(error) });
			return;
		}
		let stdout = "";
		let stderr = "";
		child.stdout.setEncoding("utf8");
		child.stderr.setEncoding("utf8");
		child.stdout.on("data", (chunk) => { stdout += chunk; });
		child.stderr.on("data", (chunk) => { stderr += chunk; });
		const timer = setTimeout(() => { try { child.kill(); } catch { /* already gone */ } }, timeoutMs);
		child.on("error", (error) => {
			clearTimeout(timer);
			settle({ code: -1, stdout, stderr: `${stderr}${String(error)}` });
		});
		child.on("close", (code) => {
			clearTimeout(timer);
			settle({ code: code ?? -1, stdout, stderr });
		});
	});
}

/** First capture group of a multiline match, or undefined. */
function pick(text, pattern) {
	const match = text.match(pattern);
	return match ? match[1].trim() : undefined;
}

/** Register the SpaceClaim tool on the harness tool registry. */
function apply(ctx) {
	ctx.tools.register(defineTool({
		name: "scdm_build",
		description: DESCRIPTION,
		parameters: {
			script: {
				type: "string",
				required: true,
				description: "Absolute path to the IronPython model script (.py) to run in SpaceClaim."
			},
			out: {
				type: "string",
				required: true,
				description: "Absolute path to the .scdocx the run must produce. It has to match the path the script passes to finish(); the runner reports `artifact is missing` when it does not."
			},
			verify: {
				type: "boolean",
				description: "Re-open the saved file in a fresh SpaceClaim session and read back its size and named selections. Defaults to true; pass false only to save a minute on a throwaway run."
			},
			timeout_sec: {
				type: "integer",
				description: "Per-step timeout in seconds for each SpaceClaim launch. Defaults to 900."
			}
		},
		output: {
			schema: {
				type: "object",
				additionalProperties: false,
				properties: {
					status: { type: "string", required: true },
					artifact: { type: "string" },
					artifact_size: { type: "integer" },
					verify_report: { type: "string" },
					exit_code: { type: "integer", required: true },
					output: { type: "string", required: true }
				}
			},
			render: (_args, value) => [{
				type: "text",
				text: value.output
			}]
		},
		async execute(args) {
			const timeoutSec = args.timeout_sec ?? 900;
			const cliArgs = ["-Script", args.script, "-Out", args.out];
			if (args.verify !== false) cliArgs.push("-Verify");
			cliArgs.push("-TimeoutSec", String(timeoutSec));

			const result = await runRunner(cliArgs, (timeoutSec * 2 + 180) * 1000);
			const combined = `${result.stdout}${result.stderr ? `\n${result.stderr}` : ""}`;
			const reported = pick(combined, /^\[scdm\] status=(\S+)/m);
			const status = reported ?? (result.code === 0 ? "ok" : "failed");
			const sizeText = pick(combined, /^\[scdm\] artifact_size=(\d+)/m);
			const verifyStart = combined.indexOf("--- verify (fresh session");
			const verifyEnd = combined.indexOf("--- end verify ---");
			const verifyReport = verifyStart >= 0 && verifyEnd > verifyStart
				? combined.slice(verifyStart, verifyEnd).trim()
				: undefined;

			return {
				status,
				...(pick(combined, /^\[scdm\] artifact=(.+)$/m) !== undefined
					? { artifact: pick(combined, /^\[scdm\] artifact=(.+)$/m) }
					: {}),
				...(sizeText !== undefined ? { artifact_size: Number(sizeText) } : {}),
				...(verifyReport !== undefined ? { verify_report: verifyReport } : {}),
				exit_code: result.code,
				output: combined.trim()
			};
		}
	}));
}

export { apply, inject, name };
