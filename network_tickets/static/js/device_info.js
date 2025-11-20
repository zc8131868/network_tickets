(function() {
  'use strict';
  
  // Wait for DOM to be ready
  function initDeviceInfo() {
    const publicIpElement = document.getElementById("device-public-ip");
    const privateIpElement = document.getElementById("device-private-ip");
    const ispElement = document.getElementById("device-isp");
    const browserElement = document.getElementById("device-browser");

    if (!publicIpElement || !privateIpElement || !ispElement || !browserElement) {
      console.error("Device info elements not found");
      return;
    }

    // Get client IP from server (if available)
    const clientIpElement = document.getElementById("client-ip-data");
    const serverClientIP = clientIpElement ? JSON.parse(clientIpElement.textContent) : null;

    // Helper function to add timeout to fetch
    function fetchWithTimeout(url, options = {}, timeout = 4000) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      
      return fetch(url, {
        ...options,
        signal: controller.signal
      }).finally(() => {
        clearTimeout(timeoutId);
      });
    }

    // Get browser and device information
    function getBrowserInfo() {
      try {
        const ua = navigator.userAgent;
        let browserName = "Unknown";
        let osName = "Unknown";

        // Detect browser
        if (ua.indexOf("Firefox") > -1) {
          browserName = "Firefox";
        } else if (ua.indexOf("Chrome") > -1 && ua.indexOf("Edg") === -1) {
          browserName = "Chrome";
        } else if (ua.indexOf("Safari") > -1 && ua.indexOf("Chrome") === -1) {
          browserName = "Safari";
        } else if (ua.indexOf("Edg") > -1) {
          browserName = "Edge";
        } else if (ua.indexOf("Opera") > -1 || ua.indexOf("OPR") > -1) {
          browserName = "Opera";
        }

        // Detect OS
        if (ua.indexOf("Windows") > -1) {
          osName = "Windows";
        } else if (ua.indexOf("Mac") > -1) {
          osName = "macOS";
        } else if (ua.indexOf("Linux") > -1) {
          osName = "Linux";
        } else if (ua.indexOf("Android") > -1) {
          osName = "Android";
        } else if (ua.indexOf("iOS") > -1 || ua.indexOf("iPhone") > -1 || ua.indexOf("iPad") > -1) {
          osName = "iOS";
        }

        return `${browserName} on ${osName}`;
      } catch (error) {
        console.error("Error getting browser info:", error);
        return "Unknown";
      }
    }

    // Get private IP using WebRTC
    function getPrivateIP() {
      return new Promise((resolve) => {
        try {
          const RTCPeerConnection = window.RTCPeerConnection || 
                                    window.mozRTCPeerConnection || 
                                    window.webkitRTCPeerConnection;

          if (!RTCPeerConnection) {
            resolve("Not supported");
            return;
          }

          let resolved = false;
          const ips = new Set();
          const ipRegex = /([0-9]{1,3}(\.[0-9]{1,3}){3})/g;

          // Helper to check if IP is private
          function isPrivateIP(ip) {
            if (!ip || ip.startsWith("127.") || ip.startsWith("0.0.0.0") || ip.startsWith("169.254.")) {
              return false;
            }
            return ip.startsWith("192.168.") || 
                   ip.startsWith("10.") || 
                   (ip.startsWith("172.") && 
                    parseInt(ip.split(".")[1]) >= 16 && 
                    parseInt(ip.split(".")[1]) <= 31);
          }

          // Helper to extract IPs from candidate string
          function extractIPs(candidate) {
            const matches = candidate.match(ipRegex);
            if (!matches) return [];
            return matches.filter(ip => isPrivateIP(ip));
          }

          const pc = new RTCPeerConnection({
            iceServers: [
              { urls: "stun:stun.l.google.com:19302" },
              { urls: "stun:stun1.l.google.com:19302" },
              { urls: "stun:stun2.l.google.com:19302" }
            ],
            iceCandidatePoolSize: 0
          });

          // Create data channel to trigger candidate gathering
          const dataChannel = pc.createDataChannel("");

          pc.onicecandidate = (event) => {
            if (event.candidate) {
              const candidate = event.candidate.candidate;
              const foundIPs = extractIPs(candidate);
              
              foundIPs.forEach(ip => {
                if (!ips.has(ip)) {
                  ips.add(ip);
                  // Resolve immediately when we find first private IP
                  if (!resolved) {
                    resolved = true;
                    resolve(ip);
                    try {
                      dataChannel.close();
                      pc.close();
                    } catch(e) {}
                    return;
                  }
                }
              });
            } else {
              // No more candidates - gathering complete
              if (!resolved) {
                resolved = true;
                const ipArray = Array.from(ips);
                if (ipArray.length > 0) {
                  resolve(ipArray[0]);
                } else {
                  resolve("Not detected");
                }
                try {
                  dataChannel.close();
                  pc.close();
                } catch(e) {}
              }
            }
          };

          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === "complete" && !resolved) {
              resolved = true;
              const ipArray = Array.from(ips);
              if (ipArray.length > 0) {
                resolve(ipArray[0]);
              } else {
                resolve("Not detected");
              }
              try {
                dataChannel.close();
                pc.close();
              } catch(e) {}
            }
          };

          pc.onerror = (error) => {
            console.error("WebRTC error:", error);
            if (!resolved) {
              resolved = true;
              const ipArray = Array.from(ips);
              resolve(ipArray.length > 0 ? ipArray[0] : "Not detected");
              try {
                dataChannel.close();
                pc.close();
              } catch(e) {}
            }
          };

          // Create offer and set local description
          pc.createOffer({ offerToReceiveAudio: false, offerToReceiveVideo: false })
            .then(offer => {
              return pc.setLocalDescription(offer);
            })
            .then(() => {
              // Also check SDP for IPs
              if (pc.localDescription && pc.localDescription.sdp) {
                const sdpIPs = extractIPs(pc.localDescription.sdp);
                sdpIPs.forEach(ip => {
                  if (!ips.has(ip) && !resolved) {
                    ips.add(ip);
                    resolved = true;
                    resolve(ip);
                    try {
                      dataChannel.close();
                      pc.close();
                    } catch(e) {}
                  }
                });
              }
            })
            .catch((error) => {
              console.error("WebRTC offer error:", error);
              if (!resolved) {
                resolved = true;
                const ipArray = Array.from(ips);
                resolve(ipArray.length > 0 ? ipArray[0] : "Not detected");
                try {
                  dataChannel.close();
                  pc.close();
                } catch(e) {}
              }
            });

          // Timeout after 4 seconds
          setTimeout(() => {
            if (!resolved) {
              resolved = true;
              const ipArray = Array.from(ips);
              resolve(ipArray.length > 0 ? ipArray[0] : "Not detected");
              try {
                dataChannel.close();
                pc.close();
              } catch(e) {}
            }
          }, 4000);
        } catch (error) {
          console.error("Error getting private IP:", error);
          resolve("Not detected");
        }
      });
    }

    // Clean service provider name - remove AS number prefix
    function cleanISPName(isp) {
      if (!isp || isp === "Unknown") {
        return isp;
      }
      
      // Remove AS number prefix (e.g., "AS137872 " or "AS12345 ")
      // Pattern: AS followed by numbers, then space, then company name
      const cleaned = isp.replace(/^AS\d+\s+/i, '').trim();
      
      // If the cleaned string is empty, return original
      return cleaned || isp;
    }

    // Fetch public IP and service provider
    async function fetchPublicIPAndISP() {
      const services = [
        {
          name: "ipapi.co",
          url: "https://ipapi.co/json/",
          parser: (data) => {
            const isp = data.org || data.isp || data.asn || data.company || null;
            return {
              ip: data.ip,
              isp: cleanISPName(isp || "Unknown")
            };
          }
        },
        {
          name: "ip-api.com",
          url: "https://ip-api.com/json/?fields=status,message,query,isp,org,as,asname",
          parser: (data) => {
            if (data.status === "success") {
              const isp = data.isp || data.org || data.asname || null;
              return {
                ip: data.query,
                isp: cleanISPName(isp || "Unknown")
              };
            }
            return null;
          }
        },
        {
          name: "ipinfo.io",
          url: "https://ipinfo.io/json",
          parser: (data) => {
            const isp = data.org || data.isp || data.company || null;
            return {
              ip: data.ip,
              isp: cleanISPName(isp || "Unknown")
            };
          }
        },
        {
          name: "ipify",
          url: "https://api.ipify.org?format=json",
          parser: (data) => ({
            ip: data.ip,
            isp: "Unknown"
          })
        }
      ];

      for (const service of services) {
        try {
          const response = await fetchWithTimeout(service.url, {
            method: "GET",
            headers: {
              "Accept": "application/json",
            },
          }, 4000);

          if (!response.ok) {
            continue;
          }

          const data = await response.json();
          const result = service.parser(data);

          if (result && result.ip) {
            publicIpElement.textContent = result.ip;
            ispElement.textContent = result.isp;
            return; // Success
          }
        } catch (error) {
          console.log(`Service ${service.name} failed:`, error.message);
          // Try next service
          continue;
        }
      }

      // All services failed
      publicIpElement.textContent = "Unable to detect";
      ispElement.textContent = "Unable to detect";
    }

    // Initialize - set browser info immediately
    try {
      browserElement.textContent = getBrowserInfo();
    } catch (error) {
      console.error("Error setting browser info:", error);
      browserElement.textContent = "Unknown";
    }

    // Set private IP - use server-provided IP if available, otherwise try WebRTC
    if (serverClientIP) {
      privateIpElement.textContent = serverClientIP;
    } else {
      // Fallback to WebRTC detection
      getPrivateIP()
        .then(ip => {
          privateIpElement.textContent = ip;
        })
        .catch(error => {
          console.error("Error getting private IP:", error);
          privateIpElement.textContent = "Not detected";
        });
    }

    // Fetch public IP and ISP
    fetchPublicIPAndISP()
      .catch(error => {
        console.error("Error fetching public IP/ISP:", error);
        if (publicIpElement.textContent === "Loading...") {
          publicIpElement.textContent = "Unable to detect";
        }
        if (ispElement.textContent === "Loading...") {
          ispElement.textContent = "Unable to detect";
        }
      });
  }

  // Run when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDeviceInfo);
  } else {
    // DOM is already ready
    initDeviceInfo();
  }
})();
