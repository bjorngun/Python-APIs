# Opt In to Validated AD Connections

Issue #54 adds secure connection configuration without changing the TLS behavior of existing
callers. The expected release impact is `semver:minor`.

## Existing Callers

No source change is required to preserve current behavior:

```python
connection = ADConnection(servers, search_base)
```

This continues to use unvalidated `CERT_NONE` TLS with the historical TLSv1.2 protocol setting.
That compatibility choice is not a security recommendation.

## Secure Opt-In

The adoption change is explicit and small:

```python
from python_apis.apis import ADConnection, ADTLSConfig

connection = ADConnection(
    servers,
    search_base,
    tls=ADTLSConfig.secure(),
)
```

Before enabling it:

1. Install the issuing CA chain in the process host's trust store, or configure an approved CA
   file/path/data source.
2. Ensure every configured server DNS name appears in its certificate SAN.
3. Test the connection from the deployed process identity and network path.
4. Keep the old connection path behind a consumer-owned rollback switch until parity is accepted.

There is no silent fallback to `CERT_NONE` when explicit secure TLS fails.

## Simple Bind

Simple bind is additive but cannot use the unvalidated compatibility default:

```python
connection = ADConnection(
    servers,
    search_base,
    authentication="simple",
    username=secret_provider_username,
    password=secret_provider_password,
    tls=ADTLSConfig.secure(),
)
```

Keep credentials in the consumer's secret provider. Do not place them in package configuration
files, source, exception text, telemetry, or logs.

## Certificate Remediation Bridge

`ADTLSConfig.secure(legacy_leaf_key_compatibility=True)` is only for a trusted, hostname-valid
certificate whose leaf key is rejected by the current OpenSSL security level. It still requires the
CA chain and hostname to validate. It is not equivalent to the omitted unvalidated default.

## Rollout

1. Validate trust, SAN, authentication, timeouts, and cleanup outside the request hot path.
2. Run old and secure connection paths in parity mode without database writes.
3. Canary the secure path with masked aggregate diagnostics.
4. Cut over and retain rollback for an agreed observation period.

Do not use removal of `ADTLSConfig.secure()` as an operational rollback. Roll back to the previous
consumer path or package release while retaining the last valid downstream state.
