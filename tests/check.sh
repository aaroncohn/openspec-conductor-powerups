#!/bin/bash
# Everything that can be checked without a live Conductor. Run before merging: tests/check.sh
set -eu
cd "$(dirname "$0")/.."
fail() { echo "✗ $1"; exit 1; }

# 1. The scripts compile and their self-tests pass (each runs its asserts first).
python3 -m py_compile skills/babysitter/conductor-local.py skills/babysitter/state.py skills/doctor/doctor.py
BABYSITTER_STATE="$(mktemp -d)/s.json" python3 skills/babysitter/state.py counts >/dev/null
python3 -c 'import importlib.util as u, sys; s=u.spec_from_file_location("c","skills/babysitter/conductor-local.py"); m=u.module_from_spec(s); s.loader.exec_module(m); m.check_stage(); m.check_scan_changes()'
grep -q "'steer'" skills/babysitter/conductor-local.py || fail "conductor-local.py send must use mode steer (Conductor 0.92 stopped draining queue)"
echo "✓ scripts compile and self-tests pass"

# 2. Prompt invariants: things that drifted once and must not again.
same() { diff <(grep -F "$1" "$2") <(grep -F "$1" "$3") >/dev/null || fail "$4"; }
grep -q 'ask the open decisions \*\*one at a time\*\*' skills/new-batch-explore/SKILL.md || fail "explore prompt must ask decisions one at a time"
same 'ask the open decisions' skills/new-batch-explore/SKILL.md skills/new-batch-explore/cloud.md "explore decision text differs between SKILL.md and cloud.md"
! grep -q 'every open decision in one message' skills/new-batch-explore/SKILL.md skills/new-batch-explore/cloud.md || fail "explore prompt asks all decisions at once"
grep -q 'output of `state.py table`, pasted as is' skills/babysitter/SKILL.md || fail "digest must paste state.py table"
grep -q 'output of `state.py counts`, pasted as is' skills/babysitter/SKILL.md || fail "digest must paste state.py counts"
grep -q 'A digest is always the full shape below, table included' skills/babysitter/SKILL.md || fail "digest must always include the table"
grep -q '^\*\*Critical path:\*\*' skills/babysitter/examples/digest.md || fail "digest example lacks a critical path"
grep -q '^| workspace | stage | effort | progress | next step | ETA | babysitter monitoring? |' skills/babysitter/examples/digest.md || fail "digest example table columns differ from state.py"
grep -q 'Via Babysitter: ' skills/babysitter/SKILL.md skills/babysitter/cloud.md || fail "Via Babysitter prefix missing"
! grep -rnE '[^`/]/opsx:propose[^`]' skills/*/SKILL.md skills/*/cloud.md skills/*/examples/*.md || fail "a user-facing /opsx:propose is not in backticks (Conductor cuts it at the colon)"
! grep -n 'conductor workspace create' skills/*/cloud.md | grep -v -- '--repo-url' || fail "a conductor workspace create without --repo-url (the CLI guesses the project otherwise)"
echo "✓ prompt invariants hold"

# 3. Every skill is listed in the README and has frontmatter; the manifests are valid JSON.
for d in skills/*/; do
  n=$(basename "$d")
  head -1 "$d/SKILL.md" | grep -q '^---$' || fail "$n/SKILL.md has no frontmatter"
  grep -q "^name: $n$" "$d/SKILL.md" || fail "$n/SKILL.md name differs from its folder"
  grep -q "| \*\*$n\*\* |" README.md || fail "$n is not in the README table"
done
python3 -c 'import json; json.load(open(".claude-plugin/plugin.json")); json.load(open(".claude-plugin/marketplace.json"))'
! grep -q '"version"' .claude-plugin/plugin.json || fail "plugin.json must not have a version"
echo "✓ skills listed, manifests valid"

# 4. Nothing project-specific leaked into the skills (CLAUDE.md: keep the skills generic).
! grep -rniE --exclude-dir=__pycache__ 'nicesite|@gmail' skills/ || fail "project-specific name in skills/"
! grep -rn --exclude-dir=__pycache__ 'aaroncohn' skills/ | grep -v 'aaroncohn/openspec-conductor-powerups' || fail "project-specific name in skills/ (the plugin's own repo URL is fine)"
echo "✓ skills are generic"

# 5. The plugin validates (three warnings expected: no version, no icon, CLAUDE.md not loaded).
claude plugin validate . >/dev/null 2>&1 || fail "claude plugin validate failed"
echo "✓ plugin validates"
