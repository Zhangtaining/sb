#!/usr/bin/env bash
# Stop all locally running Smart Gym services.

echo "Stopping Smart Gym services..."

pkill -f "ingestion.main"  2>/dev/null && echo "  ✓ ingestion stopped" || echo "  - ingestion not running"
pkill -f "perception.main" 2>/dev/null && echo "  ✓ perception stopped" || echo "  - perception not running"
pkill -f "exercise.main"   2>/dev/null && echo "  ✓ exercise stopped"   || echo "  - exercise not running"
pkill -f "guidance.main"   2>/dev/null && echo "  ✓ guidance stopped"   || echo "  - guidance not running"
pkill -f "worker.app"      2>/dev/null && echo "  ✓ worker stopped"     || echo "  - worker not running"
pkill -f "uvicorn api.main" 2>/dev/null && echo "  ✓ api stopped"       || echo "  - api not running"

rm -f /tmp/gym-pids.txt
echo "Done."
