# Security

Keep tokens, refresh credentials, authorization callbacks and issued upload URLs
in an appropriate secret store. Examples require caller-supplied credentials and
contain no account data. Tests use synthetic values and mocked HTTP.

Do not include credentials or private responses in public issues. Use GitHub's
private vulnerability-reporting feature when available for a security report.
The default transport rejects redirects and credential forwarding to issued
storage URLs. An uncertain mutation is never automatically replayed.
