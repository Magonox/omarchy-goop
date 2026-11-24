# Security policy

Goop looks at what is in a window you point it at and sends that, with your question, to the agent you chose. It can also type into terminals and move files, each time behind an
approval card. So the things that matter most are: private text leaving the machine, something acting without an approval, and files readable by other accounts on the same computer.

## Reporting a vulnerability

Please report it privately, not in a public issue:

1. Go to the **Security** tab of this repository and choose **Report a vulnerability** (GitHub private vulnerability reporting).
2. If that button is not there, open a public issue titled **"Security: please contact me"** with no details, and a way to reach you will be arranged.

Please include what you found, where (file and line if you can), the steps to reproduce it, and what an attacker could do with it. You will get an answer as soon as it can be read,
and a fix is made on a pull request like any other change, with credit to you if you want it.

## What is covered

The latest version on `main`. Goop is young and has one maintainer, so older versions are not patched separately.

Examples of what counts: a question, window text or screenshot readable by another local account (folders under `~/.cache/goop` are meant to be owner-only), text of a question showing up in a process
list, an action that runs without its approval card or ignores the access level (Look only, Ask first, Ask for everything), a file read outside what the access level allows, generated 3D lesson
code that escapes its sandbox (`daemon/goop/explainer/codegen.py`), or the optional Chromium page reader reading pages it was not asked to read.

## What Goop sends where

See "Privacy and permissions" in the [README](README.md): questions and window context go to your own agent (the Claude Code CLI by default), a 3D lesson sends its topic and a short summary to the
model that plans it, voice runs on your computer, and there is no telemetry, account or server of ours.

Earlier reports, all fixed: a question visible in a process list, `~/.cache/goop` readable by other accounts, lesson code importing a private file, native file reads ignoring the access level, image
links in replies fetched without approval, and lesson text in command-line arguments. The history is in [CHANGELOG.md](CHANGELOG.md).
