# Launchbot TODO

## Pantheon Deploy Key

- Status: blocked on GitHub repository admin action.
- Add the VM-generated public key as a read-only deploy key on `staffany-eng/pantheon`.
- Key title: `launchbot-pantheon-readonly`.
- Public key:

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILFnaYc4wzzJqoZmThJRtZp+yF9YDGYSreQ93MXn5Y1c launchbot-pantheon-readonly
```

- Keep `Allow write access` unchecked.
- After adding the key, verify from `hermes-data-bot-poc`:

```bash
~/.hermes/profiles/launchbot/scripts/launchbot-update-pantheon-repo.sh
~/.hermes/profiles/launchbot/scripts/launchbot-check-health.sh
~/.hermes/profiles/launchbot/scripts/launchbot-audit-live-profile.sh
```
