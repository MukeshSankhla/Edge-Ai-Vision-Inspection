#!/usr/bin/env python3
"""
BMS Vision Inspection — Pure Edge Impulse (.eim) Photo-Level AOI System
======================================================================
Engineered for Arduino UNO Q (Qualcomm QRB2210 Linux MPU + STM32U585 Zephyr MCU)
& Edge SBCs (Debian / Linux / Cross-Platform).

Key Architectural Specifications:
  1. Pure .EIM Execution (ZERO ONNX RUNTIME):
     - Directly communicates with compiled Edge Impulse .eim binaries via Unix domain socket IPC
     - High-speed POSIX Shared Memory (SHM) zero-copy tensor streaming
  2. Fit-Longest Aspect-Ratio Preserving Preprocessing:
     - Scales longest axis to model input dimensions and pads with 0
     - Configured for unquantized float32 Edge Impulse models
     - Guarantees 100% field-of-view retention for peripheral SMD passives and edge connectors
  3. Arduino UNO Q Dual-Domain Architecture:
     - Pure Python zero-dependency Unix domain socket client connecting to /var/run/arduino-router.sock
     - Full fallback for arduino.app_utils.Bridge, UART Serial, or Virtual Simulation
  4. Photo-Level 6-Slot Turntable Inspection:
     - Continuous camera worker drains V4L2/DirectShow buffers for zero queue lag
     - Distance-adaptive servo travel and settle delay eliminates motion blur
  5. Minimal Lightweight Runtime:
     - Strictly uses: Flask, OpenCV, NumPy (no onnxruntime).
"""

import os
import sys
import time
import json
import glob
import math
import socket
import shutil
import signal
import tempfile
import argparse
import threading
import subprocess
import concurrent.futures
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, Response, render_template_string, jsonify, request, send_file, redirect

# Verify OpenCV is a real functional installation (not the fake/empty PyPI 'cv2' package)
if not hasattr(cv2, "VideoCapture") or not hasattr(cv2, "cvtColor"):
    print("\n" + "=" * 72)
    print("  [CRITICAL ERROR] The installed 'cv2' module has no VideoCapture/cvtColor!")
    print("  This occurs when the dummy placeholder PyPI package 'cv2' was installed")
    print("  instead of 'opencv-python-headless', or OpenCV was corrupted during install.")
    print("  Fix it by running these commands in your active virtualenv (.venv):")
    print("      pip uninstall -y cv2 opencv-python opencv-python-headless")
    print("      pip install --no-cache-dir opencv-python-headless")
    print("=" * 72 + "\n")
    sys.exit(1)

# POSIX Shared Memory for zero-copy EIM tensor feeds
try:
    from multiprocessing import shared_memory
    HAS_SHM = True
except ImportError:
    shared_memory = None
    HAS_SHM = False

# Arduino UNO Q app_utils
try:
    from arduino.app_utils import Bridge
    HAS_APP_BRIDGE = True
except ImportError:
    Bridge = None
    HAS_APP_BRIDGE = False

# PySerial
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

# ── DIRECTORIES & MODEL BINDINGS ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent
MODELS_DIR    = BASE_DIR / "models"
SNAPSHOT_DIR  = BASE_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# Direct paths to Edge Impulse .eim models
SLOT_MODEL_P  = MODELS_DIR / "slot-occupancy.eim"
BIG_MODEL_P   = MODELS_DIR / "big-components-inspection.eim"
SMALL_MODEL_P = MODELS_DIR / "small-components-inspection.eim"
PCB_MODEL_P   = MODELS_DIR / "pcb-inspection.eim"

# ── HARDWARE CONSTANTS ───────────────────────────────────────────────────────
SERVO_POSITIONS   = [500, 930, 1360, 1790, 2220, 2650]  # Pulse widths for slots 1-6
AUTO_IDLE_TIMEOUT = 10.0                               # Revert to Auto Loop after 10s idle

# ── COMPONENT DEFINITIONS & LABELS (PER TRAINING DATASETS) ───────────────────
# Big Components: 6 Physical Locations, 12 Classes (A = Available/Present, N = Absent/Missing)
BIG_CLASSES = [
    "C1A", "C1N", "C2A", "C2N", "IA", "IN", "PA", "PN", "SA", "SN", "UA", "UN"
]
BIG_COMPONENTS = [
    ("S",  "Switch / Socket"),
    ("U",  "IC / USB Unit"),
    ("C1", "Capacitor 1"),
    ("I",  "Inductor"),
    ("P",  "Power IC"),
    ("C2", "Capacitor 2"),
]

# Small Components: 13 Physical Locations, 26 Classes
SMALL_CLASSES = [
    "C1A", "C1N", "C2A", "C2N", "C3A", "C3N", "C4A", "C4N",
    "C5A", "C5N", "C6A", "C6N", "C7A", "C7N", "L1A", "L1N",
    "L2A", "L2N", "R1A", "R1N", "R3A", "R3N", "R4A", "R4N",
    "R5A", "R5N",
]
SMALL_COMPONENTS = [
    ("C1", "Capacitor 1"),
    ("C2", "Capacitor 2"),
    ("C3", "Capacitor 3"),
    ("C4", "Capacitor 4"),
    ("C5", "Capacitor 5"),
    ("C6", "Capacitor 6"),
    ("C7", "Capacitor 7"),
    ("L1", "Inductor / LED 1"),
    ("L2", "Inductor / LED 2"),
    ("R1", "Resistor 1"),
    ("R3", "Resistor 3"),
    ("R4", "Resistor 4"),
    ("R5", "Resistor 5"),
]

# Fixture Occupancy Classes
SLOT_CLASSES  = ["Empty", "PCB", "PCBA"]

# Bare PCB Defect Classes
PCB_CLASSES   = ["Issue"]

# Visual Overlays Colors (BGR)
COLOR_AVAILABLE   = (46, 170, 40)     # Clean green (PASS / Present)
COLOR_MISSING     = (35, 45, 230)     # Vivid red (FAIL / Missing)
COLOR_WARN_AMBER  = (10, 150, 240)    # Amber / warning
COLOR_ROI_CYAN    = (210, 150, 30)    # Cyan / teal for reticle

FONT    = getattr(cv2, "FONT_HERSHEY_DUPLEX", 2)
FONTS   = getattr(cv2, "FONT_HERSHEY_SIMPLEX", 0)
LINE_AA = getattr(cv2, "LINE_AA", 16)


# ── ARDUINO UNO Q DIRECT ROUTER BRIDGE CLIENT ────────────────────────────────
class UnoQBridgeClient:
    """
    Direct zero-dependency Unix domain socket client for Arduino UNO Q's arduino-router.
    Communicates via MessagePack-RPC over /var/run/arduino-router.sock.
    Pure Python standard library implementation.
    """
    SOCK_PATH = "/var/run/arduino-router.sock"

    def __init__(self):
        self.sock = None
        self.is_connected = False
        self.lock = threading.Lock()
        self.connect()

    def _pack_str(self, s):
        b = str(s).encode("utf-8")
        l = len(b)
        if l <= 31:
            return bytes([0xa0 | l]) + b
        elif l <= 0xFF:
            return b"\xd9" + bytes([l]) + b
        return b"\xda" + l.to_bytes(2, "big") + b

    def _pack_notify(self, method, args):
        m_bytes = self._pack_str(method)
        arg_bytes = bytes([0x90 | len(args)])
        for a in args:
            if isinstance(a, int):
                arg_bytes += bytes([a]) if 0 <= a <= 127 else (b"\xcc" + bytes([a]))
            elif isinstance(a, str):
                arg_bytes += self._pack_str(a)
        return b"\x93\x02" + m_bytes + arg_bytes

    def connect(self):
        with self.lock:
            if not os.path.exists(self.SOCK_PATH):
                self.is_connected = False
                return False
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(self.SOCK_PATH)
                self.sock = s
                self.is_connected = True
                return True
            except Exception:
                self.sock = None
                self.is_connected = False
                return False

    def notify(self, method, *args):
        pkt = self._pack_notify(method, args)
        with self.lock:
            if not self.is_connected or self.sock is None:
                if not self.connect():
                    return False
            try:
                self.sock.sendall(pkt)
                return True
            except Exception:
                self.is_connected = False
                self.sock = None
                return False

    def close(self):
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
            self.sock = None
            self.is_connected = False


