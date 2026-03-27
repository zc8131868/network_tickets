#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# OpenClaw Memory — Cron Job Installer
#
# Installs two cron entries on the host (or inside the Docker container):
#   1. Nightly at 23:30  — daily → weekly distillation + archive cleanup
#   2. Saturday at 23:45 — weekly → permanent distillation
#
# Usage:
#   bash cron_setup.sh              # Install cron jobs
#   bash cron_setup.sh --remove     # Remove cron jobs
#   bash cron_setup.sh --show       # Show current memory cron entries
# ---------------------------------------------------------------------------

set -euo pipefail

# Resolve paths — adjust MEMORY_MODULE to wherever the Python package lives
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MEMORY_MODULE="$(dirname "$SCRIPT_DIR")/memory"
PYTHON="${PYTHON:-python3}"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
LOG_DIR="${WORKSPACE}/memory/logs"
CRON_TAG="# openclaw-memory"

mkdir -p "$LOG_DIR"

NIGHTLY_ENTRY="30 23 * * * cd ${SCRIPT_DIR}/.. && ${PYTHON} -m memory distill-nightly >> ${LOG_DIR}/nightly.log 2>&1 ${CRON_TAG}"
SATURDAY_ENTRY="45 23 * * 6 cd ${SCRIPT_DIR}/.. && ${PYTHON} -m memory distill-saturday >> ${LOG_DIR}/saturday.log 2>&1 ${CRON_TAG}"
CLEANUP_ENTRY="0 4 * * * cd ${SCRIPT_DIR}/.. && ${PYTHON} -m memory cleanup >> ${LOG_DIR}/cleanup.log 2>&1 ${CRON_TAG}"

show_entries() {
    echo "Current openclaw-memory cron entries:"
    crontab -l 2>/dev/null | grep "$CRON_TAG" || echo "  (none)"
}

install_entries() {
    # Remove old entries first, then add fresh ones
    local existing
    existing=$(crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true)

    echo "$existing" | { cat; echo "$NIGHTLY_ENTRY"; echo "$SATURDAY_ENTRY"; echo "$CLEANUP_ENTRY"; } | crontab -

    echo "Installed cron jobs:"
    echo "  Nightly (23:30 daily):   daily → weekly + cleanup"
    echo "  Saturday (23:45 Sat):    weekly → permanent"
    echo "  Cleanup  (04:00 daily):  archive moves + deletions"
    echo ""
    echo "Logs: ${LOG_DIR}/"
}

remove_entries() {
    local existing
    existing=$(crontab -l 2>/dev/null | grep -v "$CRON_TAG" || true)
    echo "$existing" | crontab -
    echo "Removed all openclaw-memory cron entries."
}

case "${1:-}" in
    --remove) remove_entries ;;
    --show)   show_entries ;;
    *)        install_entries ;;
esac
