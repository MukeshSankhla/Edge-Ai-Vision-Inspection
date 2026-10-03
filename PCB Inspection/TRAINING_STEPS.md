# PCB Inspection - YOLO Vision Model Training Documentation

This document provides a comprehensive, step-by-step record of the training, validation, evaluation, and export of the YOLO object detection model for the **PCB Inspection** project.

---

## 1. Project Overview & Inspection Objective

### 1.1 Objective
The purpose of this project is Automated Optical Inspection (AOI) to detect and localize defects and surface issues on Printed Circuit Boards (PCBs). The model detects bounding boxes labeled as **`Issue`**.

### 1.2 Inspection Classes
- **Class Count:** 1 class (`Issue`)
- **Annotation Count:** 157 bounding boxes across 20 high-resolution images (`1280 x 720`).
- **Splits:** 16 training images (126 issues), 4 test images (31 issues).

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

### Step 1: Dataset Exploration
- 20 total images in `train/` and `test/` folders.
- Labels parsed from `labels_makesense.csv` containing 157 bounding box instances.

### Step 2: YOLO Format Conversion
- Pixel coordinates `(bbox_x, bbox_y, bbox_width, bbox_height)` converted to normalized center coordinates `(x_center, y_center, width, height)`.
- Dataset structured into `yolo_dataset/images/` and `yolo_dataset/labels/` for `train` and `val`.
- Generated `data.yaml`.

### Step 3: Model Architecture & Training Optimization
- Architecture: **YOLO11s (`yolo11s.pt`)** with 9.4M parameters for improved feature resolution on fine defects.
- Hyperparameter Tuning for Micro-Defects:
  - `mosaic = 0.0`: Disabled to prevent cutting and tiling distortion of subtle defects.
  - `fliplr = 0.0`, `flipud = 0.0`: Preserves spatial orientation of the circuit layout.
  - `scale = 0.1`: Minimizes downscaling distortion of small solder/pad anomalies.
- Epochs: 100
- Batch size: 4
- Image size: 640
- Device: NVIDIA RTX 5070 Ti

### Step 4: Validation Performance
- **Precision ($P$):** **73.3% (0.733)**
- **Recall ($R$):** **62.1% (0.621)**
- **mAP@0.5:** **62.2% (0.622)**
- **mAP@0.5:0.95:** **25.5% (0.255)**

### Step 5: Test Inference
- Evaluated on test set images with visual defect bounding boxes saved to `runs/predict_test/`.

### Step 6: Model Export to ONNX
- Model exported to `weights/best.onnx` and `runs/train/weights/best.onnx`.
- Input tensor: `[1, 3, 640, 640]` (`float32`)
- Output tensor: `[1, 5, 8400]` (`float32`) -> 4 coordinates + 1 class score across 8400 anchor candidates.
- Slimmed and optimized with `onnxslim`.
- Target: Edge Impulse Bring Your Own Model (BYOM) deployment.

---

## 4. How to Run & Reproduce

### Run Live Webcam Inspection:
```bash
python webcam_inspect.py --weights weights/best.onnx --cam 0 --conf 0.30
```

### Run Batch Test Prediction:
```bash
yolo predict model=weights/best.onnx source=yolo_dataset/images/val conf=0.30
```

### Edge Impulse Labels:
```text
Issue
```
