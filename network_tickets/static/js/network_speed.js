(() => {
  const testButton = document.getElementById("network-speed-refresh");
  const listContainer = document.getElementById("network-speed-list");
  const lastUpdated = document.getElementById("network-speed-updated");
  const sitesDataElement = document.getElementById("network-speed-sites-data");
  const thresholdsElement = document.getElementById("network-speed-thresholds-data");
  const timeoutElement = document.getElementById("network-speed-timeout-data");

  if (!testButton || !listContainer) {
    return;
  }

  const sites = sitesDataElement ? JSON.parse(sitesDataElement.textContent) : [];
  const thresholds = thresholdsElement ? JSON.parse(thresholdsElement.textContent) : {};
  const timeoutSeconds = timeoutElement ? JSON.parse(timeoutElement.textContent) : 5;
  const timeoutMs = (timeoutSeconds || 5) * 1000;

  const statusLabels = {
    good: "Good",
    medium: "Medium",
    poor: "Poor",
    error: "Error",
  };

  function classifyLatency(latency) {
    if (latency === null || latency === undefined) {
      return "error";
    }
    const goodThreshold = thresholds.good ?? 300;
    const warningThreshold = thresholds.warning ?? 800;
    if (latency <= goodThreshold) {
      return "good";
    }
    if (latency <= warningThreshold) {
      return "medium";
    }
    return "poor";
  }

  function statusToColor(status) {
    switch (status) {
      case "good":
        return "green";
      case "medium":
        return "yellow";
      default:
        return "red";
    }
  }

  function setLoadingState(isLoading) {
    testButton.disabled = isLoading;
    testButton.innerHTML = isLoading
      ? '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Testing...'
      : '<i class="fas fa-sync-alt me-2"></i>Test Now';
  }

  function createStatusBadge(colorClass, text) {
    const badge = document.createElement("span");
    badge.className = `badge px-3 py-2 text-uppercase fw-semibold bg-${colorClass}`;
    badge.textContent = text;
    return badge;
  }

  function updateList(items) {
    listContainer.innerHTML = "";
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "col-lg-6 col-md-12 mb-4";
      card.innerHTML = `
        <div class="card h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <div>
                <h5 class="mb-1"><a href="${item.url}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">${item.name}</a></h5>
              </div>
              <div class="status-badge"></div>
            </div>
            <div>
              ${
                item.latency_ms !== null
                  ? `<span class="fs-4 fw-bold">${item.latency_ms} ms</span>`
                  : '<span class="text-danger fw-semibold">Failed</span>'
              }
              ${
                item.error
                  ? `<div class="text-muted small mt-2">Error: ${item.error}</div>`
                  : ""
              }
            </div>
          </div>
        </div>
      `;

      const badge = createStatusBadge(
        item.color === "green"
          ? "success"
          : item.color === "yellow"
          ? "warning"
          : "danger",
        statusLabels[item.status] || "Unknown"
      );
      card.querySelector(".status-badge").appendChild(badge);
      listContainer.appendChild(card);
    });
  }

  async function testSite(site) {
    const controller = new AbortController();
    const start = performance.now();
    let latency = null;
    let error = null;

    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      await fetch(site.url, {
        method: "GET",
        mode: "no-cors",
        cache: "no-store",
        signal: controller.signal,
      });
      latency = Math.round((performance.now() - start) * 100) / 100;
    } catch (err) {
      error = err.name === "AbortError" ? "Request timed out" : err.message;
    } finally {
      clearTimeout(timeoutId);
    }

    const status = classifyLatency(latency);
    return {
      name: site.name || site.url,
      url: site.url,
      latency_ms: latency,
      status,
      color: statusToColor(status),
      error,
    };
  }

  async function runSpeedTest() {
    if (!sites.length) {
      return;
    }
    setLoadingState(true);
    try {
      const results = await Promise.all(sites.map((site) => testSite(site)));
      updateList(results);
      if (lastUpdated) {
        lastUpdated.textContent = new Date().toLocaleString();
      }
    } catch (err) {
      console.error("Speed test failed", err);
      listContainer.innerHTML =
        '<div class="alert alert-danger">Unable to run tests in the browser. Please try again.</div>';
    } finally {
      setLoadingState(false);
    }
  }

  testButton.addEventListener("click", runSpeedTest);
})();
