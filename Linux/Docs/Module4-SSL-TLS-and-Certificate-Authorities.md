# Module 4: SSL/TLS and Certificate Authorities
> Subject: Linux | Difficulty: Intermediate | Estimated Time: 285 minutes

## Objective

After completing this module, you will understand the Public Key Infrastructure (PKI) trust model well enough to design a certificate hierarchy for real deployments. You will create a two-tier private CA — a root CA and an intermediate CA — using the `openssl` command-line toolkit, then issue and sign server certificates suitable for internal AI API endpoints and service-to-service communication. You will configure Nginx and Apache to terminate TLS using those certificates. You will obtain publicly trusted certificates for internet-facing servers using Certbot and Let's Encrypt, automate renewal with both cron and systemd timers, and verify renewal works before it matters. You will convert certificates between PEM, DER, and PKCS#12 formats, install a private CA into the OS trust store and into browsers, set up mutual TLS (mTLS) so services can authenticate each other without passwords, and diagnose certificate errors using `openssl s_client` and related tools.

## Prerequisites

- Comfort with the Linux command line: navigating the filesystem, editing files with `nano` or `vim`, running commands as root with `sudo`
- Basic understanding of what a web server does and what HTTPS means conceptually
- `openssl` installed — verify with `openssl version` (version 3.x is assumed; most modern Linux distributions ship OpenSSL 3.0 or later)
- A Linux server or VM with Nginx or Apache installed for the web server sections
- For the Let's Encrypt section: a publicly reachable domain name pointed at your server (not required for private CA or dev sections)
- No prior cryptography knowledge is assumed, but familiarity with the concept of public/private key pairs is helpful

## Key Concepts

### PKI, the Chain of Trust, and Why It Exists

**Public Key Infrastructure (PKI)** is the system of roles, policies, hardware, software, and procedures needed to manage digital certificates and public-key encryption. Its purpose is to answer one question: "How does a client know it is really talking to the server it intended to reach, and not an impostor?"

The answer is the **chain of trust**. A **Certificate Authority (CA)** is an entity that issues digital certificates. A certificate is a signed document that binds a public key to an identity (a domain name, an IP address, an organization, or a service name). When a CA signs a certificate, it uses its own private key to add a cryptographic signature. Any party that trusts the CA can verify that signature using the CA's public key — if the signature is valid, the certificate is genuine and unmodified.

CAs form a hierarchy:

```
Root CA  (self-signed, stored in OS/browser trust stores)
  └── Intermediate CA  (signed by Root CA)
        └── Server Certificate  (signed by Intermediate CA)
```

**Root CAs** are the anchors of trust. Their certificates are self-signed and are distributed with operating systems and browsers. Because root CA private keys are extremely sensitive targets, root CAs are kept offline and sign only intermediate CAs — they almost never sign end-entity certificates directly.

**Intermediate CAs** do the day-to-day work of signing server and client certificates. If an intermediate CA is compromised, only it needs to be revoked; the root CA remains intact and can issue a replacement intermediate.

**End-entity certificates** (also called leaf certificates) are the certificates installed on servers and clients. They cannot sign other certificates — their `CA:FALSE` basic-constraint prevents this.

When a browser connects to your HTTPS server, it receives the server certificate and any intermediate CA certificates bundled with it (the **certificate chain**). The browser walks up the chain until it finds a certificate signed by a CA already in its trust store. If no trusted anchor is found, the connection is rejected with a certificate error.

### Certificate Anatomy and X.509 Fields

Every certificate used on the public internet (and most internal ones) follows the **X.509v3** standard. Understanding its fields helps you configure OpenSSL correctly and debug problems.

Key fields in an X.509 certificate:

| Field | Purpose | Example |
|---|---|---|
| Subject | Who the certificate belongs to | `CN=api.internal, O=Acme Corp` |
| Issuer | Who signed the certificate | `CN=Acme Intermediate CA` |
| Serial Number | Unique identifier within the issuing CA | `0x4A2F...` |
| Not Before / Not After | Validity window | `2025-01-01` to `2026-01-01` |
| Public Key | The subject's public key | RSA 4096-bit or EC P-256 |
| Subject Alternative Name (SAN) | Additional DNS names or IP addresses the cert is valid for | `DNS:api.internal, IP:10.0.1.5` |
| Key Usage | What the key may be used for | `Digital Signature, Key Encipherment` |
| Extended Key Usage | Higher-level purpose | `serverAuth, clientAuth` |
| Basic Constraints | Whether this cert can act as a CA | `CA:TRUE` or `CA:FALSE` |

The **Subject Alternative Name (SAN)** extension is the authoritative field for hostname validation. The older `Common Name (CN)` field is ignored for hostname matching by all modern TLS implementations. If you generate a certificate without SANs, browsers and `curl` will reject it even if the CN matches.

You can inspect any certificate's fields with:

```bash
openssl x509 -in server.crt -text -noout
```

### Certificate Formats: PEM, DER, and PKCS#12

Certificates and keys are stored in a few common serialization formats. Confusing them is one of the most common sources of errors.

**PEM (Privacy Enhanced Mail)** is the most common format on Linux systems. It is Base64-encoded DER data wrapped in `-----BEGIN CERTIFICATE-----` / `-----END CERTIFICATE-----` header lines. PEM files can contain a certificate, a private key, a chain, or all three concatenated together. File extensions are inconsistently applied — `.crt`, `.cer`, `.pem`, and `.key` are all frequently PEM files.

