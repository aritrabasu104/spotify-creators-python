# Security

Keep tokens, refresh credentials, authorization callbacks and issued upload URLs
in an appropriate secret store. Examples require caller-supplied credentials and
contain no account data. Tests use synthetic values and mocked HTTP.

Do not include credentials or private responses in public issues. Use GitHub's
private vulnerability-reporting feature when available for a security report.
The default transport rejects redirects and credential forwarding to issued
storage URLs. An uncertain mutation is never automatically replayed.

HTTP transport failures expose a typed, sanitized exception. Read failures use
`TransportUnavailable` (an `OSError`); dispatched mutations remain
`OutcomeUnknown`. Default tracebacks suppress credential-bearing transport
messages and signed URLs. Do not log private exception attributes or response
bodies. The publication tests reject machine-specific paths, literal account
secrets and undeclared/private imports from the package source.
