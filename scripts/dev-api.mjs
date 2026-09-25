/**
 * Start the FastAPI dev server with PYTHONPATH set to the app root (dwa/).
 * Cross-platform: uses .venv when present, otherwise `python` on PATH.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const venvCandidates =
  process.platform === "win32"
    ? [path.join(root, ".venv", "Scripts", "python.exe")]
    : [path.join(root, ".venv", "bin", "python3"), path.join(root, ".venv", "bin", "python")];

const python = venvCandidates.find((p) => existsSync(p)) ?? "python";
const port = process.env.DWA_DEV_API_PORT ?? "8000";

const child = spawn(
  python,
  ["-m", "uvicorn", "dbt_builder.api:app", "--reload", "--port", port],
  {
    cwd: root,
    env: { ...process.env, PYTHONPATH: root },
    stdio: "inherit",
  },
);

child.on("exit", (code) => process.exit(code ?? 1));
