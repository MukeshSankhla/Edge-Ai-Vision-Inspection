# Slot Occuppancy Detection - YOLO Vision Model Training Documentation

This document provides a comprehensive, step-by-step record of the training, validation, evaluation, and export of the YOLO image classification model for the **Slot Occuppancy Detection** project.

---

## 1. Project Overview & Classification Objective

### 1.1 Objective
The purpose of this project is automated machine vision verification of slot occupancy in an electronic manufacturing or test fixture. The system classifies whether an inspection slot is:
1. **`Empty`** - No board present in the slot.
2. **`PCB`** - Bare, unpopulated Printed Circuit Board loaded.
3. **`PCBA`** - Populated Printed Circuit Board Assembly loaded with components.

### 1.2 Dataset Breakdown
- **Class Count:** 3 classes (`Empty`, `PCB`, `PCBA`)
- **Total Images:** 76 images
- **Train Split (61 images):**
  - `Empty`: 16 images
  - `PCB`: 21 images
  - `PCBA`: 24 images
- **Test / Validation Split (15 images):**
  - `Empty`: 4 images
  - `PCB`: 5 images
  - `PCBA`: 6 images

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

### Step 1: Dataset Formatting & Organization
- Organized into standard YOLO classification structure:
  ```
  Slot Occuppancy Detection/
  ├── train/
  │   ├── Empty/
  │   ├── PCB/
  │   └── PCBA/
  └── test/
      ├── Empty/
      ├── PCB/
      └── PCBA/
  ```

### Step 2: Model Architecture
- Architecture: **YOLO11 Nano Classifier (`yolo11n-cls.pt`)**
- Pretrained backbone fine-tuned for high-speed edge classification.
- Image resolution: `224 x 224`
- Epochs: 50 (Early stopped at epoch 22 upon full convergence)
- Batch size: 8
- Device: NVIDIA RTX 5070 Ti

### Step 3: Evaluation Metrics
- **Top-1 Accuracy:** **1.0000 (100.00%)**
- **Top-5 Accuracy:** **1.0000 (100.00%)**
- **Inference Speed:** **~0.1 ms to 2.1 ms** per image on GPU.

### Step 4: Model Export to ONNX
- Model exported to `weights/best.onnx` and `runs/train/weights/best.onnx`.
- Input tensor: `[1, 3, 224, 224]` (`float32`)
- Output tensor: `[1, 3]` (`float32`) representing logits / class probabilities for `[Empty, PCB, PCBA]`.
- Slimmed and optimized with `onnxslim`.

---

## 4. How to Run & Reproduce

### Run Live Webcam Stream:
```bash
python webcam_inspect.py --weights weights/best.onnx --cam 0
```

### Run Batch Prediction:
```bash
yolo classify predict model=weights/best.onnx source=test
```
