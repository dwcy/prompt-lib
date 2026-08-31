// Release note content for the desktop workspace. Static data, versioned with the app:
// every entry names where the feature lives in the UI so a reader can go straight to it.

export interface ReleaseEntry {
  /** Short feature name. */
  title: string;
  /** Sidebar path to the feature, or "—" for changes with no screen of their own. */
  location: string;
  /** What problem it solves. */
  purpose: string;
  /** Ordered steps to actually use it. */
  steps: string[];
  /** Optional caveat worth knowing before relying on it. */
  note?: string;
}

export interface ReleaseSection {
  id: string;
  title: string;
  blurb: string;
  entries: ReleaseEntry[];
}

export const RELEASE_TITLE = "Desktop workspace";
export const RELEASE_SUMMARY =
  "The read-only browser page is retired. Everything the terminal wizard could do now has a screen here, " +
  "and anything that changes your machine goes through a preview-and-confirm step first.";

export const RELEASE_SECTIONS: ReleaseSection[] = [
  {
    id: "start-here",
    title: "Start here",
    blurb: "The three screens that orient you before anything else.",
    entries: [
      {
        title: "Overview",
        location: "Machine → Overview",
        purpose:
          "The landing screen: what is ready, what has drifted from source, and what needs attention right now.",
        steps: [
          "Open it from the sidebar, or press the module switcher and type 'Overview'.",
          "Read the readiness tiles top-left; each one links to the screen that fixes it.",
          "Follow any 'Drift' badge in the sidebar to Deploy config.",
        ],
      },
      {
        title: "Switch project",
        location: "Repo → Switch project",
        purpose:
          "Chooses which repository every project-scoped screen reads from. Most Repo screens are empty until one is picked.",
        steps: [
          "Pick a recent project, or browse to a folder.",
          "The selection persists across restarts and re-keys the cached data for every screen.",
        ],
      },
      {
        title: "Docs",
        location: "Reference → Docs",
        purpose:
          "Reads this repository's README and everything under docs/ without leaving the app.",
        steps: [
          "Open Docs.",
          "Pick a document from the list on the right to replace the README pane.",
        ],
      },
    ],
  },
  {
    id: "confirmations",
    title: "How changes are applied",
    blurb: "One safety model shared by every screen that writes to your machine.",
    entries: [
      {
        title: "Preview and confirm",
        location: "Every action button, app-wide",
        purpose:
          "Nothing mutates on a single click. The app first asks the backend what would happen and shows you the exact commands, files, and removals before anything runs.",
        steps: [
          "Press any action button (Install, Apply, Deploy, Remove…).",
          "Read the dialog: commands to be run, files touched, what gets removed, and whether a backup is taken.",
          "Confirm to execute, or cancel — cancelling leaves the machine untouched.",
        ],
        note: "If the machine changed between preview and confirm, the ticket is refused and you are asked to re-review. Destructive actions cannot be confirmed without naming their removals and backup.",
      },
      {
        title: "Job tray and live logs",
        location: "Top-right job tray, on every screen",
        purpose:
          "Long-running work (installs, clones, deploys) streams its output live instead of freezing the UI.",
        steps: [
          "Start a long action; a job appears in the tray.",
          "Open the job to follow its output line by line.",
          "Cancel from the tray if you need to stop it.",
        ],
      },
      {
        title: "Diagnostics and audit trail",
        location: "Machine → Diagnostics",
        purpose:
          "Backend health, the live event feed, and a record of every action that was executed — useful when something did not behave as expected.",
        steps: [
          "Open Diagnostics.",
          "Check the audit list for what ran, when, and whether it succeeded.",
        ],
      },
    ],
  },
  {
    id: "machine",
    title: "Machine",
    blurb: "Your toolchain and the environment agents run in.",
    entries: [
      {
        title: "Tools catalog",
        location: "Machine → Tools",
        purpose:
          "Inventory of the CLIs this setup expects, with installed versions, available channels, and repairs.",
        steps: [
          "Filter or search for a tool.",
          "Select it to see status, docs, and the install or update action.",
          "Pick a version where the tool offers several, then confirm.",
        ],
      },
      {
        title: "Environment variables",
        location: "Machine → Environment variables",
        purpose:
          "Reads the curated variables this setup uses plus your full system environment, and writes the curated ones back.",
        steps: [
          "Switch between the curated and system views.",
          "Edit a curated value and apply; the confirm dialog shows exactly what will be written.",
        ],
        note: "Secret-named values (anything with TOKEN, SECRET, PASSWORD, API_KEY in the name) are masked in the UI and never leave the backend in clear text.",
      },
      {
        title: "Every source of configuration for a project",
        location: "Machine → Environment variables",
        purpose:
          "Beyond Curated and System, the screen now builds a tab for every config file in the selected project and for each cloud source it can actually reach — Azure, Vercel, and GitHub — plus .NET's developer secret store, which lives outside the repository.",
        steps: [
          "Select a project. Tabs appear only for sources actually detected, so what you see is what this project really has.",
          "Every tab lists names only. Click the eye on one row to fetch that single value; it re-masks itself when you switch tab or project.",
          "A tab that says 'nothing configured' is reachable and empty; one with a hint is only partly readable and the hint names what to fix.",
          "For a .NET project, keys read as their full path (Logging:LogLevel:Default) and each row states which settings layer wins.",
        ],
        note: "Read-only against Azure, Vercel, and GitHub — nothing is ever created, updated, or deleted there. Some values can never be read back at all: GitHub secrets and Vercel 'sensitive' entries show a disabled eye stating so, which is a fact about those platforms rather than a failure. Every reveal is recorded in the audit trail, and the record never contains the value.",
      },
    ],
  },
  {
    id: "repo",
    title: "Repo",
    blurb: "Screens scoped to the project you selected.",
    entries: [
      {
        title: "Project health",
        location: "Repo → Project health",
        purpose: "Git state and the systems connected to the current project, in one view.",
        steps: [
          "Select a project first.",
          "Open Project health for branch, remote, and connected-system state.",
        ],
      },
      {
        title: "Project setup",
        location: "Repo → Project setup",
        purpose:
          "Creates project-local configuration — .gitignore templates, local settings, and the project's own agent config.",
        steps: [
          "Pick a blueprint.",
          "Review the staged file preview.",
          "Confirm to write into the project.",
        ],
      },
      {
        title: "Knowledge and retrieval",
        location: "Repo → Knowledge",
        purpose:
          "The searchable catalog of how agents, skills, hooks, and rules relate, plus retrieval that assembles a context pack for a question.",
        steps: [
          "Search for a concept or ask a question.",
          "Open a result for its full document and the evidence behind it.",
          "Build a context pack when you want the relevant slice rather than one document.",
        ],
        note: "Results tell you when the index is stale relative to the source files, so old answers are never silent.",
      },
      {
        title: "Sessions and cost",
        location: "Repo → Sessions & cost",
        purpose:
          "Reads your Claude transcripts: what each session did, how long it took, tokens used, and estimated cost.",
        steps: [
          "Sort by date, cost, tokens, or duration.",
          "Open a session for its activity, model breakdown, and raw transcript.",
        ],
      },
      {
        title: "Git identity and commit policy",
        location: "Repo → Git identity",
        purpose:
          "Shows the global and repo-local git identity and edits the agent commit policy (allowed types, refused branches, tag rules).",
        steps: ["Review both scopes side by side.", "Edit the identity or policy and confirm."],
        note: "Identity writes are limited to the global and local scopes — the system scope is rejected.",
      },
      {
        title: "New project wizard",
        location: "Repo → New project",
        purpose:
          "Scaffolds a new project from a template, including its launcher and agent configuration.",
        steps: [
          "Answer the template questions.",
          "Review the staged file list.",
          "Confirm to create the project.",
        ],
      },
    ],
  },
  {
    id: "infrastructure",
    title: "Infrastructure",
    blurb: "Connectors, running services, and dependency risk.",
    entries: [
      {
        title: "MCP connectors",
        location: "Infrastructure → MCP connectors",
        purpose:
          "Registers the MCP servers agents can call, showing which scope each one lives in and whether it is connected.",
        steps: [
          "Browse available templates and registered servers.",
          "Enable a template to register it, or remove one you no longer want.",
        ],
        note: "Servers needing cluster or account access (OpenShift/Kubernetes, okf-rag, headroom) are opt-in and stay off until you enable them.",
      },
      {
        title: "Agent services",
        location: "Infrastructure → Services",
        purpose: "Starts, stops, and tails the local bridges and runtimes agents depend on.",
        steps: [
          "Start a service.",
          "Open its log stream to watch output live.",
          "Stop it when finished.",
        ],
      },
      {
        title: "Package security",
        location: "Infrastructure → Package security",
        purpose:
          "Scans project dependencies for known vulnerabilities and outdated packages, and applies the fix command for you.",
        steps: [
          "Run a scan for the selected project.",
          "Open a finding to see severity and the exact upgrade.",
          "Use 'Ask AI' for a plain-language verdict on whether the fix is worth taking.",
          "Apply the fix and confirm.",
        ],
      },
      {
        title: "GitHub accounts and clone",
        location: "Infrastructure → GitHub",
        purpose: "Manages GitHub accounts, browses your repositories, and clones one into place.",
        steps: [
          "Sign in or pick an account.",
          "Find the repository.",
          "Clone it and confirm the destination.",
        ],
      },
    ],
  },
  {
    id: "agents",
    title: "Agents",
    blurb: "The configuration that shapes how agents behave.",
    entries: [
      {
        title: "Deploy config",
        location: "Agents → Deploy config",
        purpose:
          "The core loop of this repo: compares the versioned source tree against what is deployed to your home directory and deploys the difference.",
        steps: [
          "Open it when the sidebar shows a 'Drift' badge.",
          "Read the per-file diff to see exactly what changed.",
          "Deploy and confirm; restart your agent afterwards to pick the changes up.",
        ],
      },
      {
        title: "Settings configurator",
        location: "Agents → Settings",
        purpose:
          "Edits agent settings with their inheritance made visible — which value wins, and which file it came from.",
        steps: [
          "Find the setting.",
          "See its effective value and source.",
          "Override it locally and confirm.",
        ],
      },
      {
        title: "Claude config",
        location: "Agents → Claude config",
        purpose: "Credentials, global instructions, and the runtime identity your agent is using.",
        steps: ["Open it to review what the agent is currently configured with."],
      },
      {
        title: "Config doctor",
        location: "Agents → Config doctor",
        purpose: "Finds configuration problems and offers the route that repairs each one.",
        steps: [
          "Run the doctor.",
          "Work down the findings; each links to the screen that fixes it.",
        ],
      },
      {
        title: "Model assignments",
        location: "Agents → Model assignments",
        purpose:
          "Pins which model each agent or skill uses and shows the resulting routing distribution.",
        steps: ["Pick an asset.", "Assign a model and confirm."],
      },
      {
        title: "Scheduled tasks",
        location: "Agents → Scheduled tasks",
        purpose: "Inventory of the Claude and Codex automations scheduled on this machine.",
        steps: [
          "Review what is scheduled.",
          "Delete a task you no longer want, with confirmation.",
        ],
      },
      {
        title: "Recovery",
        location: "Agents → Recovery",
        purpose:
          "Backups, cleanup of deployed extras, and restore history — the way back when a deploy went wrong.",
        steps: [
          "Review what would be removed or restored in the preview.",
          "Confirm; destructive steps state their backup up front.",
        ],
      },
      {
        title: "Codex parity",
        location: "Agents → Codex parity",
        purpose:
          "Keeps the Codex configuration aligned with the Claude one, and converts between them.",
        steps: ["Compare the two trees.", "Deploy or convert, then confirm."],
      },
    ],
  },
  {
    id: "beyond-ui",
    title: "Two subsystems moving into the workspace",
    blurb:
      "Both shipped command-line first and are now growing screens. What is listed under each is what the screen does today; everything else still runs from the CLI.",
    entries: [
      {
        title: ".NET Code Generation",
        location: "Repo → .NET Codegen",
        purpose:
          "Generates .NET backend code through a routed pipeline — classify, plan, approve, write, verify — with per-stage model routing so a cheap model does the routing and an expensive one only does architecture.",
        steps: [
          "Describe the change in prose against the selected project.",
          "Read the plan at the approval gate: it lists every file it intends to touch, and nothing reaches disk until you approve.",
          "Approve or reject. If the project changed underneath the plan, approval is refused rather than applied to something it never saw.",
        ],
        note: "Per-stage cost and the report view are still CLI-only (python -m cabal.dotnetgen report). Build failures are separated into environment problems versus real code defects, so a broken toolchain does not consume the repair budget.",
      },
      {
        title: "Agent Eval Harness",
        location: "Agents → Agent Evals",
        purpose:
          "Answers 'did that configuration change actually help?' by running fixed coding tasks against two agent configurations and comparing them.",
        steps: [
          "Open a finished run to see the comparison: deterministic checks, the pairwise judge verdict, and what each configuration cost in tool calls, tokens and time.",
          "Drill into any single cell for its own check outcomes.",
          "Runs the CLI produced appear here too — there is no separate 'started in the app' list.",
        ],
        note: "Where the evidence is weak the view says so: no spread is claimed below three samples, a judge that disagreed with itself across both A/B orders reads as a tie rather than a win, and excluded pairs are shown with their count. Launching, resuming and editing benchmark definitions are still CLI-only.",
      },
      {
        title: "AI Technology News",
        location: "Reference → AI news feed",
        purpose:
          "Collects AI and developer-tooling news from configured sources into one reviewable feed.",
        steps: [
          "Open the feed from the sidebar.",
          "Scan the collected items; each links back to its source.",
        ],
      },
    ],
  },
  {
    id: "hardening",
    title: "Hardening in this release",
    blurb: "Fixes worth knowing about because they change what you can trust.",
    entries: [
      {
        title: "Secrets stay on the backend",
        location: "Machine → Environment variables",
        purpose:
          "Environment values with credential-shaped names are masked before they leave the backend — in this screen and in every other response — and prepared actions no longer keep your values on disk after they run.",
        steps: ["No action needed — this is on by default."],
      },
      {
        title: "Confirmations are single-use",
        location: "Every confirm dialog",
        purpose:
          "A confirmation can only execute once, even if two requests race, so one approval can never run a destructive action twice.",
        steps: ["No action needed — this is on by default."],
      },
      {
        title: "The desktop app survives a reload",
        location: "App-wide",
        purpose:
          "Refreshing the window used to disconnect the app from its backend until a full restart. It now reconnects on its own.",
        steps: ["No action needed — press F5 freely."],
      },
      {
        title: "Faster health and overview",
        location: "Machine → Overview",
        purpose:
          "Expensive host probes behind this screen and the sidebar health strip are cached briefly instead of re-running on every poll, so the app stops spawning background processes several times a minute.",
        steps: ["No action needed — values refresh on their own within a minute."],
      },
    ],
  },
];
