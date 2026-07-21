# Secure Active Directory Connections

`ADConnection` supports explicit validated LDAPS, GSSAPI and simple-bind authentication, bounded
read recovery, safe diagnostics, and supported cleanup. Configuration is per connection; the
package does not read credentials, server names, search bases, or CA material from fixed environment
variables.

## Compatibility Default

Omitting `tls` preserves the historical package behavior:

```python
connection = ADConnection(servers, search_base)
```

That path uses `ssl.CERT_NONE` and the previously pinned TLSv1.2 protocol. It does not validate the
certificate chain or hostname. It remains the default for compatibility; new security-sensitive
integrations should explicitly select `ADTLSConfig.secure()`.

## Validated LDAPS

```python
from python_apis.apis import ADConnection, ADTLSConfig

connection = ADConnection(
    servers,
    search_base,
    tls=ADTLSConfig.secure(),
    connect_timeout=5,
    receive_timeout=30,
)
```

Secure mode uses:

- `ssl.CERT_REQUIRED` certificate-chain validation.
- The operating-system trust store when no CA source is supplied.
- Hostname/SAN validation against each configured server.
- Modern protocol negotiation through the default client context (`version=None`).
- The platform's authenticated high-strength cipher defaults when `ciphers` is omitted.
- Per-server SNI and optional explicit server ports.

The server names used by the application must appear in the certificate SAN. A custom trust source
can be supplied when the issuing CA is not installed in the process host's trust store:

```python
tls = ADTLSConfig.secure(
    ca_certs_file=configured_ca_file,
    # Or ca_certs_path=... / ca_certs_data=...
)
```

Trust and cipher settings are validated before LDAP objects are constructed. Safe configuration
errors do not copy CA contents, file paths, server identities, or OpenSSL diagnostic text into the
public message.

## Authentication

GSSAPI remains the default:

```python
connection = ADConnection(servers, search_base, tls=ADTLSConfig.secure())
```

Simple bind is explicit and requires validated TLS:

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

Supplying simple credentials without `CERT_REQUIRED` fails before LDAP construction. The package
retains private inputs only for supported reconnect behavior and removes username/password from the
bound ldap3 object's public representation. Simple-bind referrals are disabled so credentials are
not carried into referral connections.

## Legacy Leaf Keys

Some validated servers have a trusted certificate chain but a leaf key rejected by the current
OpenSSL security level. A temporary compatibility mode can lower the security level for that
connection only:

```python
tls = ADTLSConfig.secure(legacy_leaf_key_compatibility=True)
```

This mode:

- Keeps `CERT_REQUIRED`.
- Keeps hostname/SAN validation.
- Does not enable `CERT_NONE` or plain LDAP.
- Emits a value-free warning.
- Cannot be combined with a caller-selected cipher expression.

Treat it as a time-bounded certificate-remediation bridge.

## Lifecycle and Recovery

```python
with ADConnection(servers, search_base, tls=ADTLSConfig.secure()) as connection:
    entries = connection.search_strict(search_filter, attributes)
```

`close()` is idempotent. Context exit does not suppress an operation exception, and an unbind
failure does not mask the original error.

Read operations retry recoverable communication/session failures once by default after a fresh
bind. The complete query restarts and partial pages are discarded. Writes default to no automatic
retry because the server may have applied a write before its response was lost.

## Logging and Errors

ldap3 detail logging is off by default. When package-controlled BASIC logging is enabled, sensitive
data stripping is enabled first. Do not enable protocol/network detail in production because those
levels can include request and response values.

Use stable exception `error_code` values and masked retry telemetry for operational routing. Do not
log exception causes, raw ldap3 results, complete filters, DNs, attributes, or returned identities.

See [the opt-in migration guide](migration/ad-secure-connection-opt-in.md) for existing callers and
[authorization membership](ad-authorization-membership.md) for fail-closed group reads.
