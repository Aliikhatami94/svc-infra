# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

We actively support the latest minor version. Security patches are backported to the current minor release only.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Report Here**: [nfrax.com/?feedback=1](https://www.nfrax.com/?feedback=1)

Select "Security Issue" as the feedback type.

**Expected Response Time**:
- Initial acknowledgment: within 48 hours
- Status update: within 7 days
- Resolution timeline: depends on severity (critical: 7 days, high: 30 days, medium: 90 days)

### What to Include

Please include the following in your report:

1. **Description**: Clear description of the vulnerability
2. **Reproduction Steps**: Step-by-step instructions to reproduce the issue
3. **Impact Assessment**: What an attacker could achieve by exploiting this
4. **Affected Versions**: Which versions are affected (if known)
5. **Suggested Fix**: If you have ideas for remediation (optional)

### What NOT to Do

- Do not open public GitHub issues for security vulnerabilities
- Do not exploit the vulnerability beyond what's necessary to demonstrate it
- Do not access or modify data belonging to others

## Disclosure Policy

1. **Report received**: We acknowledge receipt within 48 hours
2. **Triage**: We assess severity and validity within 7 days
3. **Fix development**: We develop and test a fix
4. **Coordinated disclosure**: We coordinate with you on disclosure timing
5. **Public disclosure**: We publish a security advisory after the fix is released

We aim for a 90-day disclosure timeline, but may request extensions for complex issues.

## Security Update Process

1. Security fixes are released as patch versions (e.g., 0.1.x → 0.1.x+1)
2. All security releases include a GitHub Security Advisory
3. Users are notified via:
   - GitHub Security Advisories
   - CHANGELOG.md updates
   - PyPI release notes

## Authentication & Cryptography Components

svc-infra includes security-critical components that require extra care:

### Authentication (`svc_infra.auth`)
- OAuth 2.0 / OIDC integration
- Session management
- JWT handling
- Password hashing (Argon2)

### Cryptography
- Webhook signature verification (HMAC-SHA256)
- API key generation
- Token encryption

**If you find vulnerabilities in these components, please report them with HIGH priority.**

## Security Best Practices for Users

When using svc-infra:

- **Secrets**: Never hardcode secrets. Use environment variables and fail loudly in production if missing.
- **Database**: Always use parameterized queries. Never interpolate user input into SQL.
- **Authentication**: Use the built-in auth modules instead of rolling your own.
- **Rate Limiting**: Configure rate limiting on public endpoints.
- **Webhooks**: Always verify webhook signatures before processing.
- **Sessions**: Use secure, HttpOnly cookies with proper SameSite settings.

## Contact

For security inquiries: [nfrax.com/?feedback=1](https://www.nfrax.com/?feedback=1)

For general questions: Open a GitHub issue or discussion at [github.com/nfraxlab](https://github.com/nfraxlab).
