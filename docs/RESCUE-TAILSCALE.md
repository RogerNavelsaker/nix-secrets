# Rescue Tailscale credential policy

Status: policy contract recorded. On 2026-10-05, the operator confirmed that key/secret encryption, decryption, and injection were successfully tested and deployed with the rescue ISO. This operational report does not independently establish current Tailnet control-plane settings or join-time cleanup. Never put an auth-key value in this document, Git, command output, or logs.

## Credential contract

- Use a dedicated rescue-only Tailscale auth key. Do not reuse a production-wide key.
- The intended tag is `tag:rescue`; the key must be pre-authorized for that tag.
- The current replacement key's properties were reported by the operator as reusable, ephemeral, and pre-approved. These settings have not been independently checked in the Tailnet control plane. Reusable describes the key; ephemeral describes the nodes it authorizes.
- Before relying on the key, verify that the principal creating it is allowed to assign `tag:rescue`, and that the Tailnet ACL/grants constrain rescue-tagged nodes to the minimum rescue access. Do not infer tag ownership or ACL behavior from the tag name alone.
- Record and review the configured key expiry in the control plane. Do not assume an expiry default. Rotate before expiry; revoke immediately on suspected exposure. Rotation means creating a replacement rescue-only key, updating the encrypted SOPS value, validating the rescue path, then revoking the old key. Do not retain plaintext copies.

## Storage and runtime lifecycle

- Store the auth key only in the encrypted rescue secret file at `hosts/iso/secrets.yaml`. A metadata-only check with `sops filestatus hosts/iso/secrets.yaml` reported `encrypted: true`; no plaintext was read for this check.
- SOPS decryption is gated by the rescue ISO's YubiKey/GPG unlock. Keep the resulting auth key in the SOPS-managed runtime secret under `/run`; never bake it into the ISO, Nix store, persistent storage, or a logged command.
- The ISO may join Tailscale only after the YubiKey-gated SOPS identity is available. After a successful join, remove the runtime auth-key file. A failed join must not cause the secret to be copied to persistent storage or emitted in logs.
- The ISO's temporary SOPS age-decryption identity and the final installed host's stable SSH identity have distinct roles; do not treat them as interchangeable credentials.

## Verification boundary

The operator-confirmed encryption/decryption/injection test establishes that the rescue secret flow was exercised and deployed. It does not independently establish that current Tailnet key flags, tag ownership, ACLs, expiry, join-time cleanup, or the latest live join match this contract. Verify control-plane settings without copying or displaying the secret value, and capture cleanup evidence before closing the policy issue. Physical installs remain separately gated by the rescue rollout plan.
