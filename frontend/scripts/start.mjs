// Native development/staging startup for Next's traced standalone output.
import { cpSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const standalone = resolve(root, ".next/standalone");
if (!existsSync(resolve(standalone, "server.js"))) {
  throw new Error("Build the frontend before starting it: npm run build");
}
cpSync(resolve(root, ".next/static"), resolve(standalone, ".next/static"), {
  recursive: true,
});
if (existsSync(resolve(root, "public"))) {
  cpSync(resolve(root, "public"), resolve(standalone, "public"), {
    recursive: true,
  });
}
process.env.HOSTNAME = process.env.HR_FRONTEND_HOST || "127.0.0.1";
await import(pathToFileURL(resolve(standalone, "server.js")).href);
