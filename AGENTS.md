# PBRT-v4 Art Studio Agent Bootstrap

This repository is an evolving artistic medium, not a generic PBRT sample or a
single-algorithm experiment.

Before analyzing, editing, rendering, committing, or proposing next steps:

1. Read `docs/continuity.md` completely. It is the canonical current handoff.
2. Follow its **New-thread continuity protocol** and read the routed artistic,
   architectural, or subsystem documents relevant to the task.
3. Verify the current Git branch and worktree. Active application development
   belongs on `pbrt-v4-art-studio`. Do not alter or delete historical branches.
4. Treat the older root `HANDOFF*.md` files as historical evidence only. They
   do not override current branch, path, configuration, or next-step decisions.

Core safeguards:

- `scene_workspace/config.json` is the one authoritative live scene
  configuration. Do not create a second scene JSON for a new landform, module,
  preview, or experiment unless the artist explicitly changes this rule.
- Preserve accepted visual states and checkpoint them before materially
  changing them.
- A continuity checkpoint is complete only after the active branch is pushed
  to GitHub and `docs/continuity.md` is copied to
  `gdrive:wipImages/pbrt-v4/SessionArchive/continuity.md`.
- Inspect local archived PNGs directly; do not wait for Google Drive before
  evaluating a completed render.
- New GUI and configuration work must preserve direct manual JSON editing and
  must not change the PBRT-v4/CUDA build unless the artist explicitly requests
  build work.

If repository state conflicts with `docs/continuity.md`, stop and resolve the
discrepancy before proceeding rather than guessing which state is authoritative.
