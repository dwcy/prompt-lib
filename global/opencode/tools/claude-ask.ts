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
  if (code !== 0) return `claude exited ${code}\n${stderr || stdout}`.trim()
  return stdout.trim()
}

export default tool({
  description: "Ask Claude Code for a read-only second opinion through claude -p.",
  args: {
    prompt: tool.schema.string().describe("Question or task for Claude Code"),
  },
  async execute(args, context) {
    const command = process.platform === "win32" ? "claude.exe" : "claude"
    return await run(
      command,
      ["-p", args.prompt, "--permission-mode", "plan", "--output-format", "text"],
      context.worktree || context.directory,
    )
  },
})
