#!/usr/bin/env bash
set -euo pipefail

: "${ARDUPILOT_DIR:?Defina ARDUPILOT_DIR para um checkout existente do ArduPilot no WSL.}"
if [[ ! -d "$ARDUPILOT_DIR/ArduCopter" ]]; then
  echo "ArduCopter não encontrado em ARDUPILOT_DIR." >&2
  exit 1
fi

cd "$ARDUPILOT_DIR/ArduCopter"
../Tools/autotest/sim_vehicle.py \
  --vehicle ArduCopter \
  --console \
  --map \
  --out=udp:127.0.0.1:14550
