#!/bin/bash
cd "$(dirname "$0")"

echo "========================================================"
echo "  BMS Vision Inspection - Pure Edge Impulse (.EIM) AOI"
echo "  Target: Arduino UNO Q (QRB2210 Linux SBC) / Linux ARM64"
echo "  Engine: .EIM Only (Zero ONNX Runtime)"
echo "========================================================"

# Make all .eim executables runnable
chmod +x models/*.eim 2>/dev/null

python3 bms_eim_vision_inspection.py --source 0 --serial-port bridge --conf 0.20
