# NGINX and Gunicorn Timeout Configuration

## Problem
When downloading firewall configurations, the operation takes several minutes due to:
- SSH connections to Palo Alto firewall via netmiko
- Multiple routing lookups and interface queries per IP address
- Firewall configuration commands for each row in the Excel file
- Network delays and `global_delay_factor: 2` setting

This causes NGINX to timeout (504 Gateway Timeout) before the operation completes.

## Solution Applied

### 1. NGINX Configuration (`/it_network/network_tickets/nginx/conf.d/nginx.conf`)

Added timeout settings in the proxy location block:
```nginx
# Timeout settings for long-running firewall operations
proxy_connect_timeout       600s;  # Time to establish connection with backend
proxy_send_timeout          600s;  # Time to send request to backend
proxy_read_timeout          600s;  # Time to read response from backend
send_timeout                600s;  # Time to send response to client
```

**Explanation:**
- `proxy_connect_timeout`: How long NGINX waits to connect to Gunicorn (default: 60s → 600s)
- `proxy_send_timeout`: How long NGINX waits to send the request to Gunicorn (default: 60s → 600s)
- `proxy_read_timeout`: How long NGINX waits for response from Gunicorn (default: 60s → 600s) - **Most important for long operations**
- `send_timeout`: How long NGINX waits to send response to client (default: 60s → 600s)

### 2. Gunicorn Configuration (`/etc/systemd/system/network_tickets.service`)

Updated the worker timeout:
```bash
--timeout 600  # Changed from 120 to 600 seconds
```

**Explanation:**
- If a worker doesn't respond within this time, Gunicorn kills and restarts it
- Set to 600s (10 minutes) to match NGINX timeout

## Changes Applied

**Date:** 2025-10-13

**Files Modified:**
1. `/it_network/network_tickets/nginx/conf.d/nginx.conf` - Added proxy timeout settings
2. `/etc/systemd/system/network_tickets.service` - Increased Gunicorn timeout to 600s

**Services Restarted:**
1. `systemctl restart network_tickets.service` - Gunicorn/Uvicorn
2. `docker compose restart` - NGINX container

## Testing

After applying these changes, test with:
1. Upload an Excel file with multiple rows (10-20 rows)
2. Monitor the operation time
3. Verify no timeout errors occur

## Additional Recommendations

### 1. Implement Progress Feedback (Recommended)
For better user experience, consider implementing:
- **WebSocket or Server-Sent Events (SSE)** for real-time progress updates
- **Asynchronous task processing** using Celery + Redis/RabbitMQ
- **Progress bar** showing current row being processed

### 2. Further Timeout Adjustments (If Needed)
If you have very large Excel files (100+ rows), you may need to:
- Increase timeouts further (e.g., 1200s = 20 minutes)
- Implement asynchronous processing instead of synchronous

### 3. Optimize Performance
Consider these optimizations:
- Reduce `global_delay_factor` from 2 to 1 (if firewall can handle it)
- Cache firewall zone lookups for repeated IPs
- Use connection pooling or persistent SSH connections
- Batch configuration commands when possible

### 4. Add Client-Side Timeout Warning
Add a message in the UI:
```html
<p class="text-warning">
  ⚠️ Configuration deployment may take 5-10 minutes depending on the number of rules. 
  Please do not close this page or refresh the browser.
</p>
```

### 5. Add Loading Indicator
Show a loading spinner or progress indicator while processing:
```html
<div id="loading-spinner" style="display:none;">
  <i class="fa fa-spinner fa-spin"></i> 
  Processing firewall configuration, please wait...
</div>
```

## Timeout Values Summary

| Component | Old Timeout | New Timeout | Purpose |
|-----------|-------------|-------------|---------|
| NGINX `proxy_connect_timeout` | 60s (default) | 600s | Connect to backend |
| NGINX `proxy_read_timeout` | 60s (default) | 600s | Read backend response |
| NGINX `proxy_send_timeout` | 60s (default) | 600s | Send to backend |
| NGINX `send_timeout` | 60s (default) | 600s | Send to client |
| Gunicorn `--timeout` | 120s | 600s | Worker timeout |

## Monitoring

To monitor long-running requests:
```bash
# Check NGINX logs
docker exec nginx2025 tail -f /var/log/nginx/access.log

# Check Gunicorn logs
journalctl -u network_tickets.service -f

# Check application logs
tail -f /it_network/network_tickets/logs/netmiko_session.log
```

## Rollback Instructions

If you need to revert these changes:

1. **Revert NGINX configuration:**
   ```bash
   cd /it_network/network_tickets/nginx/conf.d
   # Remove the timeout lines from nginx.conf
   docker compose restart
   ```

2. **Revert Gunicorn timeout:**
   ```bash
   sudo nano /etc/systemd/system/network_tickets.service
   # Change --timeout 600 back to --timeout 120
   sudo systemctl daemon-reload
   sudo systemctl restart network_tickets.service
   ```


