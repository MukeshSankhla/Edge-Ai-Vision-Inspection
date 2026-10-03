# Arduino Firmware Directory

This folder contains the embedded microcontroller firmware driving the physical automation hardware for the BMS Automated Optical Inspection (AOI) system.

## Subdirectories

- **[`bms_servo_led/`](file:///c:/Users/MAKERBRAINS/Downloads/Edge%20Ai%20Vision%20Inspection/BMS%20EIM%20Vision%20Inspection/arduino_firmware/bms_servo_led)**: Complete Arduino sketch (`bms_servo_led.ino`) and documentation.
  - Controls the 6-slot rotary inspection turntable via distance-aware non-blocking PWM (Pin 9).
  - Drives the WS2812B NeoPixel RGB indicator (Pin 8) with PASS/FAIL/MOVING/STANDBY colors.
  - Supports dual operation on Arduino UNO Q (Router Bridge RPC) and standard Arduino boards (Serial UART @ 115200 baud).

For complete hardware pinouts, protocol commands, timing diagrams, and flashing instructions, refer to **[`bms_servo_led/README.md`](file:///c:/Users/MAKERBRAINS/Downloads/Edge%20Ai%20Vision%20Inspection/BMS%20EIM%20Vision%20Inspection/arduino_firmware/bms_servo_led/README.md)**.
