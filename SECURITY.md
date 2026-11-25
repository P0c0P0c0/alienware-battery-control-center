# Security

The approved vulnerability reporting channel is **GitHub Private Vulnerability Reporting**. Activation is pending repository creation. Once it is enabled, use **Security → Report a vulnerability** in the project repository. Until then, keep vulnerability details private and use a private reporting channel already agreed with the owner if you have one. Avoid public issues and pull requests for vulnerability disclosures.

Include the version, affected component, operating system, impact and a minimal reproduction using synthetic data. Remove usernames, home paths, battery serials, raw databases, session tokens and full journal dumps. For screenshots, crop or redact desktop notifications and identifying information.

The backend holds the write privilege for its SQLite state and reads firmware attributes. The dashboard and notification helper are unprivileged readers. Root-side deployment requires a trusted administrator-owned payload and explicit consent. Keep the state permissions intact when sharing history. Keep AppArmor, bwrap, the image-loader sandbox and systemd restrictions enabled.

See [review findings](RELEASE_REVIEW.md) and [runtime dependency licensing](DEPENDENCIES.md).
