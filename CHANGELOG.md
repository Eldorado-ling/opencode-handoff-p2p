# Changelog

## Unreleased

### Compatibility

- Keep `SKILL.md` discovery metadata within OpenCode's 1024-character description limit.
- Accept current and legacy OpenCode share URL forms, including `/s/` paths and IDs containing `_` or `-`.

### Reliability and security

- Reject nested inbox paths, impossible timestamps, invalid GitHub usernames, malformed repo arguments, and clone/repo mismatches.
- Fail closed when `git ls-files` fails instead of reporting a false empty inbox.
- Add timeouts to external commands.
- Correct threat-model wording for unsigned metadata spoofing, replay, and hardware signing keys.
- Add cross-platform, multi-version CI and a standard-library test suite.

## v1.0.1 — 2026-06-07

### Security fixes (CRITICAL)

- **Tier 4/5 identity verification bypass via post-add modification**
  
  Previously the script used `get_add_sha()` which queries `git log --diff-filter=A`
  to find the original commit that ADDED a file. If a collaborator subsequently
  MODIFIED the file (changing the blob content), Tier 4 would still see the
  original add commit (with the legitimate sender's authorship and signature)
  while Tier 3 reads the current malicious blob — bypassing identity verification
  entirely.

  Fix: renamed to `get_last_modifying_sha()` using `git log -1 --format=%H`
  (without `--diff-filter=A`). This returns the most recent commit that touched
  the file, which is what produced the current blob content. Tier 4/5 now
  correctly verify the commit responsible for the current state.

  Reported by Gemini Code Assist on PR #4 to TheArchitectit/awesome-opencode-skills.

### Bug fixes

- **Clone fails for SSH-default `gh` users**

  Previous hardening flags included `-c protocol.allow=never` with only HTTPS
  explicitly enabled. Users who configured `gh` with SSH (e.g. via
  `git config --global url.git@github.com:.insteadOf https://github.com/`)
  could not bootstrap because SSH was blocked.

  Fix: explicitly allow both protocols — `-c protocol.https.allow=always`
  AND `-c protocol.ssh.allow=always`. Other protocols (file, git://, etc.)
  remain blocked.

  Reported by Gemini Code Assist on PR #4 to TheArchitectit/awesome-opencode-skills.

## v1.0.0 — 2026-06-06

Initial release of the P2P-only variant.

### Why this skill exists

A simplified version of [opencode-handoff](https://github.com/Eldorado-ling/opencode-handoff-skill) that supports only the P2P mode (each user owns one personal private inbox repo). Drops the shared central repo mode. Smaller attack surface, simpler configuration, clearer trust model.

### Features

- 5-tier verification pipeline (filename / trust / content / commit attribution / signature)
- Each user owns one private inbox repo (`<username>/opencode-handoff-inbox` by default)
- Transactional receive: fetch URL content before deleting inbox file
- Reference Python implementation (`verify_inbox.py`) replaces shell pseudocode
- Chinese-language trust boundary preamble + standardized user-facing messages
- Documentation: README + INSTALL + USAGE

### Security

- Strict input validation regexes (filename, URL, username, repo path)
- Clone-time hardening (`-c core.symlinks=false`, `protocol.file.allow=never`, etc.)
- Trust config isolated from OpenCode's project config merger
- Subprocess environment hardening (`GIT_CONFIG_NOSYSTEM=1`, etc.)
- ASCII-only byte-level content validation
- Tier-1 failures never trigger shell ops on the malformed filename
- Trust boundary preamble + AGENTS.md hard rule against handoff-content-driven local writes

### Differs from opencode-handoff (combined)

- No `shared_repo` config option
- No "P2P first, fallback to shared" mode selection
- Smaller SKILL.md (~440 lines vs ~635)
- Per-user collaborator list is the only access control
- Doesn't scale beyond ~5 people (N(N-1) collaborator invites)

### Known limitations

Same as the combined skill — see SKILL.md "Threat model and limits" section.
