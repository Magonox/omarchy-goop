# Publishing to the Omarchy plugin marketplace

Researched 2026-10-30 from plugins.omarchy.org and `omacom/omarchy-plugin-marketplace`. Re-check before submitting: it changes.

## What it is
plugins.omarchy.org is a community registry (Verified / Unverified, sortable by recently added, stars, views, copies, hearts, rank,
install rate). It "validates listings, not plugin security": plugins run unsandboxed inside omarchy-shell.

## What a listing needs
- A **public GitHub repo** with `manifest.json` in the root (one plugin per repo), a root **README with install and removal
  instructions**, a root **license file**, and documented external dependencies.
- **Plugin id**: globally unique, lowercase, namespaced, outside `omarchy.*`, e.g. `io.github.<user>.<name>`.
  **Ids are permanent** and cannot be reused after a rename or retirement. Search the marketplace for the id first.
- Optional `preview.png` in the repo root (up to 50 MB / 40 MP); the marketplace makes the card and detail images.
- One **category** (case-sensitive): Appearance, Desktop, Developer Tools, Hardware, Kids, Productivity, System, Widgets, Other.
  One to three **tags**: ai, bar, education, games, hyprland, kids, launcher, media, power-management, quickshell, security, system,
  vpn, workspaces. Planned for Goop: category **Productivity** (the marketplace allows one; `Kids` would overstate it, since Goop is a general AI helper) with tags `ai`, `education`, `hyprland`. Decided 2026-11-04: no kids positioning.
- `omarchy plugin validate .` must pass (no symlinks inside the plugin folder; the voice venv lives outside the repo for this reason).

## How to submit
Via the issue form on `omacom/omarchy-plugin-marketplace`, or the CLI: fill the template from SUBMISSION.md and run
`gh issue create` (title `[Plugin]: Goop`; keep all six headings and five checklist items). An AI agent may prepare the text but
creates the issue only after the owner approves it. Then: a scan of the exact commit, then a maintainer's `approved-and-verified`.
A current passing baseline is automatically marked Verified (not a security audit).

## Automated security baseline (what the scan looks at)
- **Blocking (`needs-fixes`)**: `curl`/`wget` output run by a shell; `cargo install --git` without a 40-char `--rev`; external git
  code built/run unpinned; dangerous NOPASSWD sudoers rules; privileged process control from a predictable `/tmp` PID file.
- **Maintainer review (`review-required`)**: installer scripts, package managers, `sudo`/`pkexec`, remote builds, bundled
  executables (ELF/PE/Mach-O), service management, sudoers changes.
- **Limits**: at most 1,000 relevant files, 8 MiB text total, 512 KiB per text file (tests/fixtures/dependencies are excluded).
  An incomplete scan fails closed.
- **Goop's exposure**: `setup.sh` is an installer using pip and downloading a voice model, so expect `review-required`, not a
  rejection. It has no `curl | sh`, no sudo, no unpinned remote code, no binaries. Biggest file `shell/Goop.qml` is about 38 KB.

## Featured sections
The site has "Hidden Gems" and "Just Landed"; how plugins qualify is not documented. Stars, views and copies drive ranking, so the
README, preview image and launch videos matter.

## Marketing videos: `latent-spaces/brag`
An open-source (MIT) agent skill that turns a project into a ~20 s launch video (music, motion, share copy): outputs
`brag-output/` with a plan, composition brief, share copy and `brag.mp4`. Install in Claude Code with
`/plugin marketplace add latent-spaces/brag` then `/plugin install brag@brag`; run `/brag` (options: `--tone "..."`, `--voice`).
Needs Node 22+, FFmpeg and `npx hyperframes`. One run makes one video, so run it once per feature. Installing the skill changes the
owner's Claude Code setup, so try it in a scratch directory first.

## Naming notes
No existing "goop" plugin turned up in a quick search (the neighbours are AI chat plugins such as Quick Chat). Avoid camelCase and the
"omarchy" prefix in the product name: the registry already sits inside Omarchy, and an `omarchy-` name can read as official. Use it
in the repo name only (`omarchy-goop`), where it helps search.
