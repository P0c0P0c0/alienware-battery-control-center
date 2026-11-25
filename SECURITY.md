# Security

Version 1.0.0 is a local release candidate. Route suspected security issues privately to the release owner through your existing contact channel. A public reporting address or advisory intake must be confirmed before publication. Keep technical details private until the issue has been reviewed.

Useful reports include the version, affected component, operating system, severity and minimal reproduction using synthetic data. Remove usernames, home paths, battery serials, raw databases, session tokens and full journal dumps. For screenshots, crop or redact desktop notifications and identifying information.

The backend holds the write privilege for its SQLite state and reads firmware attributes. The dashboard and notification helper are unprivileged readers. Root-side deployment requires a trusted administrator-owned payload and explicit consent. Do not change the state permissions to share history. Do not disable AppArmor, bwrap, the image-loader sandbox or systemd restrictions.

See [review findings](RELEASE_REVIEW.md) and [runtime dependency licensing](DEPENDENCIES.md).
