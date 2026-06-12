#!/usr/bin/env bash
set -euo pipefail

# claude-orchestrator-watch.sh
# Launch an Opus-4.8 / --effort max Claude Code ORCHESTRATOR in a detached tmux
# session, then wait until it exits or the wait window elapses. This is the
# orchestrator-tier analogue of .agents/skills/orchestration/references/pi-worker-watch.sh
# (which launches gpt-5.5 `pi` WORKERS). It prints the run directory, status, and the
# last log lines before returning, and supports a --watch mode for progress polling.
#
# Re-derived from the pi-worker-watch.sh template and cross-checked against the
# archived 2026-06-01 launcher. CHANGE vs archive: `Skill` added to the default
# allowlist so the orchestrator can invoke the `orchestration`/`checkpoint`/
# `web-discovery` skills directly. The Agent/Task tool is intentionally omitted so
# the orchestrator must spawn WORKERS via pi-worker-watch.sh (bash), not subagents.

usage() {
  cat <<'USAGE' >&2
Usage:
  claude-orchestrator-watch.sh [options] "<pointer to task>"
  claude-orchestrator-watch.sh [options] --watch <run-dir>

Starts a Claude Code orchestrator (model=opus, effort=max by default) in a detached
tmux session, then waits until it exits or the wait window elapses.

Options:
  --model NAME                   claude --model (default: opus  -> Opus 4.8)
  --effort LEVEL                 low|medium|high|xhigh|max (default: max)
  --permission-mode MODE         claude --permission-mode (default: bypassPermissions)
  --allowed-tools "T1 T2 ..."    space-separated tool allowlist (default below)
  --add-dir DIR                  extra dir the orchestrator may access (repeatable)
  --append-system-prompt-file F  REQUIRED: file appended to the system prompt (role+safety)
  --wait-seconds N               seconds to wait before a progress check (default: 1800)
  --poll-seconds N               seconds between status checks (default: 5)
  --tail-lines N                 log lines to print when returning (default: 25)
  --worker-root DIR              dir for orchestrator logs/status (default: $PWD/.claude-orchestrators)
  --watch DIR                    watch an existing run dir instead of starting a new orchestrator
  -h, --help                     show this help

Environment:
  CLAUDE_BIN                     claude executable to run (default: claude)
USAGE
}

is_uint() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }
shell_quote() { printf '%q' "$1"; }

model="opus"
effort="max"
perm="bypassPermissions"
allowed_tools="Bash Read Grep Glob Edit Write TodoWrite Skill"
sys_file=""
add_dirs=()
wait_seconds="${CLAUDE_ORCH_WAIT_SECONDS:-1800}"
poll_seconds="${CLAUDE_ORCH_POLL_SECONDS:-5}"
tail_lines="${CLAUDE_ORCH_TAIL_LINES:-25}"
worker_root="${CLAUDE_ORCH_ROOT:-$PWD/.claude-orchestrators}"
claude_bin="${CLAUDE_BIN:-claude}"
watch_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) model="${2:-}"; shift 2;;
    --effort) effort="${2:-}"; shift 2;;
    --permission-mode) perm="${2:-}"; shift 2;;
    --allowed-tools) allowed_tools="${2:-}"; shift 2;;
    --add-dir) add_dirs+=("${2:-}"); shift 2;;
    --append-system-prompt-file) sys_file="${2:-}"; shift 2;;
    --wait-seconds) wait_seconds="${2:-}"; shift 2;;
    --poll-seconds) poll_seconds="${2:-}"; shift 2;;
    --tail-lines) tail_lines="${2:-}"; shift 2;;
    --worker-root) worker_root="${2:-}"; shift 2;;
    --watch) watch_dir="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    --) shift; break;;
    -*) echo "Unknown option: $1" >&2; usage; exit 64;;
    *) break;;
  esac
done

if ! is_uint "$wait_seconds" || ! is_uint "$poll_seconds" || ! is_uint "$tail_lines"; then
  echo "--wait-seconds, --poll-seconds, and --tail-lines must be non-negative integers" >&2
  exit 64
fi
if [[ "$poll_seconds" -eq 0 && "$wait_seconds" -gt 0 ]]; then
  echo "--poll-seconds must be greater than 0 when --wait-seconds is greater than 0" >&2
  exit 64
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
script_path="$script_dir/$(basename "${BASH_SOURCE[0]}")"

print_tail() {
  local log="$1"
  echo "--- tail -n $tail_lines $log ---"
  if [[ -f "$log" ]]; then tail -n "$tail_lines" "$log" || true; else echo "log file not found: $log"; fi
}

