#!/usr/bin/env bash
# ==============================================================================
# Smart Traffic AI - Local Server Launch Controller
# Starts the backend server locally on port 8090 with environment pre-flight
# Usage:
#   ./run_server.sh          # Starts server on port 8090
#   ./run_server.sh --port 8095
#   ./run_server.sh --force  # Force restart if already running
# ==============================================================================

set -e

PORT="8090"
HOST="0.0.0.0"
FORCE=false
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--port)
      PORT="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    -f|--force)
      FORCE=true
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================================="
echo "  🚦 SMART TRAFFIC AI - LOCAL SERVER LAUNCHER                             "
echo "  Arterial Flow, YOLOv11 Computer Vision & Spatio-Temporal Prediction     "
echo "=========================================================================="

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not found in PATH. Please install Python 3.10+."
    exit 1
fi

# Check if port is already running
if lsof -i :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    EXISTING_PID=$(lsof -i :"$PORT" -sTCP:LISTEN -t | head -n 1)
    if [ "$FORCE" = true ]; then
        echo "⚠️  Port $PORT is currently in use (PID $EXISTING_PID). Terminating old instance..."
        kill -9 "$EXISTING_PID" 2>/dev/null || true
        sleep 1
    else
        echo "✅ Server is ALREADY RUNNING locally on port $PORT (PID: $EXISTING_PID)."
        echo "   * Operational Portal: http://localhost:$PORT/portal"
        echo "   * Sign-In Gateway:    http://localhost:$PORT/login"
        echo "   * Health Status:      http://localhost:$PORT/api/health"
        echo "   (To force restart, run: ./run_server.sh --force)"
        echo "=========================================================================="
        exit 0
    fi
fi

echo "  -> Host: $HOST"
echo "  -> Port: $PORT"
echo "  -> Dedicated Local URLs:"
echo "     * Operational Portal: http://localhost:$PORT/portal"
echo "     * Sign-In Gateway:    http://localhost:$PORT/login"
echo "     * Health Endpoint:    http://localhost:$PORT/api/health"
echo "--------------------------------------------------------------------------"
echo "  Starting server in foreground (press Ctrl+C to terminate)..."
echo "=========================================================================="

exec python3 run_system.py --host "$HOST" --port "$PORT" "${EXTRA_ARGS[@]}"