# ── ARDUINO HARDWARE INTERFACE ───────────────────────────────────────────────
class ArduinoHardwareController:
    """
    Unified Hardware Controller supporting:
      1. Arduino UNO Q Direct Unix Socket Bridge (/var/run/arduino-router.sock)
      2. Arduino UNO Q app_utils.Bridge RPC
      3. UART Serial Interface (USB / External Arduino)
      4. Virtual Simulation Fallback
    """
    def __init__(self, port="auto", baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.bridge_client = UnoQBridgeClient()
        self.backend = "sim"
        self.is_connected = False
        self.current_led = "GREEN"
        self.current_slot = 1
        self.lock = threading.Lock()
        self._connect()

    @staticmethod
    def list_available_ports():
        ports = []
        if os.path.exists("/var/run/arduino-router.sock") or HAS_APP_BRIDGE:
            ports.append({"device": "bridge", "description": "Arduino UNO Q Internal Bridge"})

        if serial is not None:
            try:
                for p in serial.tools.list_ports.comports():
                    desc = (p.description or p.device).strip()
                    hwid = (p.hwid or "").strip()
                    if "bluetooth" in desc.lower() or "bthenum" in hwid.lower():
                        continue
                    ports.append({"device": p.device, "description": desc})
            except Exception:
                pass

        if sys.platform.startswith("linux"):
            for p in glob.glob("/dev/ttyRPMSG*") + glob.glob("/dev/ttyHS*") + glob.glob("/dev/ttyMSM*") + glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"):
                ports.append({"device": p, "description": p})

        return ports

    def _find_candidate_ports(self):
        candidates = []
        if serial is not None:
            try:
                for p in serial.tools.list_ports.comports():
                    desc = (p.description or "").lower()
                    hwid = (p.hwid or "").lower()
                    if "bluetooth" in desc or "bthenum" in hwid:
                        continue
                    candidates.append(p.device)
            except Exception:
                pass

        if sys.platform.startswith("linux"):
            for p in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyHS0", "/dev/ttyRPMSG0"]:
                if os.path.exists(p) and p not in candidates:
                    candidates.append(p)

        return candidates

    def connect_to_port(self, port="auto", baudrate=115200):
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None

            self.port = port
            self.baudrate = baudrate
            self.is_connected = False

            # Check UNO Q internal bridge
            if port in ("auto", "bridge") and (self.bridge_client.is_connected or os.path.exists("/var/run/arduino-router.sock") or HAS_APP_BRIDGE):
                if not self.bridge_client.is_connected:
                    self.bridge_client.connect()
                if self.bridge_client.is_connected or HAS_APP_BRIDGE:
                    self.backend = "bridge"
                    self.is_connected = True
                    print(f"  [Hardware] Connected via Arduino UNO Q Internal Bridge (/var/run/arduino-router.sock)")
                    return True, "Connected via Arduino UNO Q Internal Bridge"

            if serial is None:
                self.backend = "sim"
                self.is_connected = False
                return False, "pyserial not installed (running simulation)"

            candidates = [port] if (port != "auto" and port != "bridge") else self._find_candidate_ports()

            for cand in candidates:
                try:
                    print(f"  [Hardware] Attempting serial connection to {cand} @ {baudrate}...")
                    s = serial.Serial(cand, baudrate, timeout=1.0, write_timeout=1.0)
                    time.sleep(1.8)
                    self.ser = s
                    self.backend = "serial"
                    self.is_connected = True
                    self.port = cand
                    print(f"  [Hardware] Successfully connected via Serial: {cand}")
                    return True, f"Connected to {cand}"
                except Exception as e:
                    print(f"  [Hardware] Serial open failed on {cand}: {e}")

            self.backend = "sim"
            self.is_connected = False
            return False, f"Could not open {port}"

    def _connect(self):
        if self.port == "none":
            print("  [Hardware] Hardware link disabled. Running in Virtual Simulation mode.")
            return

        ok, msg = self.connect_to_port(self.port, self.baudrate)
        if not ok:
            print(f"  [Hardware] {msg}")

    def move_to_slot(self, slot_id):
        """Commands servo to rotate to target slot (1-6). Distance-adaptive timing prevents motion blur."""
        slot_id = max(1, min(6, int(slot_id)))
        prev_slot = self.current_slot
        dist = abs(slot_id - prev_slot)
        self.current_slot = slot_id

        # Adaptive travel time for rotary table inertia
        if dist <= 0:
            travel_time = 0.40
        elif dist == 1:
            travel_time = 0.82
        else:
            travel_time = 0.82 + (dist - 1) * 0.28  # dist 5 => ~1.94s

        with self.lock:
            if self.bridge_client.is_connected or self.backend == "bridge":
                self.bridge_client.notify("move_servo", slot_id)
                if HAS_APP_BRIDGE:
                    try:
                        Bridge.notify("move_servo", int(slot_id))
                    except Exception:
                        pass
                time.sleep(travel_time)
            elif self.backend == "serial" and self.ser:
                try:
                    self.ser.reset_input_buffer()
                    cmd = f"{slot_id}\n".encode("utf-8")
                    self.ser.write(cmd)
                    self.ser.flush()
                except Exception as e:
                    print(f"[Hardware Warning] Serial write error: {e}")
                time.sleep(travel_time)
            else:
                time.sleep(travel_time)

    def set_led(self, state):
        """Sets WS2812B NeoPixel indicator: Strictly 'PASS' (Green) or 'FAIL' (Red)."""
        state = state.upper()
        if state in ("PASS", "GREEN", "P"):
            self.current_led = "PASS"
            cmd_char = 'P'
            bridge_state = "PASS"
        else:
            self.current_led = "FAIL"
            cmd_char = 'F'
            bridge_state = "FAIL"

        with self.lock:
            if self.bridge_client.is_connected or self.backend == "bridge":
                self.bridge_client.notify("set_led", bridge_state)
                if HAS_APP_BRIDGE:
                    try:
                        Bridge.notify("set_led", bridge_state)
                    except Exception:
                        pass
            elif self.backend == "serial" and self.ser:
                try:
                    self.ser.write(f"{cmd_char}\n".encode("utf-8"))
                    self.ser.flush()
                except Exception:
                    pass

    def close(self):
        with self.lock:
            self.bridge_client.close()
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.is_connected = False


# ── PURE NATIVE EDGE IMPULSE .EIM RUNNER (ZERO ONNX RUNTIME) ─────────────────
class NativeEIMRunner:
    """
    High-performance zero-dependency Edge Impulse .eim runner.
    Directly spawns and communicates with compiled .eim executables over a Unix domain socket
    using POSIX Shared Memory zero-copy IPC or standard socket fallback.
    Implements fit-longest aspect ratio preserving letterbox preprocessing for float32 unquantized models.
    """
    def __init__(self, model_path: str, allow_shm: bool = True):
        self._model_path = str(model_path)
        self._tempdir = None
        self._proc = None
        self._client = None
        self._ix = 0
        self.dim = (0, 0)
        self.labels = []
        self.isGrayscale = False
        self.model_type = "object_detection"
        self._allow_shm = allow_shm and HAS_SHM
        self._input_shm = None
        self.is_mock = False

    def init(self, debug=False):
        p = Path(self._model_path)
        if not p.exists():
            raise FileNotFoundError(f"Model file does not exist: {self._model_path}")

        # Check if platform supports running ELF AArch64 executable directly
        can_exec = sys.platform.startswith("linux")
        if not can_exec:
            self.is_mock = True
            name = p.stem.lower()
            if "slot" in name:
                self.dim = (224, 224)
                self.labels = SLOT_CLASSES
                self.model_type = "classification"
            elif "big" in name:
                self.dim = (640, 640)
                self.labels = BIG_CLASSES
                self.model_type = "object_detection"
            elif "small" in name:
                self.dim = (640, 640)
                self.labels = SMALL_CLASSES
                self.model_type = "object_detection"
            elif "pcb" in name:
                self.dim = (640, 640)
                self.labels = PCB_CLASSES
                self.model_type = "object_detection"
            else:
                self.dim = (640, 640)
                self.labels = []
                self.model_type = "object_detection"

            print(f"    [EIM Runner Notice] Host OS: {sys.platform}. ELF AArch64 binary '{p.name}' running in simulation mode. Fully operational on Linux SBC / Arduino UNO Q.")
            return {
                "project": {"name": p.stem},
                "model_parameters": {
                    "image_input_width": self.dim[0],
                    "image_input_height": self.dim[1],
                    "labels": self.labels,
                    "model_type": self.model_type
                }
            }

        # Make binary executable on Linux
        try:
            os.chmod(self._model_path, 0o755)
        except Exception:
            pass

        self._tempdir = tempfile.mkdtemp(prefix="ei_runner_")
        sock_path = os.path.join(self._tempdir, "runner.sock")
        cmd = [self._model_path, sock_path]

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL if not debug else None,
            stderr=subprocess.DEVNULL if not debug else None,
        )

        t_start = time.time()
        while (not os.path.exists(sock_path)) or self._proc.poll() is not None:
            if self._proc.poll() is not None:
                raise RuntimeError(f"Edge Impulse .eim binary failed to start (exit code {self._proc.poll()})")
            if time.time() - t_start > 15.0:
                raise TimeoutError(f"Timed out waiting for .eim socket at {sock_path}")
            time.sleep(0.05)

        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(45.0)
        s.connect(sock_path)
        self._client = s

        hello_resp = self.send_msg({"hello": 1})
        params = hello_resp.get("model_parameters", {})
        w = params.get("image_input_width", 0)
        h = params.get("image_input_height", 0)
        self.dim = (w, h)
        self.labels = params.get("labels", [])
        self.isGrayscale = (params.get("image_channel_count", 3) == 1)
        self.model_type = params.get("model_type", "object_detection")

        # Attach POSIX Shared Memory for zero-copy tensor feed
        if self._allow_shm and "features_shm" in hello_resp:
            try:
                shm_info = hello_resp["features_shm"]
                raw_name = shm_info.get("name", "")
                shm_name = raw_name.lstrip("/")
                try:
                    shm = shared_memory.SharedMemory(name=shm_name)
                except Exception:
                    shm = shared_memory.SharedMemory(name=raw_name)
                self._input_shm = {
                    "shm": shm,
                    "type": shm_info.get("type", "float32"),
                    "elements": shm_info.get("elements", w * h),
                    "array": np.ndarray((shm_info.get("elements", w * h),), dtype=np.float32, buffer=shm.buf)
                }
                print(f"    [IPC] Shared Memory enabled for {Path(self._model_path).name} (Zero-Copy)")
            except Exception as e:
                self._input_shm = None
                print(f"    [IPC Note] Standard socket IPC used for {Path(self._model_path).name}: {e}")

        return hello_resp

    @staticmethod
    def resize_fit_longest(img, target_width, target_height):
        """
        Fit-Longest (Aspect-Ratio Preserving) Preprocessing:
        Scales the image uniformly so the longest side matches the target dimension,
        then pads the shorter side symmetrically with 0 (black).
        Matches Edge Impulse 'fit-longest' studio export setting.
        """
        orig_h, orig_w = img.shape[:2]
        scale = min(target_width / orig_w, target_height / orig_h)
        new_w = int(round(orig_w * scale))
        new_h = int(round(orig_h * scale))

        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        scaled = cv2.resize(img, (new_w, new_h), interpolation=interp)

        top_pad = (target_height - new_h) // 2
        bottom_pad = target_height - new_h - top_pad
        left_pad = (target_width - new_w) // 2
        right_pad = target_width - new_w - left_pad

        padded = cv2.copyMakeBorder(
            scaled, top_pad, bottom_pad, left_pad, right_pad, cv2.BORDER_CONSTANT, value=[0, 0, 0]
        )
        return padded, scale, left_pad, top_pad

    def get_features_from_image(self, img):
        """
        Converts input RGB image into Edge Impulse 32-bit packed feature buffer.
        Applies fit-longest letterboxing.
        Returns: (features, processed_canvas, meta_dict)
        """
        target_w, target_h = self.dim
        if target_w == 0 or target_h == 0:
            target_w, target_h = 640, 640

        orig_h, orig_w = img.shape[:2]
        canvas, scale, left_pad, top_pad = self.resize_fit_longest(img, target_w, target_h)

        meta = {
            "scale": scale,
            "left_pad": left_pad,
            "top_pad": top_pad,
            "orig_w": orig_w,
            "orig_h": orig_h,
            "canvas_w": target_w,
            "canvas_h": target_h
        }

        # Vectorized pixel packing ((R << 16) | (G << 8) | B) for unquantized float32 EIM DSP blocks
        if self.isGrayscale:
            gray = cv2.cvtColor(canvas, cv2.COLOR_RGB2GRAY) if len(canvas.shape) == 3 else canvas
            p = gray.astype(np.uint32)
            features = ((p << 16) | (p << 8) | p).flatten()
        else:
            pixels = canvas.astype(np.uint32)
            r = pixels[:, :, 0]
            g = pixels[:, :, 1]
            b = pixels[:, :, 2]
            features = ((r << 16) | (g << 8) | b).flatten()

        return features, canvas, meta

    def classify(self, data):
        if self.is_mock:
            # Simulated inference for Windows/Host validation
            time.sleep(0.045)
            if self.model_type == "classification":
                return {
                    "result": {
                        "classification": {
                            "PCBA": 0.985,
                            "PCB": 0.010,
                            "Empty": 0.005
                        }
                    }
                }
            elif "big" in self._model_path.lower():
                mock_boxes = [
                    {"label": "SA", "value": 0.96, "x": 190, "y": 140, "width": 80, "height": 80},
                    {"label": "UA", "value": 0.94, "x": 380, "y": 140, "width": 90, "height": 90},
                    {"label": "C1A", "value": 0.92, "x": 140, "y": 370, "width": 70, "height": 70},
                    {"label": "IA", "value": 0.95, "x": 270, "y": 370, "width": 85, "height": 85},
                    {"label": "PA", "value": 0.91, "x": 370, "y": 420, "width": 75, "height": 75},
                    {"label": "C2A", "value": 0.93, "x": 450, "y": 370, "width": 70, "height": 70},
                ]
                return {"result": {"bounding_boxes": mock_boxes}}
            elif "small" in self._model_path.lower():
                mock_small = [
                    {"label": "C1A", "value": 0.90, "x": 180, "y": 250, "width": 25, "height": 25},
                    {"label": "C2A", "value": 0.88, "x": 210, "y": 250, "width": 25, "height": 25},
                    {"label": "C3A", "value": 0.91, "x": 240, "y": 250, "width": 25, "height": 25},
                    {"label": "C4A", "value": 0.89, "x": 270, "y": 250, "width": 25, "height": 25},
                    {"label": "C5A", "value": 0.93, "x": 300, "y": 250, "width": 25, "height": 25},
                    {"label": "C6A", "value": 0.87, "x": 330, "y": 250, "width": 25, "height": 25},
                    {"label": "C7A", "value": 0.92, "x": 360, "y": 250, "width": 25, "height": 25},
                    {"label": "L1A", "value": 0.94, "x": 200, "y": 320, "width": 30, "height": 30},
                    {"label": "L2A", "value": 0.91, "x": 240, "y": 320, "width": 30, "height": 30},
                    {"label": "R1A", "value": 0.89, "x": 280, "y": 320, "width": 25, "height": 25},
                    {"label": "R3A", "value": 0.95, "x": 310, "y": 320, "width": 25, "height": 25},
                    {"label": "R4A", "value": 0.92, "x": 340, "y": 320, "width": 25, "height": 25},
                    {"label": "R5A", "value": 0.90, "x": 370, "y": 320, "width": 25, "height": 25},
                ]
                return {"result": {"bounding_boxes": mock_small}}
            elif "pcb" in self._model_path.lower():
                return {"result": {"bounding_boxes": []}}
            return {"result": {}}

        if self._input_shm is not None:
            n_elements = min(len(data), self._input_shm["elements"])
            self._input_shm["array"][:n_elements] = data[:n_elements]
            msg = {"classify_shm": {"elements": n_elements}}
        else:
            data_list = data.tolist() if isinstance(data, np.ndarray) else data
            msg = {"classify": data_list}

        return self.send_msg(msg)

    def send_msg(self, msg):
        if not self._client:
            raise RuntimeError("NativeEIMRunner is not initialized")

        self._ix += 1
        msg["id"] = self._ix
        self._client.sendall(json.dumps(msg).encode("utf-8"))

        raw = b""
        while True:
            chunk = self._client.recv(8192)
            if not chunk:
                break
            if chunk[-1] == 0:
                raw += chunk[:-1]
                break
            raw += chunk

        raw_text = raw.decode("utf-8", errors="ignore").strip().rstrip("\x00")
        s_idx = raw_text.find("{")
        e_idx = raw_text.rfind("}")

        if s_idx == -1 or e_idx == -1 or e_idx <= s_idx:
            raise RuntimeError("Invalid JSON payload from Edge Impulse .eim")

        try:
            resp = json.loads(raw_text[s_idx:e_idx + 1])
        except Exception as e:
            raise RuntimeError(f"Corrupt JSON payload from .eim: {e}")

        if not resp.get("success", False):
            raise RuntimeError(resp.get("error", "Unknown .eim error"))

        resp.pop("id", None)
        resp.pop("success", None)
        return resp

    def stop(self):
        if self._input_shm is not None:
            try:
                self._input_shm["shm"].close()
            except Exception:
                pass
            self._input_shm = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        if self._proc:
            try:
                self._proc.terminate()
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

        if self._tempdir and os.path.exists(self._tempdir):
            try:
                shutil.rmtree(self._tempdir)
            except Exception:
                pass
            self._tempdir = None

    def __del__(self):
        self.stop()


