/**
 * BMS Vision Inspection — Rotary Table Servo & WS2812B Controller
 * ==============================================================
 * Compatible with:
 *   - Arduino UNO Q (Qualcomm QRB2210 Linux MPU + STM32U585 Zephyr MCU via
 * Bridge RPC)
 *   - Standard Arduino boards (UNO, Nano, Mega via Serial UART)
 *
 * Hardware Wiring:
 *   - Servo Motor Signal: Pin 9 (PWM)
 *   - WS2812B NeoPixel Data: Pin 8 (RGB LED)
 *
 * Rotary Positions (Microseconds):
 *   Slot 1:  500 us
 *   Slot 2:  930 us
 *   Slot 3: 1360 us
 *   Slot 4: 1790 us
 *   Slot 5: 2220 us
 *   Slot 6: 2650 us
 *
 * LED Indications:
 *   - Motor Moving / Positioning: ORANGE (RGB: 255, 120, 0)
 *   - Inspection Result PASS:    GREEN  (RGB: 0, 255, 0)
 *   - Inspection Result FAIL:    RED    (RGB: 255, 0, 0)
 *   - Empty Slot / Standby:      AMBER  (RGB: 160, 90, 0)
 *
 * Distance-Aware Adaptive Settling:
 *   Adjacent slot movement (1 step) generates ~35 pulses (~700 ms).
 *   Full 180-degree return (Slot 6 -> Slot 1, 5 steps) dynamically scales
 *   to ~62 pulses (~1240 ms) so the turntable completely stops and settles
 *   before the camera captures, completely eliminating motion blur.
 */

#include <Adafruit_NeoPixel.h>

// Check for Arduino UNO Q Bridge header
#if defined(ARDUINO_ARCH_ZEPHYR) || defined(ARDUINO_UNO_Q) ||                  \
    __has_include(<Arduino_RouterBridge.h>)
#include <Arduino_RouterBridge.h>
#define HAS_ROUTER_BRIDGE 1
#endif

const int SERVO_PIN = 9;
const int LED_PIN = 8;

Adafruit_NeoPixel led(1, LED_PIN, NEO_GRB + NEO_KHZ800);

// Servo pulse widths for 6 slot positions (in microseconds)
const int POSITIONS[6] = {480, 940, 1360, 1780, 2220, 2650};

// Non-blocking pulse state machine
int currentSlot = 1;
volatile int targetPulse = 500;
volatile int pulsesRemaining = 0;
unsigned long lastPulseTime = 0;

void setOrange() {
  led.setPixelColor(0, led.Color(255, 120, 0));
  led.show();
}

void setGreen() {
  led.setPixelColor(0, led.Color(0, 255, 0));
  led.show();
}

void setRed() {
  led.setPixelColor(0, led.Color(255, 0, 0));
  led.show();
}

void setAmber() {
  led.setPixelColor(0, led.Color(160, 90, 0));
  led.show();
}

void setOff() {
  led.setPixelColor(0, led.Color(0, 0, 0));
  led.show();
}

// Non-blocking trigger: safe to call from Bridge RPC callbacks (< 1
// microsecond)
void moveServoSlot(int slot) {
  if (slot >= 1 && slot <= 6) {
    int dist = abs(slot - currentSlot);
    currentSlot = slot;
    targetPulse = POSITIONS[slot - 1];
    // Dynamic settle pulses (50 Hz = 20ms per pulse):
    // 1-step move (36 deg): 45 pulses (~900 ms)
    // 5-step return (Slot 6 -> 1, 180 deg sweep): 102 pulses (~2040 ms = 2.04s)
    if (dist <= 1) {
      pulsesRemaining = 45;
    } else {
      pulsesRemaining = 45 + (dist - 1) * 15;
    }
  }
}

void setLedState(String col) {
  col.toUpperCase();
  if (col == "PASS" || col == "P" || col == "GREEN") {
    setGreen();
  } else if (col == "FAIL" || col == "F" || col == "RED") {
    setRed();
  } else if (col == "ORANGE" || col == "O") {
    setOrange();
  } else {
    setAmber();
  }
}

void setup() {
  pinMode(SERVO_PIN, OUTPUT);
  digitalWrite(SERVO_PIN, LOW);

  led.begin();
  led.setBrightness(240);
  setAmber();

  // Move to initial home position (Slot 1)
  moveServoSlot(1);
  setGreen();

#if defined(HAS_ROUTER_BRIDGE)
  // Initialize internal Bridge RPC for Arduino UNO Q
  Bridge.begin();
  Bridge.provide_safe("move_servo", moveServoSlot);
  Bridge.provide_safe("set_led", setLedState);
#endif

  // Also initialize Serial for external serial/UART monitoring (D0/D1)
  Serial.begin(115200);
  Serial.println("OK:READY");
}

void loop() {
  unsigned long now = micros();

  // Generate 50Hz PWM pulses non-blockingly (every 20,000 microseconds)
  if (pulsesRemaining > 0 && (now - lastPulseTime >= 20000)) {
    lastPulseTime = now;
    digitalWrite(SERVO_PIN, HIGH);
    delayMicroseconds(targetPulse);
    digitalWrite(SERVO_PIN, LOW);
    pulsesRemaining--;
    // Send completion notification ONLY when motor has completely finished all
    // pulses!
    if (pulsesRemaining == 0) {
      Serial.print("OK:MOVED:");
      Serial.println(currentSlot);
    }
  }

  // Also service standard Serial commands ('1'..'6', 'P', 'F', 'O', 'E', '?')
  if (Serial.available() > 0) {
    char input = Serial.read();

    if (input == '\n' || input == '\r' || input == ' ') {
      return;
    }

    if (input >= '1' && input <= '6') {
      moveServoSlot(input - '0');
      Serial.print("ACK:MOVE:");
      Serial.println(input);
    } else if (input == 'P' || input == 'p') {
      setGreen();
      Serial.println("OK:PASS");
    } else if (input == 'F' || input == 'f') {
      setRed();
      Serial.println("OK:FAIL");
    } else if (input == 'O' || input == 'o') {
      setOrange();
      Serial.println("OK:ORANGE");
    } else if (input == 'E' || input == 'e') {
      setAmber();
      Serial.println("OK:EMPTY");
    } else if (input == '?') {
      Serial.println("OK:READY");
    } else {
      Serial.print("ERR:UNKNOWN_CMD:");
      Serial.println(input);
    }
  }
}
