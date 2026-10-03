# BMS Vision Inspection — Rotary Table Servo & WS2812B Controller Firmware

Firmware for the 6-slot indexing rotary turntable and WS2812B RGB NeoPixel inspection indicator in the BMS Automated Optical Inspection (AOI) system.

Compatible with:
- **Arduino UNO Q** (Qualcomm QRB2210 Linux MPU + STM32U585 Zephyr MCU via internal MessagePack Bridge RPC)
- **Standard Arduino & Microcontroller Boards** (UNO R3/R4, Nano, Mega, ESP32, RP2040, STM32 via USB-Serial UART @ 115200 baud)

---

## 📑 Table of Contents

- [Overview & Key Features](#-overview--key-features)
- [Hardware Wiring & Pinout](#-hardware-wiring--pinout)
- [How the Code Works](#-how-the-code-works)
  - [1. Dual-Architecture Communication](#1-dual-architecture-communication)
  - [2. Non-Blocking 50 Hz Software Pulse Generator](#2-non-blocking-50-hz-software-pulse-generator)
  - [3. Distance-Aware Adaptive Settle Engine](#3-distance-aware-adaptive-settle-engine)
  - [4. Calibrated Slot Microsecond Pulse Table](#4-calibrated-slot-microsecond-pulse-table)
  - [5. WS2812B LED Color Indications](#5-ws2812b-led-color-indications)
- [Serial UART Protocol Specification](#-serial-uart-protocol-specification)
- [Arduino UNO Q Bridge RPC Specification](#-arduino-uno-q-bridge-rpc-specification)
- [Dependencies & Installation](#-dependencies--installation)
- [Compilation & Flashing](#-compilation--flashing)
  - [Option A: Arduino IDE](#option-a-arduino-ide)
  - [Option B: PlatformIO CLI](#option-b-platformio-cli)
  - [Option C: Arduino UNO Q App Lab / CLI](#option-c-arduino-uno-q-app-lab--cli)
- [Testing & Verification](#-testing--verification)

---

## 🎯 Overview & Key Features

The `bms_servo_led.ino` sketch acts as the low-latency hardware actuator bridge between the high-level Python AOI vision inspection engine and the physical inspection rig.

### Key Capabilities:
- **Non-Blocking Control Loop:** Does not rely on blocking `delay()` calls or traditional hardware timers that conflict with the NeoPixel library or Zephyr RTOS scheduler.
- **Distance-Aware Settling:** Rotary indexing mechanisms have angular inertia. The firmware dynamically emits calibrated stabilization pulse bursts based on distance traveled, completely eliminating camera motion blur.
- **Dual Communication Modes:** Seamlessly services high-speed MessagePack Bridge RPC on the Arduino UNO Q while concurrently serving an ASCII command protocol over hardware Serial UART.
- **Visual Status Annunciation:** Drives an ultra-bright WS2812B addressable LED with dedicated colors for Moving, Pass, Fail, and Standby states.

---

## 🔌 Hardware Wiring & Pinout

```
   ┌────────────────────────────────────────────────────────┐
   │             Arduino / STM32 / UNO Q MCU                │
   │                                                        │
   │   [Pin 9] (PWM Out) ──────> Servo Motor Signal (Yellow)│
   │   [Pin 8] (GPIO Out)─────> WS2812B DIN (Data In)       │
   │   [GND]   ───────────────> Common Logic GND            │
   │   [5V]    ───────────────> Logic 5V VCC                │
   └────────────────────────────────────────────────────────┘
                                   │
                                   ▼
        ┌─────────────────────────────────────────────────┐
        │  *RECOMMENDED EXTERNAL POWER FOR SERVO MOTOR*   │
        │  - External 5V / 2A DC Power Supply             │
        │  - Servo +5V (Red) ──> External 5V (+)          │
        │  - Servo GND (Brown)─> External GND (-) & MCU G │
        └─────────────────────────────────────────────────┘
```

| MCU Pin | Signal Name | Connected Device | Function |
| :---: | :---: | :--- | :--- |
| **Pin 9** | `SERVO_PIN` | Rotary Servo Signal Wire (White/Yellow) | Software 50Hz PWM pulse train |
| **Pin 8** | `LED_PIN` | WS2812B NeoPixel Data In (`DIN`) | 800 kHz single-wire NeoPixel data |
| **GND** | `GND` | Servo GND + LED GND + Power Supply GND | Common electrical reference |
| **5V** | `5V` | LED VDD (+5V) | Power for single WS2812B LED |

> [!WARNING]
> High-torque servo motors can draw momentary peak currents up to 1.5A–2.0A during rapid rotary table index sweeps. **Always power the servo from an external regulated 5V power supply with a common ground**, rather than drawing power directly from the microcontroller's 5V regulator.

---

## 🧠 How the Code Works

### 1. Dual-Architecture Communication

The firmware uses conditional compilation to detect whether it is compiling for the Arduino UNO Q's Zephyr RTOS core:

```cpp
#if defined(ARDUINO_ARCH_ZEPHYR) || defined(ARDUINO_UNO_Q) || __has_include(<Arduino_RouterBridge.h>)
#include <Arduino_RouterBridge.h>
#define HAS_ROUTER_BRIDGE 1
#endif
```

- When running on **Arduino UNO Q**, it calls `Bridge.begin()` and registers two RPC callback methods:
  - `Bridge.provide_safe("move_servo", moveServoSlot);`
  - `Bridge.provide_safe("set_led", setLedState);`
  The `provide_safe` wrapper ensures calls from the Qualcomm QRB2210 Linux MPU execute safely across threads without interrupting critical MCU routines.
- Simultaneously, it initializes `Serial.begin(115200)`, allowing standard USB-Serial or UART monitoring and control on any Arduino platform.

---

### 2. Non-Blocking 50 Hz Software Pulse Generator

Standard Arduino `Servo.h` libraries frequently conflict with the strict timing interrupts required by the `Adafruit_NeoPixel` library (which turns off interrupts during `strip.show()`). Furthermore, on Zephyr-based RTOS boards like the Arduino UNO Q, hardware timer allocations differ.

To ensure 100% rock-solid determinism, `bms_servo_led.ino` generates RC servo PWM pulses manually using a non-blocking timestamp counter:

```cpp
unsigned long now = micros();

// Generate 50Hz PWM pulses non-blockingly (every 20,000 microseconds = 50 Hz)
if (pulsesRemaining > 0 && (now - lastPulseTime >= 20000)) {
  lastPulseTime = now;
  digitalWrite(SERVO_PIN, HIGH);
  delayMicroseconds(targetPulse);
  digitalWrite(SERVO_PIN, LOW);
  pulsesRemaining--;

  // Send completion notification ONLY when motor has completely finished all pulses!
  if (pulsesRemaining == 0) {
    Serial.print("OK:MOVED:");
    Serial.println(currentSlot);
  }
}
```

- **Period:** Exactly 20,000 µs (50 Hz frame rate).
- **Pulse Duration:** Held HIGH for `targetPulse` microseconds (between 480 µs and 2650 µs), then pulled LOW.
- **Zero Drift:** Uses `micros()` delta comparison, allowing `loop()` to continuously check serial commands or bridge notifications without stalling.

---

### 3. Distance-Aware Adaptive Settle Engine

A major engineering challenge with rotary inspection tables is mechanical inertia and settling vibration. When moving 1 slot ($60^\circ$), the table reaches destination quickly. However, when resetting from **Slot 6 back to Slot 1** ($300^\circ$ reverse sweep), the table carries high momentum. If the camera captures an image too soon, the resulting image is blurry.

The `moveServoSlot(int slot)` function dynamically adapts the number of pulses generated:

```cpp
void moveServoSlot(int slot) {
  if (slot >= 1 && slot <= 6) {
    int dist = abs(slot - currentSlot);
    currentSlot = slot;
    targetPulse = POSITIONS[slot - 1];

    if (dist <= 1) {
      pulsesRemaining = 45;              // 45 pulses * 20ms = ~900 ms
    } else {
      pulsesRemaining = 45 + (dist - 1) * 15; // e.g. dist 5: 105 pulses = ~2100 ms
    }
  }
}
```

| Travel Type | Slot Delta (`dist`) | Number of Pulses | Active Settling Duration | Mechanical Objective |
| :--- | :---: | :---: | :---: | :--- |
| **Stationary / Same Slot** | 0 | 45 | 900 ms | Holds position steady |
| **Adjacent Step** (e.g. 1 $\to$ 2) | 1 | 45 | 900 ms | Smooth indexing step |
| **2-Step Move** (e.g. 1 $\to$ 3) | 2 | 60 | 1,200 ms | Intermediate travel dampening |
| **3-Step Move** (e.g. 1 $\to$ 4) | 3 | 75 | 1,500 ms | Half-circle dampening |
| **4-Step Move** (e.g. 1 $\to$ 5) | 4 | 90 | 1,800 ms | Extended travel settling |
| **Full Reverse** (6 $\to$ 1) | 5 | 105 | 2,100 ms | Complete dampening of $300^\circ$ inertia sweep |

Only after the last pulse is delivered does the MCU emit `OK:MOVED:<slot>`, notifying the Python host that the table is dead still and ready for optical capture.

---

### 4. Calibrated Slot Microsecond Pulse Table

```cpp
const int POSITIONS[6] = {480, 940, 1360, 1780, 2220, 2650};
```

```
                     Slot 1 (480 µs / ~0°)
                            ▲
                            │
       Slot 6 (2650 µs) ────┼──── Slot 2 (940 µs)
                            │
       Slot 5 (2220 µs) ────┼──── Slot 3 (1360 µs)
                            │
                            ▼
                     Slot 4 (1780 µs / ~180°)
```

These pulse widths correspond to standard 180° / 270° / 300° wide-angle precision industrial servos. If your turntable mechanical linkage or gearing ratio requires different angles, adjust the `POSITIONS` array in line 49.

---

### 5. WS2812B LED Color Indications

The addressable NeoPixel LED delivers instantaneous feedback to human operators:

| LED Color | RGB Code | Constant | Inspection Context |
| :--- | :---: | :---: | :--- |
| **ORANGE** | `(255, 120, 0)` | `setOrange()` | Turntable in motion; position changing |
| **GREEN** | `(0, 255, 0)` | `setGreen()` | Inspection **PASS** (Zero defects detected) |
| **RED** | `(255, 0, 0)` | `setRed()` | Inspection **FAIL** (Defects or missing components) |
| **AMBER** | `(160, 90, 0)` | `setAmber()` | Standby / Empty fixture slot detected / Bootup |
| **OFF** | `(0, 0, 0)` | `setOff()` | Sleep / Diagnostic mode |

---

## 📡 Serial UART Protocol Specification

Baud Rate: **115200** | Data Bits: **8** | Parity: **None** | Stop Bits: **1**

### Commands (Host $\to$ MCU):

| Command (ASCII) | Description | Example |
| :---: | :--- | :---: |
| `'1'` – `'6'` | Move turntable to designated slot index | `2\n` |
| `'P'` / `'p'` | Set status LED to GREEN (PASS) | `P\n` |
| `'F'` / `'f'` | Set status LED to RED (FAIL) | `F\n` |
| `'O'` / `'o'` | Set status LED to ORANGE (Moving) | `O\n` |
| `'E'` / `'e'` | Set status LED to AMBER (Empty / Standby) | `E\n` |
| `'?'` | Query firmware readiness status | `?\n` |

### Responses (MCU $\to$ Host):

| Response (ASCII) | Trigger Condition | Meaning |
| :--- | :--- | :--- |
| `OK:READY` | Startup or in response to `'?'` ping | Firmware initialized and ready |
| `ACK:MOVE:<N>` | Immediately upon receiving `'1'`..`'6'` | Command accepted, motion began |
| `OK:MOVED:<N>` | When all adaptive pulses finish | Turntable has fully settled at slot `<N>` |
| `OK:PASS` | In response to `'P'` | LED set to Green |
| `OK:FAIL` | In response to `'F'` | LED set to Red |
| `OK:ORANGE` | In response to `'O'` | LED set to Orange |
| `OK:EMPTY` | In response to `'E'` | LED set to Amber |
| `ERR:UNKNOWN_CMD:<C>` | Any unrecognized character | Syntax error or unsupported command |

---

## ⚡ Arduino UNO Q Bridge RPC Specification

When compiled with `HAS_ROUTER_BRIDGE`, the sketch exports RPC endpoints to the internal UNIX domain socket router (`/var/run/arduino-router.sock`):

### 1. `move_servo(int slot)`
- **Parameters:** `slot` (Integer: `1` to `6`)
- **Execution:** Safe non-blocking execution (< 1 µs execution time). Updates `targetPulse` and starts the pulse generator state machine.
- **Python Invocation:**
  ```python
  bridge_client.notify("move_servo", 3)
  ```

### 2. `set_led(String col)`
- **Parameters:** `col` (String: `"PASS"`, `"FAIL"`, `"ORANGE"`, `"AMBER"`, `"GREEN"`, `"RED"`)
- **Execution:** Case-insensitive parser updates the WS2812B NeoPixel buffer immediately.
- **Python Invocation:**
  ```python
  bridge_client.notify("set_led", "PASS")
  ```

---

## 📦 Dependencies & Installation

### Required Arduino Libraries:
1. **Adafruit NeoPixel** (by Adafruit) — Install via Arduino IDE Library Manager or `pio pkg install -l "adafruit/Adafruit NeoPixel"`.
2. **Arduino_RouterBridge** (pre-installed in the Arduino UNO Q core board package; automatically included when targeting UNO Q).

---

## 🚀 Compilation & Flashing

### Option A: Arduino IDE
1. Open the Arduino IDE (v2.x recommended).
2. Open [`bms_servo_led.ino`](file:///c:/Users/MAKERBRAINS/Downloads/Edge%20Ai%20Vision%20Inspection/BMS%20EIM%20Vision%20Inspection/arduino_firmware/bms_servo_led/bms_servo_led.ino).
3. Install **Adafruit NeoPixel** from **Tools $\to$ Manage Libraries...**.
4. Select your board:
   - For standard Arduino: Select **Arduino Uno**, **Arduino Nano**, or corresponding board.
   - For Arduino UNO Q: Select **Arduino UNO Q (STM32U585)**.
5. Select the correct COM / Serial port.
6. Click **Upload** ($\rightarrow$).

### Option B: PlatformIO CLI
Create a minimal `platformio.ini` in the firmware folder:
```ini
[env:uno]
platform = atmelavr
board = uno
framework = arduino
lib_deps =
    adafruit/Adafruit NeoPixel@^1.12.0
monitor_speed = 115200
```
Then run:
```bash
pio run --target upload
```

### Option C: Arduino UNO Q App Lab / CLI
```bash
arduino-app-cli compile --fqbn arduino:zephyr:uno_q bms_servo_led
arduino-app-cli upload --fqbn arduino:zephyr:uno_q bms_servo_led
```

---

## 🧪 Testing & Verification

### Using Serial Monitor:
1. Open the Arduino IDE Serial Monitor (or PuTTY / minicom) at **115200 baud** with `Newline` (`\n`) line ending.
2. Observe startup output:
   ```
   OK:READY
   ```
3. Type `2` and press Enter:
   - Observe immediate reply: `ACK:MOVE:2`
   - The LED turns Orange during motion.
   - Servo rotates smoothly to Slot 2 position.
   - Upon settling ($\sim 900$ ms), observe completion message: `OK:MOVED:2`.
4. Type `P` and press Enter:
   - Observe reply: `OK:PASS`
   - LED instantly turns vivid Green.
5. Type `F` and press Enter:
   - Observe reply: `OK:FAIL`
   - LED instantly turns vivid Red.
