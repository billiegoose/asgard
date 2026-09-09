---
name: ultrapowers
description: Use when the user runs "/ultrapowers <plan-path>", asks to execute an Ultraplan-marked plan, says "go ultra", or requests worktree-isolated implementation in Pi or Paseo.
argument-hint: <plan-path>
---

# Ultrapowers for Pi and Paseo

This project's adapter for `popmechanic/ultrapowers` keeps claims-v1 planning and
`compile_plan.py`, but selects orchestration for the current host. **When
`PASEO_AGENT_ID` is non-empty, prefer Paseo-managed agents** so the operator can
open each child's tab, inspect its conversation, and see failures. This applies
to new implementation workers, `ultraplan` proof readers, reviewers, and gates.
Outside Paseo, retain Pi subagent workflows or Taskplane.

Explicit operator backend choices and capability/permission boundaries take
precedence. Keep already-running workflows on their existing backend; do not
migrate or duplicate their children merely because this preference changed.

Do **not** use Claude-only tools (`Workflow`, `Skill`, `Task`, `ToolSearch`) or `${CLAUDE_PLUGIN_ROOT}`. Resolve the upstream checkout from the project root:

```bash
UP_ROOT="$(git rev-parse --show-toplevel)/.pi/git/github.com/popmechanic/ultrapowers"
```

## Workflow

1. **Preflight**
   - Confirm a clean-enough repo state for worktree work: `git status --short`.
   - Record the launch base before spawning children:
     ```bash
     BASE_SHA="$(git rev-parse HEAD)"
     BASE_BRANCH="$(git symbolic-ref --quiet --short HEAD || true)"
     ```
   - Never run `git stash` as part of an Ultrapowers run. Stash refs are repository-global and race sibling worktrees; inspect earlier states with `git show <sha>:<path>` or `git diff <sha> -- <path>` instead.
   - Confirm upstream Ultrapowers checkout exists at `$UP_ROOT`.
   - Validate the plan:
     ```bash
     python3 "$UP_ROOT/skills/ultrapowers/scripts/compile_plan.py" --check <plan-path>
     ```
   - Compile the wave graph to temporary run files:
     ```bash
     STAMP="$(date +%Y%m%d-%H%M%S)"
     RUN_DIR="$(git rev-parse --show-toplevel)/.pi/ultrapowers/run-$STAMP"
     mkdir -p "$RUN_DIR"
     python3 "$UP_ROOT/skills/ultrapowers/scripts/compile_plan.py" \
       <plan-path> \
       --run-dir "$RUN_DIR" \
       --emit-launch "$RUN_DIR/waves.json" \
       --emit-args "$RUN_DIR/args.json"
     ```

2. **Render a concise execution fit**
   - Show waves, dependencies, risk/review markers, and test command.
   - Treat auth, payments, migrations, data integrity, public APIs, loops/cursors/pagination/budgets/termination logic, and behavior hard to verify by reading as higher-risk review surfaces.
   - In Pi, do not pause for a Claude Workflow approval. If the user invoked `/ultrapowers`, that is execution authorization unless the compile/preflight found a real blocker.

3. **Select the backend before launching children**

   | Current session | Default for new orchestration |
   | --- | --- |
   | Non-empty `PASEO_AGENT_ID` | Paseo-managed agents, even if Pi `subagent` or Taskplane is available |
   | Outside Paseo, Taskplane configured and available | Taskplane |
   | Outside Paseo otherwise | Pi `subagent` workflow |

   An installed Paseo app, `PASEO_CLI`, or a running daemon alone does not establish
   that the current session is Paseo-scoped. A selected backend's unavailable
   tools, launch errors, or missing callbacks are blockers, not permission to
   silently switch backend. Report the exact error and preserve partial work
   before a same-backend retry; obtain operator approval for a backend switch.