```
-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIJANZL3gFRHSdPMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNV
... (Base64 encoded DER data) ...
-----END CERTIFICATE-----
```

**DER (Distinguished Encoding Rules)** is the binary form. It is the actual ASN.1-encoded certificate without the Base64 wrapper. Windows and Java applications often expect DER. File extensions `.der` and `.cer` (when binary) indicate DER format.

**PKCS#12 (PFX)** is a container format that bundles a certificate, its private key, and optionally the full chain into a single password-protected binary file. It is the standard exchange format for importing into Windows, Java keystores, and many network appliances. File extensions are `.p12` or `.pfx`.

Convert between formats:

```bash
# PEM certificate to DER
openssl x509 -in server.crt -out server.der -outform DER

# DER certificate back to PEM
openssl x509 -in server.der -inform DER -out server.crt -outform PEM

# Bundle cert + key + chain into PKCS#12
openssl pkcs12 -export \
  -in server.crt \
  -inkey server.key \
  -certfile ca-chain.crt \
  -out server.p12 \
  -passout pass:changeme

# Extract certificate from PKCS#12 back to PEM
openssl pkcs12 -in server.p12 -nokeys -clcerts -out server.crt -passin pass:changeme
```

### Creating a Private CA: Root and Intermediate

A private CA is the right solution for internal AI infrastructure, development environments, internal microservices, and any scenario where Let's Encrypt is unavailable (air-gapped networks, private IP addresses, non-public hostnames). Instead of trusting a public CA whose policies you cannot control, you trust only your own CA, which issues certificates only to services you control.

A two-tier hierarchy (root + intermediate) is the minimum recommended structure even for internal use. The root CA private key is kept offline after creating the intermediate; all day-to-day signing is done by the intermediate. This means:

- If the intermediate CA key is ever compromised or needs rotation, you revoke it and issue a new one — the root and all its trust anchors remain valid.
- The root CA key is kept in a secure location (encrypted disk, HSM, or simply a locked-away encrypted USB drive).

The OpenSSL configuration file (`openssl.cnf`) defines all the constraints for each CA. Spending time on this file prevents signing certificates with insecure settings.

### TLS in Nginx and Apache

Web servers terminate TLS by reading the server's private key and certificate chain from disk, performing the TLS handshake with each connecting client, and then forwarding decrypted traffic to the application. For AI API endpoints, this means your Python FastAPI server, Node.js service, or any other backend can remain unaware of TLS entirely — the web server handles it.

**Nginx TLS configuration** (minimal, secure):

```nginx
server {
    listen 443 ssl;
    server_name api.internal;

    ssl_certificate     /etc/ssl/private/api.internal.crt;
    ssl_certificate_key /etc/ssl/private/api.internal.key;

    # Include the full chain so clients can verify the intermediate CA
    # (The ssl_certificate file should contain: server cert + intermediate cert)

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

**Apache TLS configuration** (minimal, secure):

```apache
<VirtualHost *:443>
    ServerName api.internal

    SSLEngine on
    SSLCertificateFile      /etc/ssl/private/api.internal.crt
    SSLCertificateKeyFile   /etc/ssl/private/api.internal.key
    SSLCACertificateFile    /etc/ssl/private/ca-chain.crt

    SSLProtocol             all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite          HIGH:!aNULL:!MD5
    SSLHonorCipherOrder     on

    ProxyPass        / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

### Mutual TLS (mTLS) for Service-to-Service Authentication

Standard TLS authenticates only the server — the client verifies the server's certificate but presents none of its own. **Mutual TLS (mTLS)** requires both parties to authenticate: the server presents a certificate to the client, and the client presents a certificate to the server. The server verifies the client certificate against its trusted CA list before accepting the connection.

mTLS is the correct pattern for internal AI service meshes where services call each other (e.g., an orchestration service calling an inference API). Instead of managing API keys or bearer tokens, each service gets a client certificate issued by your private CA. The receiving service trusts only certificates from that CA — no valid certificate, no connection.

```
Client Service                         AI Inference API
     |                                       |
     |-- ClientHello ----------------------->|
     |<-- ServerHello + Server Cert ---------|
     |     (client verifies server cert)     |
     |-- Client Cert + ClientKeyExchange --->|
     |     (server verifies client cert)     |
     |<-- Finished (encrypted channel) ------|
```

In Nginx, mTLS is enabled by adding to the `server` block:

```nginx
ssl_client_certificate /etc/ssl/private/ca-chain.crt;
ssl_verify_client      on;
ssl_verify_depth       2;
```

### Trusting a Private CA System-Wide and in Browsers

