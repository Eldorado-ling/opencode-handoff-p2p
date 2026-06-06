# Changelog

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
