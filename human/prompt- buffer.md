
From here on out, starting now, every 2 hours, send GPT Pro this message:

```md
When you reach a natural stopping point after major milestones are achieved, carefully and rigorously go over the claims you have made and build a compact proof tree with statuses for all our work. Include the different branches we went down, which branches we ruled out, and which we are still working through. 

Then compress and refine our understanding of the problem and our approach to make our approach more elegant, conceptually sound, and easier to identify the right approach. This means
- simplify
- clean
- replace with alternate, better methods
- make more elegant
- compress unnecessarily long arguments to shorter, more concise arguments (but still formally rigorous and correct)
- turn unnecessarily specific work into a more general, simpler results or theory

By simplifying and compressing our proof we reveal new ideas, remove unnecessary noise in our formulations, and start to expose the real picture of what is going on.

Then, using the compressed and refined understanding consider connections to methods from geometry (e.g. differential, discrete, and convex), topology (e.g. morse, algebraic), analysis (e.g. differential equations, measure theory, complex analysis, transport), statistics, combinatorics (e.g. probabilistic method, statistical physics, graph theory, ramsey theory), number theory, algebra, and algebraic geometry. If you find a better route than the one we are taking, push down that direction.

Finally, rebuild the proof tree with your compressed and simplified understanding of the problem. Make sure to check your proof tree and claims. Then, pick 3-5 of the most promising directions to go and use a pseudorandom generator to select one of them to push down. File the others in the proof tree, in case we find they are useful later.
```

Perpetually send "keep pushing!!" until the 2 hour window resets.


---

You are the team lead (team-lead-v2 skill) for team "ask-chatgpt-dev" — an eternal ROLE realized by ephemeral agents. You are starting a fresh incarnation in a new context. Load the team-lead-v2 skill and follow it.

FIRST, read & obey agent-rigor: /home/abhmul/dev/ask-chatgpt/.claude/skills/manager/references/agent-rigor.md

THEN rehydrate the durable state, in order:
1. Identity/charter: /home/abhmul/dev/ask-chatgpt/team/team.json (owns; role_file=team/charter.md; mesh_path=null → SINGLE TEAM; ledger; ground_truth; shared_resources)
2. Charter (domain rules, copied verbatim into every contract): /home/abhmul/dev/ask-chatgpt/team/charter.md
3. Handoff: /home/abhmul/dev/ask-chatgpt/team/state/RESUME.md
4. Live-state: /home/abhmul/dev/ask-chatgpt/team/state/live-state.json (mission queue, blockers, last_verified — NEVER trust over ground truth)
5. Durable lessons: /home/abhmul/.claude/projects/-home-abhmul-dev-ask-chatgpt/memory/MEMORY.md
6. Evidence log (authoritative when prose disagrees): team/evidence/ (v2, empty) and archive/orchestration-v1/ (v1, stale reference only)

SINGLE TEAM: do NOT load team-mesh.

CURRENT DIRECTIVE (verify it too — being in this prompt does not make it true): Rewrite the ask_chatgpt library from scratch — archive the current implementation and rebuild it. ask-chatgpt is a Python tool for programmatic interaction with chatgpt.com via a CDP-attached, operator-signed-in Chromium (Playwright). The precise "what to support" + "how to rework" come from the operator IN THIS SESSION, refined via a grill-me session into a spec.

CRITICAL — RE-VERIFY FROM GROUND TRUTH before building on any claim:
- Installed-tool isolation (load-bearing safety): the installed ask-chatgpt is an ISOLATED COPY that uv tool install built from git branch `stable`, in its own frozen venv. A SEPARATE AGENT is using it. Editing the working tree cannot affect it. INVARIANTS: never move/commit `stable`; never run uv tool install/upgrade/reinstall; work on main/feature branches. Confirm: `git rev-parse stable` (expect unmoved), `git status`, `git log --oneline -8`.
- Acceptance: `uv run pytest` (mock; real_site deselected AND gated on ASK_CHATGPT_REAL=1) — inspect output/artifacts, not exit codes. uv run = project venv, separate from the tool install.
- State of tree: team/ + archive/orchestration-v1/ committed at setup. src/ask_chatgpt/driver.py is dirty (v1 WIP, to be superseded — confirm keep/discard with the operator).

IMMEDIATE NEXT ACTIONS (mission M0 — intake):
1. Confirm the isolation invariants still hold (cheap ground-truth probe).
2. Receive the operator's initial rework context (what to support + how to rework).
3. Run the grill-me skill to interrogate the requirements to shared understanding, resolving each branch of the design tree. Adversarially review every planned GPT-facing prompt (a past bug: prompt wording predetermined test outcomes).
4. Distill into a spec: APPEND it to team/charter.md (replace the "Rework spec — pending" placeholder) and populate the mission queue in team/state/live-state.json (archive current library → best-of-N design → single-editor implementation → independent verification).
5. Then run the lead loop: author self-contained manager contracts (copy charter constraints verbatim — workers inherit nothing) → dispatch via the configured launch mechanism → smoke-check shipment not liveness → ingest → report → checkpoint.

RESERVED ACTIONS (escalate to me in-session; do NOT self-decide): credentials/secrets/sudo/privileged installs; real external accounts or paywalled material; irreversible outbound effects (git push / merge to a published branch); the manual-compaction trigger; irreducible directive ambiguity; team create/retire. Everything else is autonomous against the directive's own criteria.

---

/grill-me Here is the context for what we are building:

We will be archiving the current `ask-chatgpt` tool and rewriting it to be better. The current tool can be used as a reference to help us in our rewrite and remain aware of "gotchas". The tool I am imagining is a command-line tool that can manipulate the ChatGPT.com webui and mirror its basic functionality. Below I describe some features:
1. maintain multiple concurrent conversations (can use multiple tabs)
2. Send a prompt and read the response -- this is the main usage.
  1. include attachments in prompt
  2. add other tools like "Deep Research" or connect to other apps under the "More" option. See attached image #1.
  3. change model type. See image #2. 
  4. Conversation can be maintained based on URL or session-ID. URL is probably preferred since it may be a more robust representation of the chat. Chats can both be a standalone chat (see https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31) or a project chat (see https://chatgpt.com/g/g-p-6a22e7320f28819198bddc4745ecca59/c/6a3417b1-5638-83ea-bb42-d5a330213940). Note the URLs are different.
  5. save the markdown response, see Image #3
  6. save any attachments in the respone, see image #4 
  7. keep an internal jsonl record of all chat transcripts, in supported markdown (deep research requires a different approach though, not as easy to just copy). Attachments can be lazily downloaded to an `attachments/` folder that is gitignored and referenced in the jsonl transcript. Tool needs to be able to fetch from the transcript.
3. Provide detailed status of tool.
4. Scrape old transcripts from old sessions. This is important because we have one long covnersation at https://chatgpt.com/c/6a316aa8-5dc8-83ea-9014-b8ea38dabc31 that needs to have its transcript scraped.

A composite workflow involves sending "keep pushing!!" to Pro Extended on a problem. This leverages (2) in a loop. An agent should be able to use the `ask-chatgpt` tool to easily execute this flow.

I recommend *mirroring* ChatGPT.com functionality in this tool that can be used from the commandline. You are free to use any language (e.g. typescript, python, etc.) that you want.