A certificate signed by your private CA will be rejected by any software that does not have your root CA in its trust store. Adding your root CA certificate to the system trust store makes all software that uses the system store (curl, wget, Python's `requests`, Node.js, etc.) accept certificates signed by your CA automatically.

**Ubuntu / Debian:**

```bash
sudo cp rootCA.crt /usr/local/share/ca-certificates/my-rootCA.crt
sudo update-ca-certificates
# Expected output: 1 added, 0 removed; done.
```

**RHEL / Fedora / Rocky Linux / AlmaLinux:**

```bash
sudo cp rootCA.crt /etc/pki/ca-trust/source/anchors/my-rootCA.crt
sudo update-ca-trust extract
```

**Firefox** maintains its own certificate store independent of the OS. To add a CA:
1. Open Settings > Privacy & Security > Certificates > View Certificates
2. Select the Authorities tab, click Import
3. Select your `rootCA.crt` file, check "Trust this CA to identify websites"

**Chrome and Edge** on Linux use the OS trust store on most distributions, so the system-wide steps above are sufficient. On some distributions you may additionally need to add the CA to Chrome's NSS database:

```bash
certutil -d sql:$HOME/.pki/nssdb -A -t "CT,," -n "My Root CA" -i rootCA.crt
```

### Debugging Certificate Errors with openssl s_client

`openssl s_client` is the most useful TLS diagnostic tool available. It initiates a TLS handshake to any server and prints exhaustive information about the certificate chain, protocol version, cipher suite, and any errors.

```bash
# Basic connectivity test
openssl s_client -connect api.internal:443

# Test with a specific CA file (for private CAs)
openssl s_client -connect api.internal:443 -CAfile /path/to/rootCA.crt

# Show the full certificate chain
openssl s_client -connect api.internal:443 -showcerts

# Test a specific TLS version
openssl s_client -connect api.internal:443 -tls1_3

# Test mTLS by presenting a client certificate
openssl s_client -connect api.internal:443 \
  -cert client.crt \
  -key client.key \
  -CAfile ca-chain.crt
```

Key lines to look for in the output:

```
Verify return code: 0 (ok)           <- Certificate chain fully verified
Verify return code: 18 (self-signed) <- Self-signed cert, not in trust store
Verify return code: 20 (unable to get local issuer certificate) <- Missing intermediate CA
Verify return code: 10 (certificate has expired)
```

## Best Practices

1. **Never store private keys alongside their certificates in the same publicly readable directory.** Private keys should be owned by root with `chmod 600` permissions. The web server process reads the key at startup — it does not need ongoing access. This prevents a directory traversal vulnerability from exposing your key.

2. **Always use a two-tier CA hierarchy for any long-lived private PKI, even for small teams.** The cost of setting it up once is low. The cost of rekeying every service because your root CA key was compromised is high. Keep the root CA key offline on encrypted storage from the moment the intermediate CA is signed.

3. **Include Subject Alternative Names (SANs) for every hostname and IP address the certificate must cover.** The CN field is ignored by modern TLS libraries for hostname validation. Omitting SANs will cause connection failures in curl, browsers, and most HTTP client libraries even if the CN appears correct.

4. **Set certificate lifetimes intentionally.** For private CAs, one year for server certificates is a reasonable default — long enough to avoid operational burden, short enough to limit exposure if a key is compromised. Root CAs are commonly issued for 10–20 years; intermediates for 5–10 years. Avoid issuing server certificates longer than two years.

5. **Bundle the intermediate CA certificate with your server certificate in the `ssl_certificate` file.** If clients must separately download the intermediate to build the chain, they will fail in restricted network environments. The correct bundle order is: server cert first, then intermediate cert(s), then (optionally) root.

6. **Automate renewal before certificates expire.** A certificate that expires on a Saturday night on a holiday will cause an outage. Certbot handles this automatically for Let's Encrypt certs. For private CA certs, build renewal into your deployment process or set calendar reminders at 60 and 30 days before expiry — or write a script that checks expiry dates and fires alerts.

7. **Test your TLS configuration with `openssl s_client` and a tool like testssl.sh before going live.** Specifically verify that the full chain is sent, that TLS 1.0 and 1.1 are disabled, and that the cipher suite does not include RC4, DES, or export-grade ciphers.

8. **For mTLS, issue a separate client certificate per service rather than sharing one across multiple services.** This lets you revoke a single compromised service's access without affecting the others. Name each certificate clearly in the CN or a SAN so logs show which service authenticated.

9. **Store Certbot-managed certificates in the default `/etc/letsencrypt/live/` path and always reference them by the symlinks, never the numbered archive paths.** Certbot rotates the underlying files on renewal but keeps the symlinks stable. Hardcoding the archive path means your web server points at an expired certificate after the first renewal.

10. **Validate certificate configuration in CI/CD pipelines.** Before deploying a new certificate or configuration change, run `openssl verify -CAfile ca-chain.crt server.crt` and `openssl s_client` in your pipeline. A failing cert in staging is a five-minute fix; a failing cert in production at 3 AM is not.

## Use Cases

### Securing an Internal AI Inference API

An organization runs a private LLM inference server on an internal network. The server should only be reachable over HTTPS, and only services with a valid client certificate may call it. The server is not publicly addressable, so Let's Encrypt cannot be used.

**Concepts applied:** Private root CA and intermediate CA creation, server certificate issuance with SAN for the internal hostname, Nginx TLS termination, mTLS client certificate verification, system-wide CA trust installation on all client machines.

**Outcome:** The inference API accepts only TLS 1.2 and 1.3 connections. Clients without a valid certificate signed by the internal CA receive a TLS handshake error before any request data is transmitted. Developers install the root CA certificate once, and all their tooling — curl, Python requests, internal dashboards — trusts the API automatically.

### Dev Environment with HTTPS for a Full-Stack Application

A development team builds a React frontend that calls a FastAPI backend. The frontend uses browser APIs (like `window.crypto` and service workers) that require a secure context — HTTPS — even on localhost. Let's Encrypt does not issue certificates for `localhost` or private IP addresses.

**Concepts applied:** Self-signed certificate generation, SAN configuration for `localhost` and `127.0.0.1`, importing the private CA into the browser and OS trust store, Nginx reverse proxy with TLS termination.

**Outcome:** Developers run a local Nginx instance that serves HTTPS on port 443. After importing the development CA once, their browsers show a green padlock on `https://localhost`, and all browser security APIs work correctly. No browser warnings interrupt development.

### Internet-Facing AI Web Application with Auto-Renewing Certificates

A company deploys a public-facing AI chatbot application at `chat.example.com`. It needs a browser-trusted HTTPS certificate at no cost, with zero downtime on renewal.

**Concepts applied:** Certbot installation, Let's Encrypt ACME challenge (HTTP-01 or DNS-01), Nginx plugin for automatic configuration, systemd timer for automated renewal, `--deploy-hook` for reloading Nginx after renewal.

**Outcome:** Certbot provisions a 90-day certificate signed by Let's Encrypt's trusted intermediate CA, writes an Nginx configuration snippet, and installs a systemd timer that runs `certbot renew` twice daily. Certificates are renewed 30 days before expiry with no manual intervention.

### Migrating a Windows Service to Accept Your Internal CA Certificates

A team integrates an AI API with an existing Windows-based internal tool that makes HTTPS requests to the API. The Windows application rejects the API's private-CA-signed certificate.

**Concepts applied:** PKCS#12 export, Windows certificate store import, understanding the difference between OS trust stores on Linux versus Windows.

**Outcome:** The root CA certificate is exported in PEM format, converted to DER, and imported into the Windows "Trusted Root Certification Authorities" store via the Microsoft Management Console (MMC) or `certutil -addstore`. After the import, all Windows TLS-using software on that machine trusts certificates signed by the internal CA.

## Hands-on Examples

### Example 1: Build a Two-Tier Private CA

This example walks through creating a production-style private CA with a root CA and an intermediate CA. You will set up the directory structure, write OpenSSL configuration files, and sign the intermediate CA with the root. These are the foundational steps that all other private-CA examples depend on.

**1. Create the directory structure for the root CA.**

```bash
mkdir -p ~/pki/rootCA/{certs,crl,newcerts,private}
cd ~/pki/rootCA
chmod 700 private
touch index.txt
echo 1000 > serial
```

**2. Create the root CA OpenSSL configuration file.**

```bash
cat > ~/pki/rootCA/openssl.cnf << 'EOF'
[ ca ]
default_ca = CA_default

[ CA_default ]
dir               = /root/pki/rootCA
certs             = $dir/certs
crl_dir           = $dir/crl
new_certs_dir     = $dir/newcerts
database          = $dir/index.txt
serial            = $dir/serial
RANDFILE          = $dir/private/.rand

private_key       = $dir/private/rootCA.key
certificate       = $dir/certs/rootCA.crt

default_days      = 3650
default_md        = sha256
preserve          = no
policy            = policy_strict

[ policy_strict ]
countryName             = match
stateOrProvinceName     = match
organizationName        = match
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[ req ]
default_bits        = 4096
distinguished_name  = req_distinguished_name
string_mask         = utf8only
default_md          = sha256
x509_extensions     = v3_ca

[ req_distinguished_name ]
countryName                     = Country Name (2 letter code)
stateOrProvinceName             = State or Province Name
localityName                    = Locality Name
organizationName                = Organization Name
organizationalUnitName          = Organizational Unit Name
commonName                      = Common Name
emailAddress                    = Email Address

[ v3_ca ]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints       = critical, CA:true
keyUsage               = critical, digitalSignature, cRLSign, keyCertSign

[ v3_intermediate_ca ]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints       = critical, CA:true, pathlen:0
keyUsage               = critical, digitalSignature, cRLSign, keyCertSign
EOF
```

Note: if you are running as a non-root user, replace `/root/pki/rootCA` with the full path to your actual home directory, e.g. `/home/youruser/pki/rootCA`.

**3. Generate the root CA private key and self-signed certificate.**

```bash
cd ~/pki/rootCA

# Generate a 4096-bit RSA key (kept offline after this step in real deployments)
openssl genrsa -aes256 -out private/rootCA.key 4096
# You will be prompted for a passphrase — choose a strong one and save it securely

# Generate the self-signed root CA certificate (valid 10 years)
openssl req -config openssl.cnf \
  -key private/rootCA.key \
  -new -x509 \
  -days 3650 \
  -sha256 \
  -extensions v3_ca \
  -out certs/rootCA.crt
# You will be prompted for the passphrase and the certificate subject fields
# Example inputs:
#   Country Name: US
#   State: California
#   Organization: Acme Corp
#   Common Name: Acme Root CA
```

Expected output: `certs/rootCA.crt` is created. Verify it:

```bash
openssl x509 -in certs/rootCA.crt -text -noout | grep -E "Subject:|Issuer:|Not After"
# Subject and Issuer should be identical (self-signed)
# Not After should be ~10 years in the future
```

**4. Set up the intermediate CA directory structure.**

```bash
mkdir -p ~/pki/intermediateCA/{certs,crl,csr,newcerts,private}
cd ~/pki/intermediateCA
chmod 700 private
touch index.txt
echo 1000 > serial
echo 1000 > crlnumber
```

**5. Create the intermediate CA OpenSSL configuration file.**

```bash
cat > ~/pki/intermediateCA/openssl.cnf << 'EOF'
[ ca ]
default_ca = CA_default

[ CA_default ]
dir               = /root/pki/intermediateCA
certs             = $dir/certs
crl_dir           = $dir/crl
new_certs_dir     = $dir/newcerts
database          = $dir/index.txt
serial            = $dir/serial
RANDFILE          = $dir/private/.rand

private_key       = $dir/private/intermediateCA.key
certificate       = $dir/certs/intermediateCA.crt

default_days      = 375
default_md        = sha256
preserve          = no
policy            = policy_loose

[ policy_loose ]
countryName             = optional
stateOrProvinceName     = optional
localityName            = optional
organizationName        = optional
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[ req ]
default_bits        = 4096
distinguished_name  = req_distinguished_name
string_mask         = utf8only
default_md          = sha256

[ req_distinguished_name ]
countryName                     = Country Name (2 letter code)
stateOrProvinceName             = State or Province Name
localityName                    = Locality Name
organizationName                = Organization Name
organizationalUnitName          = Organizational Unit Name
commonName                      = Common Name
emailAddress                    = Email Address

[ server_cert ]
basicConstraints       = CA:FALSE
nsCertType             = server
nsComment              = "OpenSSL Generated Server Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth

[ client_cert ]
basicConstraints       = CA:FALSE
nsCertType             = client, email
nsComment              = "OpenSSL Generated Client Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
keyUsage               = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage       = clientAuth, emailProtection
EOF
```

Again, replace `/root/pki/intermediateCA` with your actual path if not running as root.

**6. Generate the intermediate CA key and a Certificate Signing Request (CSR).**

```bash
cd ~/pki/intermediateCA

openssl genrsa -aes256 -out private/intermediateCA.key 4096

openssl req -config openssl.cnf -new -sha256 \
  -key private/intermediateCA.key \
  -out csr/intermediateCA.csr
# Example CN: Acme Intermediate CA
```

**7. Sign the intermediate CA CSR with the root CA.**

```bash
cd ~/pki/rootCA

openssl ca -config openssl.cnf \
  -extensions v3_intermediate_ca \
  -days 1825 \
  -notext \
  -md sha256 \
  -in ../intermediateCA/csr/intermediateCA.csr \
  -out ../intermediateCA/certs/intermediateCA.crt
# Type 'y' twice to confirm signing
```

**8. Create the certificate chain file.**

```bash
cat ~/pki/intermediateCA/certs/intermediateCA.crt \
    ~/pki/rootCA/certs/rootCA.crt \
    > ~/pki/intermediateCA/certs/ca-chain.crt
```

**9. Verify the chain.**

```bash
openssl verify -CAfile ~/pki/rootCA/certs/rootCA.crt \
  ~/pki/intermediateCA/certs/intermediateCA.crt
# Expected: /root/pki/intermediateCA/certs/intermediateCA.crt: OK
```

---

### Example 2: Issue and Install a Server Certificate for an AI API Endpoint

With the CA from Example 1 in place, this example issues a server certificate for an internal AI API reachable at `ai-api.internal` and IP `10.0.1.50`, then configures Nginx to use it.

**1. Create a configuration file for the server certificate request.**

```bash
cat > ~/pki/server-ai-api.cnf << 'EOF'
[ req ]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
req_extensions     = req_ext

[ dn ]
C  = US
ST = California
O  = Acme Corp
CN = ai-api.internal

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ai-api.internal
DNS.2 = ai-api
IP.1  = 10.0.1.50
IP.2  = 127.0.0.1
EOF
```

**2. Generate the server private key and CSR.**

```bash
openssl genrsa -out ~/pki/ai-api.internal.key 2048

openssl req -new -sha256 \
  -key ~/pki/ai-api.internal.key \
  -config ~/pki/server-ai-api.cnf \
  -out ~/pki/ai-api.internal.csr
```

**3. Sign the CSR with the intermediate CA.**

```bash
cd ~/pki/intermediateCA

openssl ca -config openssl.cnf \
  -extensions server_cert \
  -days 375 \
  -notext \
  -md sha256 \
  -in ~/pki/ai-api.internal.csr \
  -out ~/pki/ai-api.internal.crt
```

Note: OpenSSL's `ca` command enforces the extensions defined in the CA config (`server_cert`), not those in the CSR. The SAN from the CSR is not automatically copied. To copy SANs from the CSR, add `copy_extensions = copy` to the `[ CA_default ]` section of the intermediate CA's `openssl.cnf`. Without this, you must define the SANs in a separate extension file passed with `-extfile`.

For a production setup, add `copy_extensions = copy` to the intermediate CA config, then re-run the signing command. Alternatively, provide an explicit extension file:

```bash
cat > /tmp/san_ext.cnf << 'EOF'
subjectAltName = DNS:ai-api.internal, DNS:ai-api, IP:10.0.1.50, IP:127.0.0.1
EOF

openssl ca -config openssl.cnf \
  -extensions server_cert \
  -extfile /tmp/san_ext.cnf \
  -days 375 \
  -notext \
  -md sha256 \
  -in ~/pki/ai-api.internal.csr \
  -out ~/pki/ai-api.internal.crt
```

**4. Create the bundle file (server cert + intermediate CA cert) for Nginx.**

```bash
cat ~/pki/ai-api.internal.crt \
    ~/pki/intermediateCA/certs/intermediateCA.crt \
    > ~/pki/ai-api.internal-bundle.crt
```

**5. Install the certificate files and configure Nginx.**

```bash
sudo cp ~/pki/ai-api.internal-bundle.crt /etc/ssl/private/
sudo cp ~/pki/ai-api.internal.key /etc/ssl/private/
sudo chmod 600 /etc/ssl/private/ai-api.internal.key
sudo chown root:root /etc/ssl/private/ai-api.internal.key
```

Create an Nginx server block:

```bash
sudo tee /etc/nginx/sites-available/ai-api.internal << 'EOF'
server {
    listen 443 ssl;
    server_name ai-api.internal;

    ssl_certificate     /etc/ssl/private/ai-api.internal-bundle.crt;
    ssl_certificate_key /etc/ssl/private/ai-api.internal.key;

    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name ai-api.internal;
    return 301 https://$host$request_uri;
}
EOF

sudo ln -s /etc/nginx/sites-available/ai-api.internal /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Expected output from `nginx -t`:

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**6. Verify with openssl s_client (after adding the root CA to the trust store).**

```bash
# First, add the root CA to the system trust store (Ubuntu/Debian)
sudo cp ~/pki/rootCA/certs/rootCA.crt /usr/local/share/ca-certificates/acme-rootCA.crt
sudo update-ca-certificates

# Test the connection
openssl s_client -connect ai-api.internal:443 -brief
# Expected last line: CONNECTION ESTABLISHED
# Protocol version: TLSv1.3 (or TLSv1.2)
# Verify return code: 0 (ok)

# Also test with curl
curl -v https://ai-api.internal/
```

---

### Example 3: Obtain a Let's Encrypt Certificate with Certbot and Automate Renewal

This example provisions a certificate for a publicly reachable server at `chat.example.com` using Certbot's Nginx plugin. Replace `chat.example.com` with your actual domain, and ensure DNS is pointed at your server before starting.

**1. Install Certbot.**

```bash
# Ubuntu / Debian (snapd method — recommended by Let's Encrypt)
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Verify installation
certbot --version
```

**2. Obtain the certificate using the Nginx plugin.**

The Nginx plugin automatically modifies your Nginx configuration to complete the HTTP-01 challenge (Let's Encrypt makes an HTTP request to `http://chat.example.com/.well-known/acme-challenge/TOKEN` to verify you control the domain), then updates the configuration to use the new certificate.

```bash
sudo certbot --nginx -d chat.example.com
# Follow the interactive prompts:
# - Enter your email for expiry notifications
# - Agree to the Terms of Service
# - Choose whether to redirect HTTP to HTTPS (recommended: yes)
```

Expected output (abbreviated):

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/chat.example.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/chat.example.com/privkey.pem
This certificate expires on 2026-07-09.
```

**3. Verify Certbot's systemd timer is active.**

Certbot's snap installation registers a systemd timer that runs `certbot renew` twice daily:

```bash
sudo systemctl status snap.certbot.renew.timer
# Expected: active (waiting)

# List all timers and their next trigger time
systemctl list-timers | grep certbot
```

**4. Perform a dry-run renewal test.**

```bash
sudo certbot renew --dry-run
# Expected: Congratulations, all simulated renewals succeeded
```

**5. Add a deploy hook to reload Nginx after renewal.**

Certbot runs scripts in `/etc/letsencrypt/renewal-hooks/deploy/` after a successful renewal. Create one to reload Nginx:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << 'EOF'
#!/bin/bash
systemctl reload nginx
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

**6. If you prefer cron over the systemd timer**, add a cron entry for the root user:

```bash
sudo crontab -e
# Add this line:
0 3,15 * * * /usr/bin/certbot renew --quiet --deploy-hook "systemctl reload nginx"
# This runs at 03:00 and 15:00 daily; --quiet suppresses output unless an error occurs
```

---

### Example 4: Debug a Certificate Error with openssl s_client

A developer reports that `curl https://ai-api.internal/` fails with `SSL certificate problem: unable to get local issuer certificate`. This example demonstrates a systematic debugging workflow.

**1. Connect with s_client and inspect the output.**

```bash
openssl s_client -connect ai-api.internal:443 -showcerts 2>&1 | head -60
```

Look at the certificate chain section. If it shows only one certificate (depth 0, the server cert) with no intermediate, the server is not sending the intermediate CA certificate. This is the most common cause of `unable to get local issuer certificate`.

**2. Confirm the problem: the server is only sending the leaf certificate.**

```bash
openssl s_client -connect ai-api.internal:443 2>&1 | grep -E "depth|verify"
# Problem output:
# depth=0 CN = ai-api.internal
# verify error:num=20:unable to get local issuer certificate
# Verify return code: 20 (unable to get local issuer certificate)
```

**3. Fix: rebuild the bundle file with the intermediate CA included.**

```bash
cat ~/pki/ai-api.internal.crt \
    ~/pki/intermediateCA/certs/intermediateCA.crt \
    > ~/pki/ai-api.internal-bundle.crt

sudo cp ~/pki/ai-api.internal-bundle.crt /etc/ssl/private/
sudo systemctl reload nginx
```

**4. Verify the fix.**

```bash
openssl s_client -connect ai-api.internal:443 2>&1 | grep -E "depth|verify"
# Fixed output:
# depth=2 CN = Acme Root CA
# depth=1 CN = Acme Intermediate CA
# depth=0 CN = ai-api.internal
# Verify return code: 0 (ok)
```

**5. Check certificate expiry from the command line.**

```bash
# Check expiry of a certificate file
openssl x509 -in /etc/ssl/private/ai-api.internal-bundle.crt -noout -dates
# Output:
# notBefore=Jan  1 00:00:00 2025 GMT
# notAfter=Jan 11 00:00:00 2026 GMT

# Check expiry of a live server's certificate
echo | openssl s_client -connect ai-api.internal:443 2>/dev/null \
  | openssl x509 -noout -dates
```

**6. Check whether a certificate matches its private key.**

```bash
# These commands output the modulus of the key and cert — they must match
openssl rsa  -in ai-api.internal.key  -noout -modulus | openssl md5
openssl x509 -in ai-api.internal.crt  -noout -modulus | openssl md5
# If both MD5 hashes are identical, the key and certificate are a matched pair
```

## Common Pitfalls

### 1. Missing Subject Alternative Names

**Description:** Generating a certificate with only a Common Name (CN) and no SAN extension, then finding that browsers and curl reject it.

**Why it happens:** Older tutorials and legacy openssl invocations that predate the SAN-required-for-hostname-validation era (enforced since Chrome 58 in 2017 and now universal) do not include `-ext` or configuration-file SAN sections.

**Incorrect pattern:**

```bash
openssl req -newkey rsa:2048 -keyout server.key -out server.csr \
  -subj "/CN=api.internal"
# No SAN — this CSR will produce a certificate that modern clients reject
```

**Correct pattern:**

```bash
openssl req -newkey rsa:2048 -keyout server.key -out server.csr \
  -subj "/CN=api.internal" \
  -addext "subjectAltName=DNS:api.internal,DNS:api,IP:10.0.1.50"
```

Or use a configuration file with an `[alt_names]` section as shown in Example 2.

---

### 2. Sending Only the Leaf Certificate — No Intermediate

**Description:** The server is configured with `ssl_certificate` pointing at only the server certificate file, not a bundle that includes the intermediate CA cert. Clients that do not have the intermediate cached fail to build the chain.

**Why it happens:** The certificate signing step produces the server cert and the CA certs as separate files. It is easy to copy only the server cert to the server and forget to bundle it with the intermediate.

**Incorrect Nginx config:**

```nginx
ssl_certificate /etc/ssl/private/server.crt;
# Only the leaf certificate — no intermediate
```

**Correct Nginx config:**

```nginx
ssl_certificate /etc/ssl/private/server-bundle.crt;
# This file contains: server.crt concatenated with intermediateCA.crt
```

---

### 3. Wrong File Permissions on Private Keys

**Description:** Nginx or Apache fails to start with `Permission denied` when trying to read the private key.

**Why it happens:** The key file was copied with world-readable permissions (`644`), then the web server process (running as `www-data` or `nginx`) cannot read it because the directory permissions or owner is wrong — or conversely, the key is readable by everyone, which is a security risk.

**Incorrect pattern:**

```bash
cp server.key /etc/ssl/private/server.key
# Default umask may create it as 644 — world-readable
```

**Correct pattern:**

```bash
sudo cp server.key /etc/ssl/private/server.key
sudo chmod 640 /etc/ssl/private/server.key
sudo chown root:ssl-cert /etc/ssl/private/server.key
# On Debian/Ubuntu, www-data is in the ssl-cert group
# On RHEL/Rocky, use: chown root:nginx
```

---

### 4. Forgetting to Reload the Web Server After Certificate Update

**Description:** A new certificate is installed on disk but the web server continues serving the old (expired or incorrect) certificate.

**Why it happens:** Nginx and Apache load certificates into memory at startup. They do not watch certificate files for changes. Updating the file on disk has no effect until the server process re-reads its configuration.

**Incorrect assumption:** Copying a new certificate file to `/etc/ssl/private/` automatically takes effect.

**Correct pattern:**

```bash
sudo nginx -t && sudo systemctl reload nginx
# Or for Apache:
sudo apachectl configtest && sudo systemctl reload apache2
# 'reload' sends SIGHUP — it re-reads configuration without dropping connections
# Use 'restart' only if 'reload' is insufficient
```

---

### 5. Using the Archived Path Instead of the Certbot Symlink

**Description:** A Certbot-managed Nginx configuration references `/etc/letsencrypt/archive/example.com/cert1.pem` instead of `/etc/letsencrypt/live/example.com/cert.pem`. After the first automatic renewal, Nginx continues serving the original expired certificate because the hardcoded archive path points to `cert1.pem` while the renewed certificate is `cert2.pem`.

**Why it happens:** The `live/` directory contains symlinks that Certbot updates on each renewal. The `archive/` directory contains the actual numbered files. Certbot's own documentation and plugins always use the `live/` symlinks.

**Incorrect pattern:**

```nginx
ssl_certificate /etc/letsencrypt/archive/example.com/cert1.pem;
```

**Correct pattern:**

```nginx
ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;
```

---

### 6. Creating a Self-Signed Certificate for Production

**Description:** Using a self-signed certificate on an internet-facing service. Every user's browser shows a security warning, API clients fail, and automated monitoring tools report errors.

**Why it happens:** Self-signed certificates are quick to generate and work fine for dev. The step of "replace with a real cert before going live" is skipped or forgotten.

**Incorrect pattern (in production):**

```bash
openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt -days 365 -nodes
# Self-signed — no chain, not trusted by any client by default
```

**Correct pattern for production:** Use Let's Encrypt via Certbot for public-facing services, or issue a certificate from your private CA and install that CA's root cert in all clients' trust stores for internal services.

---

### 7. Mismatched Key and Certificate

**Description:** Nginx fails to start with `SSL_CTX_use_PrivateKey_file ... key values mismatch`.

**Why it happens:** The certificate file was replaced (e.g., after a renewal) but the key file was not updated to match the new certificate's key, or a mix-up occurred when copying files.

**Incorrect pattern:** Deploying `server.crt` from one signing operation and `server.key` from a different one.

**Correct diagnostic:**

```bash
openssl rsa  -in server.key -noout -modulus | openssl md5
openssl x509 -in server.crt -noout -modulus | openssl md5
# If the two MD5 values differ, the key and certificate do not match
```

**Correct pattern:** Always generate the key and CSR together in one step, and keep them as a matched pair.

---

### 8. Ignoring the pathlen Constraint on Intermediate CAs

**Description:** Intermediate CA cannot sign sub-intermediate CAs even though `CA:TRUE` is set.

**Why it happens:** The `pathlen:0` constraint in `basicConstraints` means "this CA may sign end-entity certificates but may not sign CAs that sign other certificates." If you later want to create a sub-intermediate CA, this constraint prevents it.

**Incorrect assumption:** Setting `CA:TRUE` is all that is required for a CA to sign other CAs.

**Correct pattern:** Design the `pathlen` value intentionally. `pathlen:0` is correct for a two-tier hierarchy where the intermediate only signs leaf certificates. For three tiers, set `pathlen:1` on the intermediate. For an intermediate that can sign an unlimited depth of sub-CAs, omit the `pathlen` constraint entirely.

## Summary

- PKI solves the authentication problem in TLS by establishing a chain of trust from a CA that clients already trust down to the server certificate presented during the handshake; understanding this chain is the foundation for diagnosing every certificate error you will encounter.
- A two-tier private CA (root CA plus intermediate CA) is the correct structure for securing internal AI infrastructure, internal APIs, and development environments where Let's Encrypt is not available; the root CA key is kept offline after creating the intermediate, and all day-to-day signing is done by the intermediate.
- Every server certificate must include Subject Alternative Name (SAN) extensions covering all DNS names and IP addresses the certificate should be valid for; the Common Name field is not used for hostname validation by any modern TLS client.
- Let's Encrypt and Certbot provide a fully automated path to browser-trusted certificates for public-facing services; the systemd timer installed by the snap package runs renewal automatically twice daily, and deploy hooks ensure the web server reloads after each successful renewal.
- `openssl s_client` is the primary diagnostic tool for TLS problems; checking the verify return code, the depth of the chain, and the certificate dates covers the majority of certificate errors encountered in production.

## Further Reading

- [OpenSSL Cookbook by Ivan Ristić (online edition)](https://www.feistyduck.com/library/openssl-cookbook/online/) — a free, thorough practical guide to OpenSSL covering certificate creation, TLS configuration, and diagnostics; the most useful single reference for the command-line work in this module.
- [Let's Encrypt Documentation — Getting Started](https://letsencrypt.org/getting-started/) — the official starting point for Let's Encrypt, explaining how the ACME protocol works and linking to Certbot and other client options; essential reading before choosing a challenge type.
- [Certbot Documentation](https://certbot.eff.org/docs/) — comprehensive reference for Certbot commands, plugins, configuration, hooks, and troubleshooting; covers the Nginx and Apache plugins, DNS challenges, and renewal configuration in detail.
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/) — a web tool that generates secure Nginx, Apache, and HAProxy TLS configurations for a chosen compatibility level (Modern, Intermediate, Old); saves time and prevents weak cipher and protocol configurations.
- [RFC 5280 — Internet X.509 PKI Certificate and CRL Profile](https://www.rfc-editor.org/rfc/rfc5280) — the definitive specification for X.509v3 certificates; useful when you need to understand exactly what a certificate field means or why a validation step is failing.
- [testssl.sh](https://testssl.sh/) — an open-source shell script that performs a comprehensive TLS configuration audit against any server, checking protocol versions, cipher suites, certificate chain, HSTS, HPKP, and known vulnerabilities; run this against any server before it goes to production.
- [Cloudflare Learning Center: What is mTLS?](https://www.cloudflare.com/learning/access-management/what-is-mutual-tls/) — a well-illustrated conceptual introduction to mutual TLS, covering the handshake flow, use cases in zero-trust architectures, and how mTLS compares to API key and JWT authentication; useful for explaining mTLS to stakeholders.