# ── MULTI-STAGE EDGE IMPULSE VISION INSPECTION ENGINE ────────────────────────
class EIMVisionInspector:
    """
    Dedicated Multi-Stage Inspection Engine running exclusively on Edge Impulse (.eim) binaries.
      Stage 1: Slot Occupancy Classification ('Empty', 'PCB', 'PCBA')
      Stage 2A: Major Electronic Components Inspection (S, U, C1, I, P, C2)
      Stage 2B: Miniature Passives & LEDs Inspection (C1-C7, L1-L2, R1, R3-R5)
      Stage 3: Bare Printed Circuit Board Defect Inspection (Issue)
    """
    def __init__(self):
        self.engine_name = "Edge Impulse (.eim)"

        print("\n  =======================================================")
        print("  Initializing Pure Edge Impulse (.eim) Inspection Engine")
        print("  Model Configuration: Unquantized Float32, Fit Long Axis")
        print("  =======================================================")

        # 1. Slot Occupancy Runner
        self.slot_runner = NativeEIMRunner(str(SLOT_MODEL_P))
        self.slot_info = self.slot_runner.init()
        print(f"  [OK] Stage 1: Slot Occupancy Impulse ready ({SLOT_MODEL_P.name})")

        # 2. Big Components Runner
        self.big_runner = NativeEIMRunner(str(BIG_MODEL_P))
        self.big_info = self.big_runner.init()
        print(f"  [OK] Stage 2A: Big Components Impulse ready ({BIG_MODEL_P.name})")

        # 3. Small Components Runner
        self.small_runner = NativeEIMRunner(str(SMALL_MODEL_P))
        self.small_info = self.small_runner.init()
        print(f"  [OK] Stage 2B: Small Components Impulse ready ({SMALL_MODEL_P.name})")

        # 4. Bare PCB Defect Runner
        self.pcb_runner = NativeEIMRunner(str(PCB_MODEL_P))
        self.pcb_info = self.pcb_runner.init()
        print(f"  [OK] Stage 3: Bare PCB Defect Impulse ready ({PCB_MODEL_P.name})")

        print("  All 4 Edge Impulse (.eim) models successfully loaded!\n")

    def classify_slot(self, frame_bgr):
        """Classifies slot fixture state: 'Empty', 'PCB', or 'PCBA'."""
        try:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            features, _, _ = self.slot_runner.get_features_from_image(frame_rgb)
            res = self.slot_runner.classify(features)
            result = res.get("result", {})

            # Classification impulse format
            if "classification" in result:
                cls_dict = result["classification"]
                if cls_dict:
                    top1 = max(cls_dict, key=cls_dict.get)
                    conf = float(cls_dict[top1])
                    clean_label = {"empty": "Empty", "pcb": "PCB", "pcba": "PCBA"}.get(top1.strip().lower(), top1)
                    return clean_label, conf

            # Object detection fallback format
            elif "bounding_boxes" in result:
                boxes = result["bounding_boxes"]
                if not boxes:
                    return "Empty", 0.90
                top_b = max(boxes, key=lambda b: b.get("value", 0.0))
                lbl = top_b.get("label", "Unknown")
                conf = float(top_b.get("value", 0.0))
                clean_label = {"empty": "Empty", "pcb": "PCB", "pcba": "PCBA"}.get(lbl.strip().lower(), lbl)
                return clean_label, conf

        except Exception as e:
            print(f"[EIM Warning] Slot classification error: {e}")
        return "Unknown", 0.0

    def _run_detection_runner(self, runner, features, meta, conf_thresh, class_filter=None):
        """Runs inference on a runner and unprojects bounding boxes from fit-longest canvas back to camera space."""
        try:
            res = runner.classify(features)
        except Exception as e:
            print(f"[EIM Warning] Inference error on {runner._model_path}: {e}")
            return []

        dets = []
        result = res.get("result", {})
        boxes = result.get("bounding_boxes", [])
        if not boxes:
            return []

        scale = meta.get("scale", 1.0)
        left_pad = meta.get("left_pad", 0)
        top_pad = meta.get("top_pad", 0)
        orig_w = meta.get("orig_w", 1280)
        orig_h = meta.get("orig_h", 720)

        for bb in boxes:
            score = float(bb.get("value", 0.0))
            if score < conf_thresh:
                continue

            lbl = str(bb.get("label", "")).strip()
            if class_filter:
                match = next((c for c in class_filter if c.upper() == lbl.upper()), None)
                if not match:
                    continue
                lbl = match

            bx = float(bb.get("x", 0))
            by = float(bb.get("y", 0))
            bw = float(bb.get("width", 0))
            bh = float(bb.get("height", 0))

            # Unproject from fit-longest canvas to full original frame coordinates
            x1 = int(round((bx - left_pad) / scale))
            y1 = int(round((by - top_pad) / scale))
            x2 = int(round((bx + bw - left_pad) / scale))
            y2 = int(round((by + bh - top_pad) / scale))

            x1 = max(0, min(orig_w - 1, x1))
            y1 = max(0, min(orig_h - 1, y1))
            x2 = max(0, min(orig_w - 1, x2))
            y2 = max(0, min(orig_h - 1, y2))

            dets.append({
                "label": lbl,
                "conf": score,
                "bbox": [x1, y1, x2, y2],
                "cx": (x1 + x2) / 2.0,
                "cy": (y1 + y2) / 2.0,
            })
        return dets

    def detect_pcba_components(self, frame_bgr, conf):
        """Parallel dual-model inspection for PCBA: Executes Big & Small .eim processes concurrently."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        features, _, meta = self.big_runner.get_features_from_image(frame_rgb)

        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_big = executor.submit(self._run_detection_runner, self.big_runner, features, meta, conf, BIG_CLASSES)
            fut_small = executor.submit(self._run_detection_runner, self.small_runner, features, meta, conf, SMALL_CLASSES)
            big_dets = fut_big.result()
            small_dets = fut_small.result()
        t_ms = (time.time() - t0) * 1000

        return big_dets, small_dets, t_ms, t_ms

    def detect_bare_pcb_defects(self, frame_bgr, conf=0.60):
        """Runs bare PCB defect detection impulse."""
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        features, _, meta = self.pcb_runner.get_features_from_image(frame_rgb)
        return self._run_detection_runner(self.pcb_runner, features, meta, conf, PCB_CLASSES)

    def close(self):
        for r in [self.slot_runner, self.big_runner, self.small_runner, self.pcb_runner]:
            if r is not None:
                try:
                    r.stop()
                except Exception:
                    pass


# ── INSPECTION ORCHESTRATOR & MULTI-SLOT MANAGER ─────────────────────────────
class MultiSlotInspectionSystem:
    def __init__(self, source="0", serial_port="auto", conf=0.20, pcb_conf=0.60, use_roi=True):
        self.source = source
        self.conf = conf
        self.pcb_conf = pcb_conf
        self.use_roi = use_roi

        self.hw = ArduinoHardwareController(port=serial_port)
        self.inspector = EIMVisionInspector()

        self.mode = "AUTO"  # "AUTO" or "MANUAL"
        self.active_slot = 1
        self.inspecting_slot = None
        self.is_moving = False
        self.last_manual_time = time.time()
        self.running = False

        self.lock = threading.Lock()
        self.cam_lock = threading.Lock()
        self.latest_frame = None

        self.cap = None
        try:
            self.cap = self._init_camera()

            # Standby placeholder frame
            init_frame = np.full((720, 1280, 3), (248, 250, 252), dtype=np.uint8)
            cv2.putText(init_frame, "EDGE IMPULSE VISION INSPECTION", (300, 330), FONT, 1.0, (15, 23, 42), 2, LINE_AA)
            cv2.putText(init_frame, "System Initialized. Click a Slot or Start Auto Loop.", (330, 380), FONTS, 0.65, (100, 116, 139), 1, LINE_AA)
            _, init_buf = cv2.imencode(".jpg", init_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            init_jpeg = init_buf.tobytes()

            # Slot state storage (Slots 1 to 6)
            self.slots = {}
            self.slot_photos = {}
            for s in range(1, 7):
                self.slots[s] = {
                    "slot_id": s,
                    "pulse": SERVO_POSITIONS[s - 1],
                    "verdict": "READY",
                    "verdict_type": "WARN",
                    "slot_type": "Ready",
                    "slot_confidence": 0.0,
                    "big_components": {p: {"status": "UNKNOWN", "conf": 0.0} for p, _ in BIG_COMPONENTS},
                    "small_components": {p: {"status": "UNKNOWN", "conf": 0.0} for p, _ in SMALL_COMPONENTS},
                    "pcb_issues": 0,
                    "pcb_confs": [],
                    "latency_ms": 0.0,
                    "timestamp": None,
                }
                self.slot_photos[s] = init_jpeg
        except Exception:
            self.stop()
            raise

    def start(self):
        self.running = True
        t_cam = threading.Thread(target=self._camera_worker, daemon=True)
        t_cam.start()
        t_orch = threading.Thread(target=self._orchestrator_loop, daemon=True)
        t_orch.start()

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        if hasattr(self.inspector, "close"):
            try:
                self.inspector.close()
            except Exception:
                pass
        self.hw.close()

    def _init_camera(self):
        if not hasattr(cv2, "VideoCapture"):
            print("  [Camera Warning] OpenCV VideoCapture is not available in current environment.")
            return None

        cap = None
        try:
            if self.source.isdigit():
                cam_idx = int(self.source)
                if sys.platform.startswith("linux"):
                    backend = getattr(cv2, "CAP_V4L2", 200)
                    cap = cv2.VideoCapture(cam_idx, backend)
                    if not cap.isOpened():
                        cap = cv2.VideoCapture(cam_idx)
                else:
                    cap = cv2.VideoCapture(cam_idx)
            else:
                cap = cv2.VideoCapture(self.source)

            if cap and cap.isOpened():
                cap.set(getattr(cv2, "CAP_PROP_FRAME_WIDTH", 3), 1280)
                cap.set(getattr(cv2, "CAP_PROP_FRAME_HEIGHT", 4), 720)
                print(f"  [Camera] Live camera feed active on source '{self.source}' (1280x720)")
            else:
                print(f"  [Camera Warning] Unable to open camera source '{self.source}'. Running in standby mode.")
        except Exception as e:
            print(f"  [Camera Warning] Camera init exception on '{self.source}': {e}")
            cap = None

        return cap

    def _camera_worker(self):
        """Continuously drains frames from camera driver into latest_frame to eliminate queue latency."""
        while self.running:
            if self.cap and self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret and frame is not None:
                        with self.cam_lock:
                            self.latest_frame = frame
                except Exception:
                    pass
            time.sleep(0.005)

    def _capture_photo(self):
        """Captures real-time fresh frame from camera worker."""
        with self.cam_lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()

        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame.copy()

        img = np.full((720, 1280, 3), (248, 250, 252), dtype=np.uint8)
        cv2.putText(img, f"STANDBY - SLOT {self.active_slot}", (120, 360), FONT, 1.0, (100, 116, 139), 2, LINE_AA)
        return img

    def inspect_slot(self, slot_id):
        """Executes full photo-level inspection for specified slot."""
        with self.lock:
            self.inspecting_slot = slot_id
            self.is_moving = True

        # 1. Rotate servo to slot (includes distance-adaptive travel time)
        self.hw.move_to_slot(slot_id)

        # 2. Stabilization damping pause so turntable comes to a dead stop
        time.sleep(0.22)

        # 3. Capture fresh photo
        photo = self._capture_photo()
        self.is_moving = False
        t0 = time.time()

        # 4. Stage 1: Slot Occupancy
        t_slot0 = time.time()
        slot_label, slot_conf = self.inspector.classify_slot(photo)
        t_slot_ms = (time.time() - t_slot0) * 1000

        big_status   = {p: {"status": "UNKNOWN", "conf": 0.0} for p, _ in BIG_COMPONENTS}
        small_status = {p: {"status": "UNKNOWN", "conf": 0.0} for p, _ in SMALL_COMPONENTS}
        pcb_confs    = []
        t_big_ms = 0.0
        t_small_ms = 0.0
        t_pcb_ms = 0.0

        h_f, w_f = photo.shape[:2]
        if self.use_roi:
            rx1 = int(w_f * 0.03)
            ry1 = int(h_f * 0.03)
            rx2 = int(w_f * 0.97)
            ry2 = int(h_f * 0.97)
        else:
            rx1, ry1, rx2, ry2 = 0, 0, w_f, h_f

        def in_roi(b):
            if not self.use_roi:
                return True
            return (rx1 <= b["cx"] <= rx2) and (ry1 <= b["cy"] <= ry2)

        # 5. Conditional Inspection based on Slot Fixture State
        if slot_label == "PCBA":
            big_dets_all, sm_dets_all, t_big_ms, t_small_ms = self.inspector.detect_pcba_components(photo, self.conf)
            big_dets = [b for b in big_dets_all if in_roi(b)]
            sm_dets  = [b for b in sm_dets_all if in_roi(b)]

            # Extract Big component status (Pick candidate with highest confidence)
            big_candidates = {p: [] for p, _ in BIG_COMPONENTS}
            for b in big_dets:
                lbl = b["label"]
                for prefix, _ in BIG_COMPONENTS:
                    if lbl.startswith(prefix):
                        suffix = lbl[len(prefix):]
                        if suffix in ("A", "N"):
                            big_candidates[prefix].append((suffix, b["conf"]))
                            break

            for prefix, _ in BIG_COMPONENTS:
                cands = big_candidates[prefix]
                if cands:
                    best_suffix, best_conf = max(cands, key=lambda x: x[1])
                    if best_suffix == "A":
                        big_status[prefix] = {"status": "PRESENT", "conf": round(best_conf, 3)}
                    else:
                        big_status[prefix] = {"status": "MISSING", "conf": round(best_conf, 3)}

            # Extract Small component status (Pick candidate with highest confidence)
            sm_candidates = {p: [] for p, _ in SMALL_COMPONENTS}
            for b in sm_dets:
                lbl = b["label"]
                for prefix, _ in SMALL_COMPONENTS:
                    if lbl.startswith(prefix):
                        suffix = lbl[len(prefix):]
                        if suffix in ("A", "N"):
                            sm_candidates[prefix].append((suffix, b["conf"]))
                            break

            for prefix, _ in SMALL_COMPONENTS:
                cands = sm_candidates[prefix]
                if cands:
                    best_suffix, best_conf = max(cands, key=lambda x: x[1])
                    if best_suffix == "A":
                        small_status[prefix] = {"status": "PRESENT", "conf": round(best_conf, 3)}
                    else:
                        small_status[prefix] = {"status": "MISSING", "conf": round(best_conf, 3)}

            # Draw bounding boxes on photo
            for b in big_dets + sm_dets:
                x1, y1, x2, y2 = b["bbox"]
                is_available = b["label"].endswith("A")
                col = COLOR_AVAILABLE if is_available else COLOR_MISSING
                cv2.rectangle(photo, (x1, y1), (x2, y2), col, 2)
                txt = f"{b['label']} {b['conf']*100:.0f}%"
                cv2.putText(photo, txt, (x1, max(y1 - 6, 16)), FONTS, 0.42, col, 1, LINE_AA)

            # Determine verdict
            all_vals = list(big_status.values()) + list(small_status.values())
            if any(v["status"] == "MISSING" for v in all_vals):
                verdict, v_type, led_cmd = "FAIL", "FAIL", "FAIL"
            elif all(v["status"] == "PRESENT" for v in all_vals):
                verdict, v_type, led_cmd = "PASS", "PASS", "PASS"
            else:
                verdict, v_type, led_cmd = "PARTIAL SCAN", "WARN", "FAIL"

        elif slot_label == "PCB":
            t_p0 = time.time()
            pcb_dets = [b for b in self.inspector.detect_bare_pcb_defects(photo, self.pcb_conf) if in_roi(b)]
            t_pcb_ms = (time.time() - t_p0) * 1000
            for b in pcb_dets:
                pcb_confs.append(b["conf"])
                x1, y1, x2, y2 = b["bbox"]
                cv2.rectangle(photo, (x1, y1), (x2, y2), COLOR_MISSING, 2)
                txt = f"Issue {b['conf']*100:.0f}%"
                cv2.putText(photo, txt, (x1, max(y1 - 6, 16)), FONTS, 0.42, COLOR_MISSING, 1, LINE_AA)

            if len(pcb_confs) == 0:
                verdict, v_type, led_cmd = "PASS", "PASS", "PASS"
            else:
                verdict, v_type, led_cmd = "FAIL", "FAIL", "FAIL"

        else:
            verdict, v_type, led_cmd = "EMPTY", "WARN", "FAIL"
            cv2.putText(photo, f"SLOT {slot_id}: EMPTY (NO BOARD)", (60, 80), FONT, 0.9, COLOR_WARN_AMBER, 2, LINE_AA)

        # 6. Set Hardware LED
        self.hw.set_led(led_cmd)

        # Draw Center Reticle if ROI filtering active
        if self.use_roi:
            blen, col = 26, COLOR_ROI_CYAN
            cv2.line(photo, (rx1, ry1), (rx1 + blen, ry1), col, 2)
            cv2.line(photo, (rx1, ry1), (rx1, ry1 + blen), col, 2)
            cv2.line(photo, (rx2, ry1), (rx2 - blen, ry1), col, 2)
            cv2.line(photo, (rx2, ry1), (rx2, ry1 + blen), col, 2)
            cv2.line(photo, (rx1, ry2), (rx1 + blen, ry2), col, 2)
            cv2.line(photo, (rx1, ry2), (rx1, ry2 - blen), col, 2)
            cv2.line(photo, (rx2, ry2), (rx2 - blen, ry2), col, 2)
            cv2.line(photo, (rx2, ry2), (rx2, ry2 - blen), col, 2)

        # Watermark banner
        v_col = COLOR_AVAILABLE if verdict == "PASS" else (COLOR_MISSING if verdict == "FAIL" else COLOR_WARN_AMBER)
        cv2.rectangle(photo, (20, 20), (370, 72), (255, 255, 255), -1)
        cv2.rectangle(photo, (20, 20), (370, 72), v_col, 2)
        cv2.putText(photo, f"SLOT {slot_id}: {verdict}", (35, 56), FONT, 0.85, v_col, 2, LINE_AA)

        latency = (time.time() - t0) * 1000

        # Encode JPEG for web transmission
        _, jpeg = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 75])

        with self.lock:
            self.slots[slot_id] = {
                "slot_id": slot_id,
                "pulse": SERVO_POSITIONS[slot_id - 1],
                "verdict": verdict,
                "verdict_type": v_type,
                "slot_type": slot_label,
                "slot_confidence": round(slot_conf, 3),
                "big_components": big_status,
                "small_components": small_status,
                "pcb_issues": len(pcb_confs),
                "pcb_confs": [round(c, 2) for c in pcb_confs],
                "latency_ms": round(latency, 1),
                "stage_latencies": {
                    "slot_occupancy_ms": round(t_slot_ms, 1),
                    "big_components_ms": round(t_big_ms, 1),
                    "small_components_ms": round(t_small_ms, 1),
                    "pcb_defect_ms": round(t_pcb_ms, 1),
                },
                "timestamp": time.strftime("%H:%M:%S"),
            }
            self.slot_photos[slot_id] = jpeg.tobytes()
            self.active_slot = slot_id
            self.inspecting_slot = None

        stage_breakdown = f"[Slot: {t_slot_ms:.0f}ms | Parallel PCBA AI: {t_big_ms:.0f}ms]" if slot_label == "PCBA" else (f"[Slot: {t_slot_ms:.0f}ms | PCB: {t_pcb_ms:.0f}ms]" if slot_label == "PCB" else f"[Slot: {t_slot_ms:.0f}ms]")
        print(f"  [Slot {slot_id}] Status: {verdict} ({slot_label} {slot_conf*100:.0f}%) in {latency:.0f}ms {stage_breakdown} | LED: {led_cmd}")
        return self.slots[slot_id]

    def _orchestrator_loop(self):
        """Background loop handling Auto Loop and Manual Idle watchdog."""
        print("[Orchestrator] Multi-slot worker loop running...")
        slot_pointer = 1

        while self.running:
            if self.mode == "AUTO":
                self.inspect_slot(slot_pointer)
                time.sleep(1.8)
                slot_pointer = (slot_pointer % 6) + 1
            else:
                idle_sec = time.time() - self.last_manual_time
                if idle_sec >= AUTO_IDLE_TIMEOUT:
                    print(f"\n[Watchdog] System idle for {idle_sec:.1f}s. Automatically returning to AUTO LOOP mode.")
                    self.mode = "AUTO"
                    slot_pointer = self.active_slot
                time.sleep(0.2)

    def select_slot_manual(self, slot_id):
        self.mode = "MANUAL"
        self.last_manual_time = time.time()
        return self.inspect_slot(slot_id)

    def get_telemetry(self):
        with self.lock:
            idle_remaining = max(0.0, AUTO_IDLE_TIMEOUT - (time.time() - self.last_manual_time)) if self.mode == "MANUAL" else 0.0
            return {
                "mode": self.mode,
                "engine": getattr(self.inspector, "engine_name", "Edge Impulse (.eim)"),
                "active_slot": self.active_slot,
                "inspecting_slot": self.inspecting_slot,
                "is_moving": self.is_moving,
                "idle_remaining_sec": round(idle_remaining, 1),
                "conf": self.conf,
                "use_roi": self.use_roi,
                "hardware": {
                    "is_connected": self.hw.is_connected,
                    "backend": self.hw.backend,
                    "port": self.hw.port,
                    "baudrate": self.hw.baudrate,
                    "led_color": self.hw.current_led,
                },
                "active_slot_details": self.slots[self.active_slot],
                "all_slots": self.slots,
            }


# ── MODERN INDUSTRIAL WEB DASHBOARD TEMPLATE ─────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BMS Vision Inspection — Pure Edge Impulse AOI Station</title>
  <style>
    :root {
      --bg: #f1f5f9;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --border-dark: #cbd5e1;
      --border-focus: #2563eb;
      --text: #0f172a;
      --text-muted: #475569;
      --text-subtle: #94a3b8;
      
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-subtle: #eff6ff;
      --primary-border: #bfdbfe;

      --pass: #059669;
      --pass-bg: #ecfdf5;
      --pass-border: #a7f3d0;

      --fail: #dc2626;
      --fail-bg: #fef2f2;
      --fail-border: #fecaca;

      --warn: #d97706;
      --warn-bg: #fffbeb;
      --warn-border: #fde68a;

      --radius: 8px;
      --radius-sm: 6px;
      --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
      --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.08), 0 1px 2px -1px rgba(0, 0, 0, 0.04);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      height: 100vh;
      width: 100vw;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      font-size: 13px;
      line-height: 1.4;
      -webkit-font-smoothing: antialiased;
    }

    /* ── HEADER ────────────────────────────────────────────────── */
    header {
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 8px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
      height: 48px;
      box-shadow: var(--shadow-sm);
      z-index: 20;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-emblem {
      width: 28px;
      height: 28px;
      border-radius: var(--radius-sm);
      background: #0f172a;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-weight: 800;
      font-size: 13px;
      letter-spacing: -0.5px;
    }
    .brand-title {
      font-size: 15px;
      font-weight: 700;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .station-id {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      background: #f1f5f9;
      padding: 2px 7px;
      border-radius: 4px;
      border: 1px solid var(--border);
    }
    .brand-divider {
      width: 1px;
      height: 22px;
      background: var(--border-dark);
      margin: 0 2px;
    }
    .partner-logos {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .partner-logo {
      height: 26px;
      width: auto;
      object-fit: contain;
      border-radius: 4px;
      background: #ffffff;
      padding: 2px 5px;
      border: 1px solid var(--border);
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
      transition: transform 0.15s ease;
      cursor: pointer;
    }
    .partner-logo:hover {
      transform: scale(1.05);
    }
    .logo-arduino { height: 26px; }
    .logo-ei { height: 24px; }

    .header-center {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .mode-switch-group {
      display: inline-flex;
      background: #f1f5f9;
      padding: 3px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border);
    }
    .mode-btn {
      padding: 4px 14px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 600;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .mode-btn.active {
      background: #ffffff;
      color: var(--text);
      box-shadow: var(--shadow-sm);
    }
    .idle-pill {
      font-size: 11px;
      color: var(--warn);
      font-weight: 600;
      background: var(--warn-bg);
      border: 1px solid var(--warn-border);
      padding: 3px 8px;
      border-radius: 4px;
      display: none;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .ctrl-pill {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--text-muted);
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
    }
    .ctrl-pill input[type="range"] {
      width: 65px;
      cursor: pointer;
      accent-color: var(--primary);
    }
    .ctrl-pill span.val {
      font-weight: 700;
      color: var(--text);
      min-width: 28px;
    }
    .btn-toggle-roi {
      background: #f8fafc;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 5px 12px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-toggle-roi:hover {
      background: #f1f5f9;
    }
    .hw-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      background: #f8fafc;
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 600;
    }
    .engine-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      color: #1e40af;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }
    .engine-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #2563eb;
      display: inline-block;
    }
    .led-dot {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #94a3b8;
      display: inline-block;
      transition: background 0.2s;
    }
    .led-green  { background: #10b981; }
    .led-red    { background: #ef4444; }
    .led-orange { background: #f97316; }
    .led-amber  { background: #f59e0b; }

    /* ── MAIN WORKSPACE ─────────────────────────────────────────── */
    main {
      flex: 1;
      min-height: 0;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      padding: 10px 14px;
      overflow: hidden;
    }

    /* ── LEFT PANEL (50%): CAMERA & TURNTABLE ──────────────────── */
    .left-panel {
      height: 100%;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
      overflow: hidden;
    }

    .viewport-card {
      width: 100%;
      aspect-ratio: 16 / 9;
      background: #0f172a;
      border: 1.5px solid var(--border-dark);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
      flex-shrink: 0;
    }
    .viewport-display {
      width: 100%;
      height: 100%;
      position: relative;
      overflow: hidden;
      background: #0f172a;
    }
    .viewport-display img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }

    .hud-top-right {
      position: absolute;
      top: 10px;
      right: 10px;
      background: rgba(15, 23, 42, 0.88);
      border: 1px solid rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(8px);
      padding: 5px 12px;
      border-radius: var(--radius-sm);
      color: #94a3b8;
      font-size: 12px;
      font-weight: 600;
      z-index: 10;
    }
    .hud-bottom-bar {
      position: absolute;
      bottom: 10px;
      left: 10px;
      right: 10px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(15, 23, 42, 0.88);
      border: 1px solid rgba(255, 255, 255, 0.18);
      backdrop-filter: blur(8px);
      padding: 6px 14px;
      border-radius: var(--radius-sm);
      color: #e2e8f0;
      font-size: 12px;
      font-weight: 600;
      z-index: 10;
    }
    .hud-tag {
      font-weight: 700;
      color: #ffffff;
    }

    .turntable-card {
      flex: 1;
      min-height: 0;
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 12px 16px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .turntable-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .turntable-title {
      font-size: 14px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-muted);
    }
    .turntable-hint {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-subtle);
    }
    .slot-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      flex: 1;
      align-items: stretch;
      margin: 6px 0;
    }
    .slot-item-btn {
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 6px;
      cursor: pointer;
      display: flex;
      flex-direction: column;
      gap: 6px;
      transition: all 0.15s ease;
      box-shadow: var(--shadow-sm);
    }
    .slot-item-btn:hover {
      background: #f8fafc;
      border-color: #cbd5e1;
      box-shadow: var(--shadow);
    }
    .slot-item-btn.active {
      background: #ffffff;
      border-color: var(--primary);
      box-shadow: 0 0 0 2.5px var(--primary), var(--shadow);
    }
    .slot-thumb-box {
      width: 100%;
      aspect-ratio: 16 / 9;
      background: #0f172a;
      border-radius: 4px;
      overflow: hidden;
      position: relative;
    }
    .slot-thumb-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .slot-thumb-tag {
      position: absolute;
      top: 4px;
      right: 4px;
      font-size: 11px;
      font-weight: 800;
      padding: 2px 7px;
      border-radius: 3px;
      letter-spacing: 0.3px;
      text-transform: uppercase;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
      z-index: 5;
    }
    .slot-card-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 4px;
    }
    .slot-title {
      font-size: 16px;
      font-weight: 900;
      color: var(--text);
    }
    .slot-angle {
      font-size: 13px;
      font-weight: 700;
      color: var(--text-muted);
    }
    .pill-pend { background: #f1f5f9; color: #64748b; }
    .pill-pass { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass-border); }
    .pill-fail { background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }
    .pill-warn { background: var(--warn-bg); color: var(--warn); border: 1px solid var(--warn-border); }
    .pill-move { background: var(--primary-subtle); color: var(--primary); border: 1px solid var(--primary-border); }

    .diag-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-top: 6px;
      border-top: 1px solid #edf2f7;
    }
    .diag-group {
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .diag-label {
      font-size: 13px;
      font-weight: 800;
      color: var(--text-muted);
      text-transform: uppercase;
    }
    .btn-diag {
      background: #f8fafc;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 4px 10px;
      border-radius: 4px;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-diag:hover {
      background: #f1f5f9;
      border-color: #cbd5e1;
    }
    .btn-diag-pass { color: #059669; font-weight: 800; }
    .btn-diag-fail { color: #dc2626; font-weight: 800; }

    /* ── RIGHT PANEL (50%): QC RESULTS ──────────────────────────── */
    .right-panel {
      height: 100%;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
      justify-content: space-between;
      overflow: hidden;
    }

    .card {
      background: var(--card-bg);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 14px 20px;
      box-shadow: var(--shadow-sm);
    }
    .card-title-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .card-title {
      font-size: 15px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--text-muted);
    }
    .card-badge {
      font-size: 15px;
      font-weight: 800;
      color: var(--primary);
    }

    /* 1. Hero Verdict Card */
    .verdict-banner-card {
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 14px 20px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 10px;
      flex-shrink: 0;
    }
    .verdict-banner-card.hero-pass {
      background: var(--pass-bg);
      border-color: var(--pass-border);
    }
    .verdict-banner-card.hero-fail {
      background: var(--fail-bg);
      border-color: var(--fail-border);
    }
    .verdict-banner-card.hero-warn {
      background: var(--warn-bg);
      border-color: var(--warn-border);
    }
    .verdict-main-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .verdict-big-text {
      font-size: 36px;
      font-weight: 900;
      letter-spacing: -0.6px;
    }
    .hero-pass .verdict-big-text { color: var(--pass); }
    .hero-fail .verdict-big-text { color: var(--fail); }
    .hero-warn .verdict-big-text { color: var(--warn); }
    .verdict-subtext {
      font-size: 15px;
      color: var(--text-muted);
      font-weight: 700;
      margin-top: 2px;
    }

    /* Metric KPI Strip */
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      background: rgba(255, 255, 255, 0.95);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: var(--radius-sm);
      padding: 8px 16px;
    }
    .kpi-item {
      display: flex;
      flex-direction: column;
    }
    .kpi-label {
      font-size: 13px;
      color: var(--text-muted);
      text-transform: uppercase;
      font-weight: 800;
    }
    .kpi-value {
      font-size: 22px;
      font-weight: 900;
      color: var(--text);
    }

    /* 2. Major Components Card */
    .card-major {
      flex: 1.1;
      min-height: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .major-comp-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      flex: 1;
      align-items: stretch;
      margin-top: 4px;
    }
    .comp-card {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #f8fafc;
      border: 1.5px solid #edf2f7;
      padding: 12px 20px;
      border-radius: var(--radius-sm);
    }
    .comp-name {
      font-weight: 900;
      color: var(--text);
      font-size: 20px;
    }
    .comp-status-chip {
      font-size: 16px;
      font-weight: 800;
      padding: 6px 16px;
      border-radius: 5px;
      letter-spacing: 0.2px;
    }
    .chip-ok   { background: var(--pass-bg); color: var(--pass); border: 1px solid var(--pass-border); }
    .chip-miss { background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }
    .chip-idle { background: #f1f5f9; color: #64748b; font-weight: 800; }

    /* 3. SMD Passives & LEDs Card */
    .card-passives {
      flex: 1.5;
      min-height: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }
    .passives-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      flex: 1;
      align-items: stretch;
      margin-top: 4px;
    }
    .passive-chip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #f8fafc;
      border: 1.5px solid #edf2f7;
      padding: 8px 14px;
      border-radius: 5px;
    }
    .passive-name {
      font-weight: 900;
      color: var(--text);
      font-size: 17px;
    }

    /* 4. Bare PCB Defect Card */
    .card-pcb {
      flex-shrink: 0;
      padding: 12px 20px;
    }
  </style>
</head>
<body>

  <!-- ── HEADER ────────────────────────────────────────────────── -->
  <header>
    <div class="brand">
      <div class="brand-emblem">AOI</div>
      <div class="brand-title">
        BMS Vision Inspection
        <span class="station-id">STATION 01</span>
      </div>
      <div class="brand-divider"></div>
      <div class="partner-logos" title="Powered by Arduino & Edge Impulse">
        <img src="/api/logo/arduino" alt="Arduino" class="partner-logo logo-arduino" title="Arduino UNO Q" onerror="this.onerror=null;this.src='https://logowik.com/content/uploads/images/arduino5804.jpg'">
        <img src="/api/logo/edgeimpulse" alt="Edge Impulse" class="partner-logo logo-ei" title="Edge Impulse" onerror="this.onerror=null;this.src='https://www.edge-ai-vision.com/wp-content/uploads/2021/05/logo_edgeimpulse_may_2021.png'">
      </div>
    </div>

    <!-- Mode Selector & Watchdog -->
    <div class="header-center">
      <div class="mode-switch-group">
        <button id="btn-mode-auto" class="mode-btn active" onclick="setMode('AUTO')">Auto Loop</button>
        <button id="btn-mode-manual" class="mode-btn" onclick="setMode('MANUAL')">Manual</button>
      </div>
      <div id="idle-pill" class="idle-pill">Auto in 10s</div>
    </div>

    <!-- Controls -->
    <div class="header-actions">
      <!-- Confidence Slider -->
      <div class="ctrl-pill" title="AI Confidence Cutoff">
        <span>Conf:</span>
        <input type="range" id="conf-slider" min="10" max="50" value="20" oninput="onSensitivityChange(this.value)">
        <span id="conf-val" class="val">20%</span>
      </div>

      <!-- Framing Toggle -->
      <button id="roi-btn" class="btn-toggle-roi" onclick="toggleRoi()">Center Reticle</button>

      <!-- Engine Badge (Pure Edge Impulse .eim) -->
      <div class="engine-badge" id="engine-badge" title="Active Vision Inference Engine">
        <span class="engine-dot"></span>
        <span id="engine-label">Edge Impulse (.eim)</span>
      </div>

      <!-- Hardware Link Status -->
      <div class="hw-badge">
        <span id="led-dot" class="led-dot led-green"></span>
        <span id="hw-status-label">UNO Q Bridge</span>
      </div>
    </div>
  </header>

  <!-- ── MAIN WORKSPACE ─────────────────────────────────────────── -->
  <main>
    <!-- Left Column (50%): Camera Viewport & Turntable Controller -->
    <div class="left-panel">
      <!-- 16:9 Viewport -->
      <div class="viewport-card">
        <div class="viewport-display">
          <div class="hud-top-right">1280×720 · LIVE AOI · .EIM</div>
          <img id="slot-img" src="/api/slot_photo/1" alt="Inspection Frame" onerror="onPhotoError()">
          <div class="hud-bottom-bar">
            <span id="hud-slot-tag" class="hud-tag">Slot 1 · Standby</span>
            <span id="hud-pulse-pos">Turntable: 500 µs (Slot 1 · 0°)</span>
            <span id="hud-latency-pill">Latency: -- ms</span>
          </div>
        </div>
      </div>

      <!-- 6-Slot Turntable Controller with Thumbnails -->
      <div class="turntable-card">
        <div class="turntable-header">
          <span class="turntable-title">6-Slot Rotary Turntable Controller</span>
          <span class="turntable-hint">Click any slot to index & inspect</span>
        </div>
        <div class="slot-grid">
          <button id="btn-slot-1" class="slot-item-btn active" onclick="selectSlot(1)">
            <div class="slot-thumb-box">
              <img id="thumb-img-1" src="/api/slot_photo/1" class="slot-thumb-img" alt="Slot 1">
              <span id="tag-slot-1" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 1</span>
              <span class="slot-angle">0°</span>
            </div>
          </button>
          <button id="btn-slot-2" class="slot-item-btn" onclick="selectSlot(2)">
            <div class="slot-thumb-box">
              <img id="thumb-img-2" src="/api/slot_photo/2" class="slot-thumb-img" alt="Slot 2">
              <span id="tag-slot-2" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 2</span>
              <span class="slot-angle">60°</span>
            </div>
          </button>
          <button id="btn-slot-3" class="slot-item-btn" onclick="selectSlot(3)">
            <div class="slot-thumb-box">
              <img id="thumb-img-3" src="/api/slot_photo/3" class="slot-thumb-img" alt="Slot 3">
              <span id="tag-slot-3" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 3</span>
              <span class="slot-angle">120°</span>
            </div>
          </button>
          <button id="btn-slot-4" class="slot-item-btn" onclick="selectSlot(4)">
            <div class="slot-thumb-box">
              <img id="thumb-img-4" src="/api/slot_photo/4" class="slot-thumb-img" alt="Slot 4">
              <span id="tag-slot-4" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 4</span>
              <span class="slot-angle">180°</span>
            </div>
          </button>
          <button id="btn-slot-5" class="slot-item-btn" onclick="selectSlot(5)">
            <div class="slot-thumb-box">
              <img id="thumb-img-5" src="/api/slot_photo/5" class="slot-thumb-img" alt="Slot 5">
              <span id="tag-slot-5" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 5</span>
              <span class="slot-angle">240°</span>
            </div>
          </button>
          <button id="btn-slot-6" class="slot-item-btn" onclick="selectSlot(6)">
            <div class="slot-thumb-box">
              <img id="thumb-img-6" src="/api/slot_photo/6" class="slot-thumb-img" alt="Slot 6">
              <span id="tag-slot-6" class="slot-thumb-tag pill-pend">READY</span>
            </div>
            <div class="slot-card-bottom">
              <span class="slot-title">Slot 6</span>
              <span class="slot-angle">300°</span>
            </div>
          </button>
        </div>

        <!-- Hardware Diagnostics -->
        <div class="diag-toolbar">
          <div class="diag-group">
            <span class="diag-label">Servo:</span>
            <button class="btn-diag" onclick="testServo(1)">1</button>
            <button class="btn-diag" onclick="testServo(2)">2</button>
            <button class="btn-diag" onclick="testServo(3)">3</button>
            <button class="btn-diag" onclick="testServo(4)">4</button>
            <button class="btn-diag" onclick="testServo(5)">5</button>
            <button class="btn-diag" onclick="testServo(6)">6</button>
          </div>
          <div class="diag-group">
            <span class="diag-label">LED:</span>
            <button class="btn-diag btn-diag-pass" onclick="testLed('PASS')">Pass</button>
            <button class="btn-diag btn-diag-fail" onclick="testLed('FAIL')">Fail</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Column (50%): High-Visibility QC Results -->
    <div class="right-panel">
      <!-- 1. Verdict Hero Banner -->
      <div id="verdict-banner-card" class="verdict-banner-card hero-warn">
        <div class="verdict-main-row">
          <div>
            <div id="verdict-big-text" class="verdict-big-text">SLOT 1: READY</div>
            <div id="verdict-subtext" class="verdict-subtext">Waiting for inspection trigger</div>
          </div>
          <div id="hero-badge-pill" class="slot-pill pill-warn" style="font-size: 18px; padding: 7px 24px; border-radius: 6px; font-weight: 800;">READY</div>
        </div>

        <div class="kpi-strip">
          <div class="kpi-item">
            <span class="kpi-label">Board Profile</span>
            <span id="kpi-board-type" class="kpi-value">Detecting...</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">Confidence</span>
            <span id="kpi-board-conf" class="kpi-value">--%</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">AI Latency</span>
            <span id="kpi-latency" class="kpi-value">-- ms</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-label">Surface State</span>
            <span id="kpi-surface" class="kpi-value">Clean (0)</span>
          </div>
        </div>
      </div>

      <!-- 2. Major Components Matrix (6 Locations) -->
      <div class="card card-major">
        <div class="card-title-row">
          <span class="card-title">Major Components (6 Required)</span>
          <span id="big-summary" class="card-badge">0/6 Verified</span>
        </div>
        <div id="big-grid" class="major-comp-grid"></div>
      </div>

      <!-- 3. SMD Passives & LEDs Matrix (13 Locations) -->
      <div class="card card-passives">
        <div class="card-title-row">
          <span class="card-title">SMD Passives & LEDs (13 Required)</span>
          <span id="sm-summary" class="card-badge">0/13 Verified</span>
        </div>
        <div id="small-grid" class="passives-grid"></div>
      </div>

      <!-- 4. Bare PCB Defect Inspection -->
      <div class="card card-pcb">
        <div class="card-title-row">
          <span class="card-title">Bare PCB Defect Analysis (.EIM)</span>
          <span class="card-badge">&ge; 60% Cutoff</span>
        </div>
        <div id="pcb-status-text" style="font-size: 18px; font-weight: 800; color: var(--text);">0 Issues Detected (Clean Surface)</div>
      </div>
    </div>
  </main>

  <script>
    let activeSlot = 1;
    let lastTimestamp = "";
    let currentUseRoi = true;
    const PULSES = [500, 930, 1360, 1790, 2220, 2650];
    const ANGLES = [0, 60, 120, 180, 240, 300];

    async function setMode(mode) {
      await fetch('/api/toggle_mode', { method: 'POST' });
      updateTelemetry();
    }

    async function selectSlot(slotId) {
      document.getElementById('hud-slot-tag').innerText = `Rotating to Slot ${slotId}...`;
      const res = await fetch(`/api/select_slot/${slotId}`, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        activeSlot = slotId;
        const now = Date.now();
        document.getElementById('slot-img').src = `/api/slot_photo/${slotId}?t=` + now;
        const thumb = document.getElementById(`thumb-img-${slotId}`);
        if (thumb) thumb.src = `/api/slot_photo/${slotId}?t=` + now;
        document.getElementById('hud-slot-tag').innerText = `Slot ${slotId} · Inspected`;
      }
      updateTelemetry();
    }

    async function testServo(slotId) {
      await fetch(`/api/hardware/test_servo/${slotId}`, { method: 'POST' });
    }

    async function testLed(color) {
      await fetch(`/api/hardware/test_led/${color}`, { method: 'POST' });
      const ledDot = document.getElementById('led-dot');
      ledDot.className = 'led-dot led-' + color.toLowerCase();
    }

    async function onSensitivityChange(val) {
      document.getElementById('conf-val').innerText = val + '%';
      await fetch('/api/config/sensitivity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conf: val / 100.0, use_roi: currentUseRoi })
      });
    }

    async function toggleRoi() {
      currentUseRoi = !currentUseRoi;
      document.getElementById('roi-btn').innerText = currentUseRoi ? 'Center Reticle' : 'Full Fixture';
      const confVal = parseInt(document.getElementById('conf-slider').value) / 100.0;
      await fetch('/api/config/sensitivity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conf: confVal, use_roi: currentUseRoi })
      });
    }

    function onPhotoError() {
      setTimeout(() => {
        const img = document.getElementById('slot-img');
        img.src = `/api/slot_photo/${activeSlot}?t=` + Date.now();
      }, 500);
    }

    async function updateTelemetry() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // 1. Mode Buttons & Watchdog
        const btnAuto = document.getElementById('btn-mode-auto');
        const btnManual = document.getElementById('btn-mode-manual');
        const idlePill = document.getElementById('idle-pill');

        if (data.mode === 'AUTO') {
          btnAuto.classList.add('active');
          btnManual.classList.remove('active');
          idlePill.style.display = 'none';
        } else {
          btnAuto.classList.remove('active');
          btnManual.classList.add('active');
          idlePill.style.display = 'inline-block';
          idlePill.innerText = `Auto in ${data.idle_remaining_sec}s`;
        }

        // 2. Hardware Status & LED
        const ledDot = document.getElementById('led-dot');
        const hwLabel = document.getElementById('hw-status-label');
        ledDot.className = 'led-dot led-' + data.hardware.led_color.toLowerCase();

        if (data.hardware.is_connected) {
          hwLabel.innerText = data.hardware.backend === 'bridge' ? 'UNO Q Bridge' : `${data.hardware.port}`;
        } else {
          hwLabel.innerText = 'Virtual Sim';
        }

        // Engine Badge
        if (data.engine) {
          const engLabel = document.getElementById('engine-label');
          if (engLabel) engLabel.innerText = data.engine;
        }

        // 3. Update Slot Buttons & Badges
        for (let s = 1; s <= 6; s++) {
          const sData = data.all_slots[s];
          const btn = document.getElementById(`btn-slot-${s}`);
          const tag = document.getElementById(`tag-slot-${s}`);
          const thumb = document.getElementById(`thumb-img-${s}`);

          const isInspectingThis = (data.inspecting_slot === s);
          const isCurrentActive = (data.active_slot === s && !data.inspecting_slot);

          btn.classList.toggle('active', isInspectingThis || isCurrentActive);

          if (thumb && sData.timestamp && thumb.dataset.ts !== sData.timestamp) {
            thumb.dataset.ts = sData.timestamp;
            thumb.src = `/api/slot_photo/${s}?t=` + Date.now();
          }

          if (isInspectingThis) {
            tag.className = 'slot-thumb-tag pill-move';
            tag.innerText = 'MOVING';
          } else {
            let vCls = 'pill-pend';
            if (sData.verdict === 'PASS') vCls = 'pill-pass';
            else if (sData.verdict === 'FAIL') vCls = 'pill-fail';
            else if (sData.verdict === 'EMPTY') vCls = 'pill-warn';

            tag.className = 'slot-thumb-tag ' + vCls;
            tag.innerText = sData.verdict;
          }
        }

        // 4. Update Photo & Inspection Details
        if (data.is_moving) {
          document.getElementById('hud-slot-tag').innerText = `Rotating to Slot ${data.inspecting_slot}... (Stabilizing)`;
        } else {
          const act = data.active_slot_details;
          if (activeSlot !== data.active_slot || act.timestamp !== lastTimestamp) {
            activeSlot = data.active_slot;
            lastTimestamp = act.timestamp;
            const now = Date.now();
            document.getElementById('slot-img').src = `/api/slot_photo/${activeSlot}?t=` + now;
            const thumb = document.getElementById(`thumb-img-${activeSlot}`);
            if (thumb) thumb.src = `/api/slot_photo/${activeSlot}?t=` + now;
            document.getElementById('hud-slot-tag').innerText = `Slot ${activeSlot} · ${act.slot_type} · ${act.verdict}`;
          }

          const pVal = PULSES[activeSlot - 1] || 500;
          const aVal = ANGLES[activeSlot - 1] || 0;
          document.getElementById('hud-pulse-pos').innerText = `Turntable Position: ${pVal} µs (Slot ${activeSlot} · ${aVal}°)`;
          document.getElementById('hud-latency-pill').innerText = `Inference Latency: ${act.latency_ms} ms`;

          const hero = document.getElementById('verdict-banner-card');
          const heroLabel = document.getElementById('verdict-big-text');
          const heroSub = document.getElementById('verdict-subtext');
          const heroPill = document.getElementById('hero-badge-pill');

          let hClass = 'hero-warn';
          let pClass = 'pill-warn';
          if (act.verdict === 'PASS') {
            hClass = 'hero-pass';
            pClass = 'pill-pass';
            heroSub.innerText = `All 19 components verified intact (${act.latency_ms} ms)`;
          } else if (act.verdict === 'FAIL') {
            hClass = 'hero-fail';
            pClass = 'pill-fail';
            heroSub.innerText = `Defect or missing component detected (${act.latency_ms} ms)`;
          } else {
            heroSub.innerText = `Empty nest or unplaced board`;
          }

          hero.className = 'verdict-banner-card ' + hClass;
          heroPill.className = 'slot-pill ' + pClass;
          heroLabel.innerText = `SLOT ${act.slot_id}: ${act.verdict}`;
          heroPill.innerText = act.verdict;

          // KPIs
          document.getElementById('kpi-board-type').innerText = act.slot_type;
          document.getElementById('kpi-board-conf').innerText = `${(act.slot_confidence * 100).toFixed(0)}%`;
          document.getElementById('kpi-latency').innerText = `${act.latency_ms} ms`;
          document.getElementById('kpi-surface').innerText = act.pcb_issues > 0 ? `${act.pcb_issues} Issue(s)` : 'Clean (0)';

          // Major Components Grid
          const bigLabels = {
            'S': 'Switch (S)',
            'U': 'USB-C / IC (U)',
            'C1': 'Capacitor 1 (C1)',
            'I': 'Inductor (I)',
            'P': 'Power IC (P)',
            'C2': 'Capacitor 2 (C2)'
          };
          const bigGrid = document.getElementById('big-grid');
          bigGrid.innerHTML = '';
          let bigOkCount = 0;
          for (const [k, v] of Object.entries(act.big_components)) {
            const isOk = (v.status === 'PRESENT');
            if (isOk) bigOkCount++;
            const tagCls = isOk ? 'chip-ok' : (v.status === 'MISSING' ? 'chip-miss' : 'chip-idle');
            const tagTxt = isOk ? `✓ OK ${(v.conf*100).toFixed(0)}%` : (v.status === 'MISSING' ? '✗ MISS' : '--');
            const dName = bigLabels[k] || k;
            bigGrid.innerHTML += `
              <div class="comp-card">
                <span class="comp-name">${dName}</span>
                <span class="comp-status-chip ${tagCls}">${tagTxt}</span>
              </div>
            `;
          }
          document.getElementById('big-summary').innerText = `${bigOkCount}/6 Verified`;

          // Small Passives Grid
          const smGrid = document.getElementById('small-grid');
          smGrid.innerHTML = '';
          let smOkCount = 0;
          for (const [k, v] of Object.entries(act.small_components)) {
            const isOk = (v.status === 'PRESENT');
            if (isOk) smOkCount++;
            const tagCls = isOk ? 'chip-ok' : (v.status === 'MISSING' ? 'chip-miss' : 'chip-idle');
            const tagTxt = isOk ? `${(v.conf*100).toFixed(0)}%` : (v.status === 'MISSING' ? 'MISS' : '--');
            smGrid.innerHTML += `
              <div class="passive-chip">
                <span class="passive-name">${k}</span>
                <span class="comp-status-chip ${tagCls}">${tagTxt}</span>
              </div>
            `;
          }
          document.getElementById('sm-summary').innerText = `${smOkCount}/13 Verified`;

          // Bare PCB Defect
          const pcbText = document.getElementById('pcb-status-text');
          if (act.pcb_issues > 0) {
            pcbText.innerText = `${act.pcb_issues} Surface Issue(s) Detected`;
            pcbText.style.color = '#dc2626';
          } else {
            pcbText.innerText = '0 Issues Detected (Clean Surface)';
            pcbText.style.color = 'var(--pass)';
          }
        }
      } catch (e) {
        console.error("Telemetry fetch error:", e);
      }
    }

    setInterval(updateTelemetry, 350);
  </script>
</body>
</html>
"""

