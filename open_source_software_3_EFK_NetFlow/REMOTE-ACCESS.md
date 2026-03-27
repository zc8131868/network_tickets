# Remote access to Elasticsearch (https://172.19.11.14:9200)

## 1. Allow traffic on the server (172.19.11.14)

Elasticsearch is already bound to `0.0.0.0` and port `9200` is published in Docker. Ensure the host firewall allows inbound TCP 9200 (and 5601 for Kibana if needed).

**firewalld (Rocky/RHEL):**
```bash
sudo firewall-cmd --permanent --add-port=9200/tcp
sudo firewall-cmd --permanent --add-port=5601/tcp   # optional, for Kibana
sudo firewall-cmd --reload
```

**iptables:** Allow INPUT for destination port 9200 (and 5601) as per your policy.

**Network:** Any intermediate firewall or security group must also allow 9200 (and 5601) from the remote clients to 172.19.11.14.

---

## 2. TLS so https://172.19.11.14:9200 validates

The server cert currently has only `DNS:elasticsearch.qytopensource.com`. For the URL **https://172.19.11.14:9200** to work without hostname errors you have two options.

### Option A – Cert includes the IP (recommended for “use the IP in the URL”)

Regenerate the Elasticsearch server cert with `172.19.11.14` in the SAN (script and config are in `certs/`). You need the **CA private key**.

```bash
cd /it_network/open_source_software_3_EFK_NetFlow/certs
./regenerate-elasticsearch-cert.sh /path/to/ca-key.pem
cd ..
docker compose -f docker-compose-tls.yaml restart elasticsearch
```

Then from any remote machine (with firewall open):

- Open **https://172.19.11.14:9200** in a browser or call it with `curl`; the cert will match the IP.
- Remote clients must **trust your CA** (install `certs/ca.cer` as a trusted CA, or use `curl --cacert ca.cer`).

### Option B – Use the hostname from remote (no CA key needed)

On each **remote** machine (Windows, macOS, or Linux) that will access the stack, add a hosts entry so the hostname resolves to 172.19.11.14. Then use **https://elasticsearch.qytopensource.com:9200** (not the IP) in the browser or script.

**Windows**
1. Run Notepad as Administrator (right‑click → Run as administrator).
2. Open: `C:\Windows\System32\drivers\etc\hosts`
3. Add a new line at the end:
   ```
   172.19.11.14  elasticsearch.qytopensource.com kibana.qytopensource.com
   ```
4. Save and close.

**macOS**
1. Open Terminal.
2. Run:
   ```bash
   echo "172.19.11.14  elasticsearch.qytopensource.com kibana.qytopensource.com" | sudo tee -a /etc/hosts
   ```
3. Enter your Mac password when prompted.

**Linux**
- Same as macOS: add that line to `/etc/hosts` (e.g. with the command above, or edit `/etc/hosts` with sudo).

Then use in browser or scripts:

- **https://elasticsearch.qytopensource.com:9200**
- **https://kibana.qytopensource.com:5601** (if Kibana is exposed)

Traffic still goes to 172.19.11.14; the hostname in the URL matches the cert.

---

## 3. Authentication

X-Pack security is enabled. Use the `elastic` user and the password set in the compose file (e.g. `ELASTIC_PASSWORD`) when logging in or calling the API:

```bash
curl -k -u elastic:YOUR_PASSWORD https://172.19.11.14:9200
# Or with hostname (after /etc/hosts):
curl -u elastic:YOUR_PASSWORD https://elasticsearch.qytopensource.com:9200
```

---

## Summary

| Goal | Do this |
|------|--------|
| Open port from internet/VPN to 172.19.11.14 | firewall: allow TCP 9200 (and 5601) on the server and any middleboxes |
| Use **https://172.19.11.14:9200** without cert errors | Option A: regenerate cert with IP in SAN (need CA key) |
| Use hostname from remote, no cert change | Option B: add hosts entry on remote client, use **https://elasticsearch.qytopensource.com:9200** |
