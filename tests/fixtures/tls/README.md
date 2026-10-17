# Local TLS regression fixtures

These certificates and the intentionally public server private key are ONLY for
socket-pair tests. Never install them into a system trust store or deploy them.
They were generated with cryptography using RSA-2048 and SHA-256. No production
key or certificate is included. Tests need only the Python standard library and
the declared Windows truststore runtime dependency, with no public network.

The root and live intermediate/localhost leaf are valid 2020-01-01 to 2044-01-01.
The expired intermediate has the same subject and public key as the live one,
but expired 2021-01-01. The expired leaf also expired 2021-01-01. A server sends
its leaf plus live intermediate while the client trusts the root and optionally
loads the expired intermediate, reproducing OpenSSL's stale-chain preference.
