# Mercury AI Error Fix - October 20, 2025

## Problem Description
When accessing Mercury AI via web and querying "show me the information of the device named M09-EXT-SW01", users received the error:
```
Sorry, I encountered an error. Please try again later.
```

## Root Cause
The ChromaDB database files located at `/it_network/network_tickets/auto_tickets/ai_tools/chromadb.db/` were owned by `root` user, but the Django application (via gunicorn) runs as `www-data` user.

When Mercury AI tried to query the ChromaDB database, it failed with:
```
chromadb.errors.InternalError: error returned from database: (code: 8) attempt to write a readonly database
```

SQLite databases (which ChromaDB uses) require write permission even for read operations because they need to manage locks and temporary files.

## Solution Applied
Changed ownership of the ChromaDB database files to `www-data`:
```bash
sudo chown -R www-data:www-data /it_network/network_tickets/auto_tickets/ai_tools/chromadb.db/
sudo chown www-data:www-data /it_network/network_tickets/auto_tickets/ai_tools/.env
```

Restarted the service:
```bash
sudo systemctl restart network_tickets.service
```

## Verification
Tested the query as `www-data` user:
```bash
cd /it_network/network_tickets
sudo -u www-data bash -c "source .venv/bin/activate && cd auto_tickets/ai_tools && python3 -c 'import asyncio; from chromadb_agent import run_query; result = asyncio.run(run_query(\"show me the information of the device named M09-EXT-SW01\")); print(result)'"
```

Result: Successfully returned device information for M09-EXT-SW01.

## Files Affected
- `/it_network/network_tickets/auto_tickets/ai_tools/chromadb.db/` (directory and all contents)
- `/it_network/network_tickets/auto_tickets/ai_tools/.env`

## Recommendations for Future
1. **When adding new data to ChromaDB**: Always run the `chromadb_insert_delete.py` script as `www-data` user, or ensure ownership is changed after adding data:
   ```bash
   sudo -u www-data python chromadb_insert_delete.py
   # OR after running as root:
   sudo chown -R www-data:www-data /it_network/network_tickets/auto_tickets/ai_tools/chromadb.db/
   ```

2. **Consider adding to deployment scripts**: Add ownership change commands to any deployment or data update scripts.

3. **Monitor logs**: Check gunicorn logs for similar permission issues:
   ```bash
   sudo journalctl -u network_tickets.service -f
   ```

## Status
✅ **RESOLVED** - Mercury AI is now functioning correctly and can respond to device information queries.

---

## Performance Analysis

### Current Performance
- **Average response time**: 7-8 seconds per query
- **Breakdown**:
  - API call to embed question: ~3.5s
  - ChromaDB local search: ~0.4s (fast ✅)
  - API call to generate answer: ~3.7s
  - **Total**: ~7.5s

### Performance Bottlenecks

1. **Network Latency to aihubmix.com**
   - Base latency: ~3.2 seconds
   - Affects both API calls (embedding + generation)
   - **Cannot be optimized** without changing API provider

2. **Context Size (TOP_K=25)**
   - Retrieves 25 chunks (~14.4KB of context)
   - More chunks = better accuracy but slower
   - Tested reducing to 5-15 chunks: faster but loses accuracy
   - **Current setting prioritizes accuracy over speed**

3. **Two Sequential API Calls**
   - Must embed question → search → generate answer
   - Cannot be parallelized due to dependencies

### Why It's Slow
The main reason is the **external API latency**. Mercury AI makes 2 round-trip calls to aihubmix.com:
- First to convert your question to an embedding vector
- Second to generate the answer with AI

Each API call takes ~3-4 seconds due to network distance and API processing time.

### What Could Be Improved (Future Options)

1. **Use a local embedding model** (e.g., sentence-transformers)
   - Eliminate first API call (~3.5s saved)
   - Requires GPU for reasonable performance
   
2. **Cache frequently asked questions**
   - Store common queries and their results
   - Instant response for repeated questions
   
3. **Use a faster/closer API provider**
   - Switch from aihubmix.com to a local or regional provider
   - Could reduce latency by 50-70%
   
4. **Implement streaming responses**
   - Show partial results as they're generated
   - Feels faster even if total time is the same

### Tested Configurations

| TOP_K | Context Size | Speed | Accuracy |
|-------|-------------|-------|----------|
| 5 | 2.9KB | ~6s | ❌ Poor - Often says "I don't know" |
| 10 | 5.8KB | ~6.8s | ❌ Poor - Inconsistent results |
| 15 | 8.6KB | ~7.2s | ⚠️ Mixed - Sometimes works |
| **25** | **14.4KB** | **~7.5s** | **✅ Good - Current default** |

**Recommendation**: Keep `TOP_K=25` for reliability. The 1-2 second saved by reducing it is not worth the accuracy loss.

