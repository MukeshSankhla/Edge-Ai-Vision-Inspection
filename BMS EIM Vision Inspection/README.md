# BMS Vision Inspection — Pure Edge Impulse (.EIM) AOI System

A dedicated, lightweight photo-level Automated Optical Inspection (AOI) package engineered to run **strictly on Edge Impulse (.eim) compiled binaries with zero ONNX Runtime dependencies**.

Optimized specifically for the **Arduino UNO Q (Qualcomm QRB2210 Linux MPU + STM32U585 Zephyr MCU)** and Linux AArch64 / ARM SBCs.

---

## ⚡ Pure .EIM Architecture (No ONNX)

- **Zero ONNX Runtime Dependency**: Completely eliminates `onnxruntime` from dependencies and runtime memory footprint.
- **Hardware Acceleration**: Executes Edge Impulse `.eim` binaries compiled with ARM NEON SIMD acceleration for the QRB2210 Cortex-A53 cores.
- **Fit-Longest Preprocessing**: Preserves full 16:9 aspect ratio and letterboxes into square dimensions with black padding (`pad=0`), ensuring 100% field-of-view retention for peripheral connectors and miniature passives without clipping.
- **Unquantized Float32 Compatibility**: Engineered to feed unquantized float32 models via high-speed 32-bit packed RGB pixel features or POSIX Shared Memory (`features_shm`).
- **Parallel Dual-Process PCBA Scanning**: Runs Big Components and Small Passives `.eim` instances concurrently on separate CPU cores.

---

## 🏷️ Model Labels & Configurations

### 1. Stage 1: Slot Occupancy (`slot-occupancy.eim`)
- **Impulse Type**: Classification
- **Labels**: `Empty`, `PCB`, `PCBA`
- **Routing**:
  - `Empty`: Skips component scan, alerts operator (Amber/Red LED).
  - `PCB`: Routes to Bare PCB Defect Inspection.
  - `PCBA`: Routes to Parallel Component Inspection (Big + Small).

### 2. Stage 2A: Big Components (`big-components-inspection.eim`)
- **Impulse Type**: Object Detection
- **12 Classes**: `C1A`, `C1N`, `C2A`, `C2N`, `IA`, `IN`, `PA`, `PN`, `SA`, `SN`, `UA`, `UN`
- **6 Physical Components**:
  - `S` : Switch / Socket (Top Left)
  - `U` : IC / USB-C Unit (Top Right)
  - `C1`: Capacitor 1 (Bottom Left)
  - `I` : Inductor (Bottom Center-Left)
  - `P` : Power IC / Port (Bottom Center-Right)
  - `C2`: Capacitor 2 (Bottom Right)
- **Evaluation**: `A` (Available / Present) vs `N` (Absent / Missing).

### 3. Stage 2B: Small Components (`small-components-inspection.eim`)
- **Impulse Type**: Object Detection
- **26 Classes**:
  - Capacitors: `C1A`, `C1N`, `C2A`, `C2N`, `C3A`, `C3N`, `C4A`, `C4N`, `C5A`, `C5N`, `C6A`, `C6N`, `C7A`, `C7N`
  - Inductors / LEDs: `L1A`, `L1N`, `L2A`, `L2N`
  - Resistors: `R1A`, `R1N`, `R3A`, `R3N`, `R4A`, `R4N`, `R5A`, `R5N`
- **13 Physical Components**: Evaluated for `A` vs `N`.

### 4. Stage 3: Bare PCB Defect Inspection (`pcb-inspection.eim`)
- **Impulse Type**: Object Detection
- **1 Class**: `Issue` (Scratch, solder bridge, open circuit, copper exposed).
- **Evaluation**: 0 Issues = PASS; $\ge 1$ Issue = FAIL.

---

## 🛠️ Hardware Wiring & Communication

| Component | Pin / Channel | Description |
| :--- | :---: | :--- |
| **Servo Motor Signal** | **Pin 9** | 50Hz PWM driving 6-slot rotary table |
| **WS2812B NeoPixel Data**| **Pin 8** | Single-wire RGB indicator |
| **Power (Servo / LED)** | **5V / GND** | External 5V supply recommended |

### Turntable Slot Pulse Positions:
- **Slot 1**: `500 µs` (0°)
- **Slot 2**: `930 µs` (60°)
- **Slot 3**: `1360 µs` (120°)
- **Slot 4**: `1790 µs` (180°)
- **Slot 5**: `2220 µs` (240°)
- **Slot 6**: `2650 µs` (300°)

### Hardware Communication Backends:
1. **Arduino UNO Q Router Bridge**: Direct Unix socket `/var/run/arduino-router.sock` with MessagePack-RPC.
2. **Serial UART**: USB or `/dev/tty*` serial link @ 115200 baud.
3. **Virtual Simulation**: Automatic fallback for offline UI & camera testing.

---

## 🚀 Quickstart

### On Arduino UNO Q (Linux SBC):
```bash
cd "BMS EIM Vision Inspection"
chmod +x models/*.eim run_app.sh
./run_app.sh
```

### On Host PC (Windows / Testing):
Double-click `run_app.bat` or run:
```bash
python bms_eim_vision_inspection.py --source 0
```
Open your browser at `http://localhost:5000`.
