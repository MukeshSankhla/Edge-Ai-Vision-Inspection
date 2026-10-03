@echo off
cd /d "%~dp0"
echo ========================================================
echo   BMS Vision Inspection - Pure Edge Impulse (.EIM) AOI
echo   Engine: .EIM Only (Zero ONNX Runtime)
echo ========================================================
python bms_eim_vision_inspection.py --source 0 --conf 0.20
pause
