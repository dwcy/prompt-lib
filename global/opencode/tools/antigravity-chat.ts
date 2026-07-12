import { tool } from "@opencode-ai/plugin"

async function run(command: string, args: string[], cwd: string) {
  const proc = Bun.spawn([command, ...args], {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
  })
  const stdout = await new Response(proc.stdout).text()
  const stderr = await new Response(proc.stderr).text()
  const code = await proc.exited
  if (code !== 0) return `antigravity exited ${code}\n${stderr || stdout}`.trim()
  return (stdout || "Antigravity chat launch requested.").trim()
}

export default tool({
  description: "Open a Google Antigravity chat for the current worktree.",
  args: {
    prompt: tool.schema.string().describe("Prompt for Antigravity chat"),
    mode: tool.schema.string().optional().describe("Antigravity chat mode: ask, edit, or agent"),
  },
  async execute(args, context) {
    const command = process.platform === "win32" ? "antigravity.cmd" : "antigravity"
    return await run(
      command,
      ["chat", "--mode", args.mode || "agent", "--reuse-window", args.prompt],
      context.worktree || context.directory,
    )
  },
})
