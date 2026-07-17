# blogdeploy

A small, stdlib-only Python tool that rebuilds and publishes a Hugo blog when a GitHub
webhook fires. It clones the blog's repo at the configured branch, builds it with Hugo,
publishes the result as a new release under `/srv/<domain>/releases/`, and atomically
flips a `current` symlink to it — with old releases pruned and email notification on
failure (and optionally on success).

## Usage

```
python -m blogdeploy <blogkey>
```

`<blogkey>` is one of the keys listed in `BLOGS=` in `blogdeploy.conf` (e.g. `jre` or
`oos`). This is what the `webhook` service invokes when a signed push webhook arrives — see
`webhook/hooks.json.tmpl` and `systemd/override.conf`. Exit code is `0` on success,
non-zero on failure (and a failure email is sent either way an error occurs).

## Runtime: stdlib-only

The `blogdeploy` package (see `pyproject.toml`: `dependencies = []`) uses only the
Python 3.11+ standard library at runtime — no pip installs are needed on the deploy VM.
It shells out to `git` and `hugo`, which must be present on the VM (installed by
`cloud-init/blog-vm.vendor.yaml`), but the Python process itself has no third-party
dependencies. Crucially, the package never calls `op` (1Password CLI) — the VM does not
have it installed, and secrets reach the VM already resolved (see below).

## Config and secrets

Two different trust levels are involved, and only the non-secret one is ever committed:

- **`blogdeploy.conf`** — a plain `KEY=VALUE` blog registry (repo URL, branch, domain,
  serve root, `KEEP_RELEASES`). No secrets. `blogdeploy.conf.example` in this repo shows
  the shape; `cloud-init/blog-vm.vendor.yaml` writes the real one to
  `/etc/blogdeploy/blogdeploy.conf` on the VM directly, since it contains nothing
  sensitive.
- **`ref.env`** and **`webhook/hooks.json.tmpl`** — templates containing `op://...`
  1Password references (SMTP credentials, webhook HMAC secrets) instead of real values.
  These *are* committed, because they hold no secrets, only pointers to where the
  secrets live in 1Password.

Resolving those templates happens on the **workstation**, never on the VM. Copy each
committed template to a gitignored local copy, put your real 1Password refs there, then
inject. (`op inject` resolves `op://` references anywhere in the file — comment lines
included — so keep reference-shaped tokens out of comments, or the run aborts.)

```
cp ref.env ref.local.env                            # edit: real refs + SMTP host/from
cp webhook/hooks.json.tmpl webhook/hooks.local.json # edit: real webhook-secret refs
op inject -i ref.local.env           -o .env
op inject -i webhook/hooks.local.json -o hooks.json
```

The resulting `.env` and `hooks.json` contain real secrets and are gitignored (see
`.gitignore`) — they must never be committed. They get copied to the VM during
provisioning: the SMTP env to `/etc/blogdeploy/.env`, and the resolved hooks to
`/etc/webhook.conf` — the path the packaged `webhook.service` reads, guarded by its
`ConditionPathExists` so the listener stays inactive until the file is present. A small
systemd drop-in (`systemd/override.conf`) adds `EnvironmentFile=/etc/blogdeploy/.env` and
runs the listener as the unprivileged `blogdeploy` user. The VM itself never runs `op` and
never needs 1Password access.

## Repo layout

- `blogdeploy/` — the Python package (`config`, `build`, `notify`, `__main__`).
- `tests/` — the pytest suite.
- `caddy/Caddyfile` — reverse-proxy-free static file server config for both blogs on
  port 80, keyed by `Host` header.
- `webhook/hooks.json.tmpl` — `webhook` hook definitions (HMAC-signed GitHub webhooks
  trigger `python -m blogdeploy <key>`); resolved to `/etc/webhook.conf` on the VM.
- `systemd/override.conf` — drop-in over the packaged `webhook.service`: runs the
  listener as the unprivileged `blogdeploy` user, loads `/etc/blogdeploy/.env`, and
  re-declares `ExecStart` with `-verbose` so deliveries are logged (`journalctl -u webhook`).
- `cloud-init/blog-vm.vendor.yaml` — cloud-init vendor data that provisions a fresh VM:
  installs Hugo (extended, pinned version), Caddy, and `webhook` (Debian package), clones
  this repo, creates the `blogdeploy` user and `/srv/*` directories, and installs the
  Caddyfile and the webhook drop-in. It deliberately does **not** place `.env` or the hooks
  file — those are injected and copied in during a later provisioning step, and the packaged
  webhook listener only starts once `/etc/webhook.conf` exists.
- `ref.env` — op-reference template for the resolved `.env` (SMTP settings).
- `blogdeploy.conf.example` — example of the non-secret blog registry.

## Tests

```
python -m pytest
```

All builder, config, notify, and CLI entrypoint logic is covered with injected `runner`
and `now` fakes — no real network, git, Hugo, or SMTP calls happen in the test suite.

## Provisioning

This repo only contains the application and its static runtime artifacts. Actually
standing up the VM — DNS, firewall, 1Password item layout, `op inject` + copying
`.env`/`hooks.json` to the VM, and starting the `webhook` service — is covered by a
separate provisioning runbook ("Plan 2"), not included in this repository.
