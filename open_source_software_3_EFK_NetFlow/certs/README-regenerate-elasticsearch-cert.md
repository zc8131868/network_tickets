# Regenerate Elasticsearch server cert for IP access (e.g. https://172.19.11.14:9200)

The default cert only has `DNS:elasticsearch.qytopensource.com`. To allow **https://172.19.11.14:9200** (and localhost) without TLS hostname errors, regenerate the server cert with the SAN config that includes the IP.

## Prerequisites

- You need the **CA private key** that was used to sign the original cert (e.g. `ca-key.pem` or `ca.key`). If you don’t have it, use the [hosts-file workaround](#option-b-use-etchosts) instead.

## Steps (run from this `certs/` directory)

1. **Back up the current cert** (optional):
   ```bash
   cp server-elasticsearch.pem server-elasticsearch.pem.bak
   ```

2. **Generate a CSR** from the existing server key, with SAN (DNS + IP):
   ```bash
   openssl req -new -key server-key-elasticsearch.pem -out server-elasticsearch.csr \
     -config elasticsearch-san.cnf -extensions v3_req
   ```

3. **Sign the CSR** with your CA (replace `path/to/ca-key.pem` with your CA private key path):
   ```bash
   openssl x509 -req -in server-elasticsearch.csr \
     -CA ca.cer -CAkey path/to/ca-key.pem -CAcreateserial \
     -out server-elasticsearch.pem -days 825 \
     -extfile elasticsearch-san.cnf -extensions v3_req
   ```

4. **Restart Elasticsearch** so it loads the new cert:
   ```bash
   cd ..
   docker compose -f docker-compose-tls.yaml restart elasticsearch
   ```

5. **Verify** the new cert includes the IP:
   ```bash
   openssl x509 -in server-elasticsearch.pem -noout -text | grep -A2 "Subject Alternative Name"
   ```
   You should see `DNS:elasticsearch.qytopensource.com`, `IP Address:172.19.11.14`, and `IP Address:127.0.0.1`.

After this, **https://172.19.11.14:9200** will validate without hostname mismatch (clients still need to trust your `ca.cer`).

---

## Option B: Use `/etc/hosts` (no cert change)

If you don’t have the CA key, on each machine that needs to reach Elasticsearch add:

```text
172.19.11.14  elasticsearch.qytopensource.com kibana.qytopensource.com
```

Then open **https://elasticsearch.qytopensource.com:9200** (not the IP). The existing cert will match.