4. **Paseo backend**
   - **Required:** read the `paseo` skill. Prefer available agent-scoped MCP tools;
     otherwise use the executable at `PASEO_CLI`, then `paseo` on PATH, or the
     documented bundled CLI. Use CLI `--help` for installed-version syntax.
     Preserve the parent agent environment/identity so launches are real
     subagents in Paseo, not detached unrelated sessions.
   - Read configured profiles and every profile's notes before selection. If
     profile MCP tools are absent, inspect only the profile section of the
     status-reported local daemon config. Prefer a suitable **OpenAI** profile
     or discover available providers/models and announce the profile fallback.
     The model and orchestration provider are separate: Paseo's `pi` provider
     can run a discovered OpenAI model even when its `codex` provider is absent.
     Do not hardcode a model ID or assume catalog availability proves execution
     compatibility/authentication. Do not retry a known-failed model unchanged;
     inspect its error and make an explicit same-Paseo retry with a compatible
     discovered model, or report the blocker. Do not silently switch to Claude.
   - Create Paseo-managed worktree workspaces for writers, one writer per
     workspace. Attach each child with `workspaceId` / CLI `--workspace`.
     Read-only reviewers may share an immutable candidate workspace; never
     review a tree while its writer is still changing it. Launch ready tasks
     from the compiled wave graph; no Pi workflow is needed to wrap Paseo calls.
   - Use descriptive task/role titles. Record each `agentId`, `workspaceId`,
     cwd, branch/base, selected provider/model, status, and report/patch path in
     the run ledger; include agent IDs in progress so tabs are identifiable.
   - Prefer background launches with `notifyOnFinish: true` (the agent-scoped
     default). Collect every completion/error/permission notification in the
     parent, then read the result and evidence; do not poll status in a loop.
     If notifications cannot reach this parent, explicitly arrange a supported
     wait/result-return path before proceeding, rather than losing the child.
     A running/idle status alone is not success.
   - For `ultraplan` proof gates, keep one fresh reader per extracted task and
     have the parent collect each verdict and write the hash-keyed gate artifact.
     Async notification-backed readers are valid; do not fire-and-forget them.
     Execution still requires independent peer reviews and all declared exams.
     Paseo lifecycle status does not replace Pi acceptance evidence: collect
     changed files, commands/exits, validation output and review findings.

5. **Common task, review, and handoff contract**
   - One child per compiled task; independent contexts and managed writer isolation.
   - Give each worker its exact task body, declared files, satisfied dependencies,
     tests, `BASE_SHA`, and no-commit/no-stash/no-nested-delegation boundaries.
   - First action: `git rev-parse HEAD`; report `startHead`, cwd and branch. If
     HEAD differs from the assigned base, correct it only in a verified clean,
     newly allocated worktree and report `baseCorrected: { from, to }`. Never
     reset away saved work during resume. Missing `startHead` is **BASE anchoring
     unverified**. Materialize reviewed dependency patches before new edits;
     record their provenance so anchoring cannot erase satisfied dependencies.
   - Preserve inspectable diffs/reports before cleanup. Integrate each reviewed
     wave deliberately into the session or local integration branch, then run
     project tests. Reconcile peer findings before dependent tasks or acceptance.
     Keep commit, push, merge and cleanup within the operator's authorization.

6. **Pi subagent backend (outside Paseo or explicitly selected)**
   - Discover executable agents first. Use one async `workflowScript` with
     `runs.all([...])` per wave, `worktree:true`, and acceptance evidence requiring
     changed-files, commands-run, validation-output, and review-findings.
     Never launch multiple top-level calls for the wave fanout. Keep reviewers
     fresh and read-only; return durable output/handoff references.

7. **Taskplane backend (outside Paseo or explicitly selected)**
   - Use `create-taskplane-task` conventions for PROMPT.md/STATUS.md, with
     dependencies matching compiled edges. Use configured review levels for
     peer/high-risk surfaces, plus `orch_status`, `read_agent_status`,
     `read_agent_replies`, and `orch_integrate` for monitoring and integration.
   - Apply the same common task, review and handoff contract.

## Asgard defaults

For this repo, prefer:

```bash
uv run pytest
uv run ruff check .
uv run mypy
```

If that is too broad for a task, derive narrower pytest/ruff/mypy commands from the touched files, then run the broader commands before final completion.

For changes to this routing bootstrap, also run:

```bash
node --experimental-strip-types --test .pi/skills/ultrapowers/tests/routing.test.mjs
```
