// opencode plugin: block coding agents from reading credential files.
//
// A thin adapter. The decision lives once, in ../secret_read_guard.py, which this
// plugin runs before every tool call with {tool, args, cwd} on stdin. Exit 2
// means blocked: the plugin throws, opencode cancels the call and shows the
// reason (stderr) to the model. Any other exit lets the call run, so a missing
// python3 does not break the session; it only disables the guard.
//
// install.sh --secret-guard links this file into ~/.config/opencode/plugins/.
// One default export serves both plugin APIs: opencode 1.x (>= 1.18.29) calls
// server() and uses its `tool.execute.before` hook; opencode 2 reads id and
// setup() and registers `execute.before` on ctx.tool
// (https://opencode.ai/v2/docs/build/plugins#support-v1).

import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// realpath: the plugin is installed as a symlink, the guard sits next to its target.
const GUARD = join(dirname(dirname(realpathSync(fileURLToPath(import.meta.url)))), "secret_read_guard.py");
const EXIT_BLOCK = 2;

function check(tool, args, cwd) {
  const run = spawnSync("python3", [GUARD, "--harness", "opencode"], {
    input: JSON.stringify({ tool, args: args ?? {}, cwd: cwd ?? process.cwd() }),
    encoding: "utf8",
  });
  if (run.status === EXIT_BLOCK) {
    throw new Error(run.stderr.trim());
  }
}

export default {
  id: "fabiandistler-agents.secret-read-guard",
  async setup(ctx) {
    await ctx.tool.hook("execute.before", (event) => {
      check(event.tool, event.input, ctx.directory);
    });
  },
  async server(ctx) {
    return {
      "tool.execute.before": async (input, output) => {
        check(input.tool, output?.args, ctx?.directory);
      },
    };
  },
};
