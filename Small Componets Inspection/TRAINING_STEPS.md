# Small Components Inspection - YOLO Vision Model Training Documentation

This document provides a comprehensive, step-by-step record of the training, validation, evaluation, and export of the YOLO object detection model for the **Small Components Inspection** project.

---

## 1. Project Overview & Inspection Objective

### 1.1 Objective
The purpose of this project is Automated Optical Inspection (AOI) of small passive and active electronic components (ceramic capacitors, inductors, chip resistors) on assembled circuit boards. The system detects whether each component is **Present / Available (`A`)** or **Absent / Missing (`N`)**.

### 1.2 Inspection Zones & Classes (26 Classes)
There are **13 physical component locations** inspected on each board:

| Component Code | Component Description | Present (`A`) | Absent (`N`) |
| :--- | :--- | :--- | :--- |
| **C1** | Ceramic Capacitor 1 | `C1A` | `C1N` |
| **C2** | Ceramic Capacitor 2 | `C2A` | `C2N` |
| **C3** | Ceramic Capacitor 3 | `C3A` | `C3N` |
| **C4** | Ceramic Capacitor 4 | `C4A` | `C4N` |
| **C5** | Ceramic Capacitor 5 | `C5A` | `C5N` |
| **C6** | Ceramic Capacitor 6 | `C6A` | `C6N` |
| **C7** | Ceramic Capacitor 7 | `C7A` | `C7N` |
| **L1** | SMD Inductor 1 | `L1A` | `L1N` |
| **L2** | SMD Inductor 2 | `L2A` | `L2N` |
| **R1** | Surface Resistor 1 | `R1A` | `R1N` |
| **R3** | Surface Resistor 3 | `R3A` | `R3N` |
| **R4** | Surface Resistor 4 | `R4A` | `R4N` |
| **R5** | Surface Resistor 5 | `R5A` | `R5N` |

---

## 2. Hardware and Software Environment
- **Operating System:** Windows 11
- **Python Version:** 3.14.6
- **Deep Learning Framework:** PyTorch 2.14.0+cu130
- **Computer Vision Framework:** Ultralytics YOLO v8.4.164
- **Accelerator / GPU:** NVIDIA GeForce RTX 5070 Ti (17 GB VRAM)
- **CUDA Support:** CUDA 13.0 Enabled

---

## 3. Step-by-Step Training Workflow

### Step 1: Data Cleansing & Integrity
1. Filtered out corrupted/degenerate bounding boxes (e.g. width=1, height=0 click artifact in original MakeSense CSV).
2. Cleaned out 4 incomplete images that only had 3 missing component tags without tagging the other 10 visible components, removing false-negative training penalties.
3. Clean dataset split: 41 training images (533 instances), 9 validation/test images (117 instances), all completely annotated across all 13 components.

### Step 2: YOLO Format Conversion
- Pixel coordinates transformed to normalized center coordinates $(x_c, y_c, w, h) \in [0.0, 1.0]$.
- Standardized directory layout under `yolo_dataset/`.
- Generated `data.yaml` defining all 26 classes.

### Step 3: Industrial AOI Model Training
- Architecture: **YOLO11 Nano (`yolo11n.pt`)** (2.58M parameters, 6.4 GFLOPs)
- Epochs: 100
- Batch size: 8
- Image size: 640
- Domain-specific spatial preservation: `mosaic = 0.0`, `fliplr = 0.0`, `flipud = 0.0` (preserves fixed circuit layout)
- Device: NVIDIA RTX 5070 Ti

### Step 4: Final Validation Performance
- **Overall Precision ($P$):** **89.69% (0.8969)**
- **Overall Recall ($R$):** **97.50% (0.9750)**
- **mAP@0.5:** **97.63% (0.9763)**
- **mAP@0.5:0.95:** **82.73% (0.8273)**
- **Class Highlights:** 24 out of 26 classes achieved **0.995 (99.5%) mAP@0.5** with **100% Recall**!

### Step 5: Test Inference
- Evaluated on test set images with predictions saved to `runs/predict_test/`.

### Step 6: Model Export to ONNX
- Exported to `weights/best.onnx` and `runs/train/weights/best.onnx`.
- Input tensor: `[1, 3, 640, 640]` (`float32`)
- Output tensor: `[1, 30, 8400]` (`float32`) -> 4 coordinates + 26 class scores across 8400 anchor candidates.
- Slimmed and optimized with `onnxslim`.
- Target: Edge Impulse Bring Your Own Model (BYOM) deployment.

---

## 4. How to Run & Reproduce

### Run Live Webcam Inspection:
```bash
python webcam_inspect.py --weights weights/best.onnx --cam 0 --conf 0.35
```

### Run Batch Prediction:
```bash
yolo predict model=weights/best.onnx source=yolo_dataset/images/val conf=0.35
```

### Edge Impulse Labels:
Paste into the Edge Impulse output labels field:
```text
C1A, C1N, C2A, C2N, C3A, C3N, C4A, C4N, C5A, C5N, C6A, C6N, C7A, C7N, L1A, L1N, L2A, L2N, R1A, R1N, R3A, R3N, R4A, R4N, R5A, R5N
```
