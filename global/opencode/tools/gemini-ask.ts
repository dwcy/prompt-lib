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
  if (code !== 0) return `gemini exited ${code}\n${stderr || stdout}`.trim()
  return stdout.trim()
}

export default tool({
  description: "Ask Gemini CLI for a read-only second opinion through gemini -p.",
  args: {
    prompt: tool.schema.string().describe("Question or task for Gemini CLI"),
  },
  async execute(args, context) {
    const command = process.platform === "win32" ? "gemini.cmd" : "gemini"
    return await run(
      command,
      ["-p", args.prompt, "--approval-mode", "plan", "--output-format", "text"],
      context.worktree || context.directory,
    )
  },
})