watch_run() {
  local run_dir="$1" run_id status log deadline now remaining sleep_for code
  run_id="$(basename "$run_dir")"
  status="$run_dir/status"; log="$run_dir/output.log"
  deadline=$(( $(date +%s) + wait_seconds ))
  while [[ ! -s "$status" ]]; do
    now=$(date +%s)
    [[ "$now" -ge "$deadline" ]] && break
    remaining=$(( deadline - now )); sleep_for="$poll_seconds"
    [[ "$remaining" -lt "$sleep_for" ]] && sleep_for="$remaining"
    [[ "$sleep_for" -le 0 ]] && break
    sleep "$sleep_for"
  done
  echo "orchestrator run dir: $run_dir"
  if [[ -s "$status" ]]; then
    code="$(tr -d '\r\n' < "$status" || true)"
    echo "orchestrator finished: $run_id exit $code"
    print_tail "$log"
    if is_uint "$code"; then exit "$code"; fi
    exit 1
  fi
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$run_id" 2>/dev/null; then
    echo "$wait_seconds-second check: orchestrator still running: $run_id"
    echo "watch again: bash $(shell_quote "$script_path") --watch $(shell_quote "$run_dir")"
    echo "attach (read-only recommended): tmux attach-session -t $(shell_quote "$run_id")"
    print_tail "$log"
    exit 0
  fi
  echo "orchestrator session ended but no status file: $run_id" >&2
  print_tail "$log"
  exit 1
}

if [[ -n "$watch_dir" ]]; then
  [[ $# -gt 0 ]] && { echo "Unexpected arguments after --watch: $*" >&2; usage; exit 64; }
  [[ ! -d "$watch_dir" ]] && { echo "run directory not found: $watch_dir" >&2; exit 66; }
  watch_run "$watch_dir"
fi

[[ $# -lt 1 ]] && { echo "Missing pointer to task" >&2; usage; exit 64; }
task="$*"

command -v "$claude_bin" >/dev/null 2>&1 || { echo "claude executable not found: $claude_bin" >&2; exit 127; }
command -v tmux >/dev/null 2>&1 || { echo "tmux is required to run detached orchestrators" >&2; exit 127; }
[[ -z "$sys_file" ]] && { echo "--append-system-prompt-file is REQUIRED (carries role + non-negotiable safety rules)" >&2; exit 64; }
[[ ! -f "$sys_file" ]] && { echo "system prompt file not found: $sys_file" >&2; exit 66; }

cwd="$PWD"
mkdir -p "$worker_root"
worker_root="$(cd "$worker_root" && pwd -P)"
run_id="claude-orch-$(date +%Y%m%d-%H%M%S)-$$-${RANDOM}"
run_dir="$worker_root/$run_id"
mkdir -p "$run_dir"
log="$run_dir/output.log"; status="$run_dir/status"; runner="$run_dir/run-orch.sh"; metadata="$run_dir/metadata.txt"
: > "$log"

cat > "$metadata" <<EOF
started_at=$(date -Iseconds)
cwd=$cwd
tmux_session=$run_id
model=$model
effort=$effort
permission_mode=$perm
allowed_tools=$allowed_tools
append_system_prompt_file=$sys_file
task=$task
EOF

# Build the claude command as a quoted array. Order matters: the single-valued
# --append-system-prompt-file is placed LAST before the positional task so the
# variadic --allowedTools/--add-dir cannot swallow the task argument.
{
  echo '#!/usr/bin/env bash'
  echo 'set -u'
  printf 'cd %q\n' "$cwd"
  printf 'log=%q\n' "$log"
  printf 'status=%q\n' "$status"
  printf 'cmd=(%q -p --model %q --effort %q --permission-mode %q' "$claude_bin" "$model" "$effort" "$perm"
  printf ' --allowedTools'
  for t in $allowed_tools; do printf ' %q' "$t"; done
  if [[ ${#add_dirs[@]} -gt 0 ]]; then
    for d in "${add_dirs[@]}"; do printf ' --add-dir %q' "$d"; done
  fi
  printf ' --append-system-prompt-file %q' "$sys_file"
  printf ' %q' "$task"
  printf ')\n'
  cat <<'RUNNER'
"${cmd[@]}" </dev/null >"$log" 2>&1
code=$?
printf '%s\n' "$code" >"$status"
exit "$code"
RUNNER
} > "$runner"
chmod +x "$runner"

tmux new-session -d -s "$run_id" "bash $(shell_quote "$runner")"
echo "orchestrator started: $run_id"
watch_run "$run_dir"