# ── FLASK APP ROUTING ────────────────────────────────────────────────────────
app = Flask(__name__)
system = None


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/logo/arduino")
def api_logo_arduino():
    p = BASE_DIR / "arduino_logo.jpg"
    if p.exists():
        return send_file(str(p), mimetype="image/jpeg")
    return redirect("https://logowik.com/content/uploads/images/arduino5804.jpg")


@app.route("/api/logo/edgeimpulse")
def api_logo_edgeimpulse():
    p = BASE_DIR / "ei_logo.png"
    if p.exists():
        return send_file(str(p), mimetype="image/png")
    return redirect("https://www.edge-ai-vision.com/wp-content/uploads/2021/05/logo_edgeimpulse_may_2021.png")


@app.route("/api/slot_photo/<int:slot_id>")
def get_slot_photo(slot_id):
    slot_id = max(1, min(6, slot_id))
    if system is not None:
        with system.lock:
            jpeg = system.slot_photos.get(slot_id)
            if jpeg:
                resp = Response(jpeg, mimetype="image/jpeg")
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                return resp

    blank = np.full((480, 640, 3), (248, 250, 252), dtype=np.uint8)
    cv2.putText(blank, f"Slot {slot_id}: Standby", (160, 240), FONT, 0.8, (100, 116, 139), 2, LINE_AA)
    _, buf = cv2.imencode(".jpg", blank)
    resp = Response(buf.tobytes(), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.route("/api/status")
def api_status():
    if system is not None:
        return jsonify(system.get_telemetry())
    return jsonify({"error": "System uninitialized"}), 503


@app.route("/api/select_slot/<int:slot_id>", methods=["POST"])
def api_select_slot(slot_id):
    if system is not None:
        res = system.select_slot_manual(slot_id)
        return jsonify({"success": True, "slot": res})
    return jsonify({"success": False}), 500


@app.route("/api/toggle_mode", methods=["POST"])
def api_toggle_mode():
    if system is not None:
        system.mode = "MANUAL" if system.mode == "AUTO" else "AUTO"
        system.last_manual_time = time.time()
        return jsonify({"success": True, "mode": system.mode})
    return jsonify({"success": False}), 500


@app.route("/api/hardware/ports")
def api_hardware_ports():
    ports = ArduinoHardwareController.list_available_ports()
    return jsonify({"ports": ports})


@app.route("/api/hardware/connect", methods=["POST"])
def api_hardware_connect():
    data = request.get_json(force=True, silent=True) or {}
    port = data.get("port", "auto")
    baud = int(data.get("baud", 115200))
    if system is not None:
        ok, msg = system.hw.connect_to_port(port, baud)
        return jsonify({
            "success": ok,
            "message": msg,
            "connected": system.hw.is_connected,
            "backend": system.hw.backend,
            "port": system.hw.port,
            "baudrate": system.hw.baudrate
        })
    return jsonify({"success": False, "message": "System not ready"}), 503


@app.route("/api/hardware/test_servo/<int:slot_id>", methods=["POST"])
def api_hardware_test_servo(slot_id):
    if system is not None:
        system.hw.move_to_slot(slot_id)
        return jsonify({"success": True, "slot": slot_id, "pulse": SERVO_POSITIONS[slot_id - 1]})
    return jsonify({"success": False}), 503


@app.route("/api/hardware/test_led/<color>", methods=["POST"])
def api_hardware_test_led(color):
    if system is not None:
        system.hw.set_led(color)
        return jsonify({"success": True, "color": color})
    return jsonify({"success": False}), 503


@app.route("/api/config/sensitivity", methods=["POST"])
def api_config_sensitivity():
    data = request.get_json(force=True, silent=True) or {}
    conf = float(data.get("conf", 0.20))
    use_roi = bool(data.get("use_roi", False))
    if system is not None:
        system.conf = conf
        system.use_roi = use_roi
        return jsonify({"success": True, "conf": system.conf, "use_roi": system.use_roi})
    return jsonify({"success": False}), 503


# ── ENTRYPOINT ───────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="BMS Vision Inspection — Pure Edge Impulse (.eim) AOI System")
    parser.add_argument("--source", type=str, default="0",
                        help="Camera index ('0', '1'), video path ('.mp4'), or image path ('.jpg')")
    parser.add_argument("--serial-port", type=str, default="auto",
                        help="Communication port ('bridge', 'auto', '/dev/ttyACM0', 'COM15')")
    parser.add_argument("--baud", type=int, default=115200,
                        help="Serial baudrate (default: 115200)")
    parser.add_argument("--port", type=int, default=5000,
                        help="Flask web dashboard HTTP port (default: 5000)")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Flask host interface (default: 0.0.0.0)")
    parser.add_argument("--conf", type=float, default=0.20,
                        help="Component detection confidence threshold (default: 0.20)")
    parser.add_argument("--pcb-conf", type=float, default=0.60,
                        help="Bare PCB defect confidence cutoff (default: 0.60)")
    parser.add_argument("--use-roi", action="store_true", default=True,
                        help="Enable tight center PCB reticle filtering (default: True)")
    parser.add_argument("--full-frame", action="store_false", dest="use_roi",
                        help="Disable center reticle filtering and inspect full frame")
    return parser.parse_args()


def main():
    global system
    args = parse_args()

    print("\n" + "="*65)
    print("  BMS Vision Inspection - Pure Edge Impulse (.EIM) AOI System")
    print(f"  Inference Engine : Edge Impulse (.eim) ONLY (No ONNX)")
    print(f"  Preprocessing    : Fit Long Axis (Letterbox, Unquantized float32)")
    print(f"  Camera Source    : {args.source}")
    print(f"  Hardware Link    : {args.serial_port}")
    print(f"  Detection Conf   : {args.conf:.2f}")
    print(f"  Web Dashboard    : http://{args.host}:{args.port}")
    print("="*65 + "\n")

    # Verify model presence
    models_to_check = [
        ("Slot Occupancy", SLOT_MODEL_P),
        ("Big Components", BIG_MODEL_P),
        ("Small Components", SMALL_MODEL_P),
        ("Bare PCB Defect", PCB_MODEL_P)
    ]
    missing = [f"{name} ({p.name})" for name, p in models_to_check if not p.exists()]
    if missing:
        print(f"ERROR: Edge Impulse .eim model(s) missing in {MODELS_DIR}: {missing}")
        sys.exit(1)

    system = MultiSlotInspectionSystem(
        source=args.source,
        serial_port=args.serial_port,
        conf=args.conf,
        pcb_conf=args.pcb_conf,
        use_roi=args.use_roi
    )
    system.start()

    print(f"Starting Flask server on port {args.port}...")
    try:
        app.run(host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\nShutting down pipeline...")
    finally:
        system.stop()
        print("BMS Vision Inspection shutdown complete.")


if __name__ == "__main__":
    main()
