# Big Components Inspection - YOLO Vision Model Training Documentation

This document provides a comprehensive, step-by-step record of the training, validation, evaluation, and export of the YOLO object detection model for the **Big Components Inspection** project.

---

## 1. Project Overview & Inspection Objective

### 1.1 Objective
The purpose of this project is Automated Optical Inspection (AOI) of large electronic components on circuit boards or mechanical assemblies. The visual inspection system detects whether each designated component is **Present / Available (`A`)** or **Absent / Missing (`N`)**.

### 1.2 Inspection Zones & Classes
There are **6 physical component locations** on each board, producing **12 distinct detection classes**:

| Component Code | Component Description | Present / Available (`A`) | Absent / Missing (`N`) |
| :--- | :--- | :--- | :--- |
| **C1** | Capacitor 1 (Bottom Left) | `C1A` | `C1N` |
| **C2** | Capacitor 2 (Bottom Right) | `C2A` | `C2N` |
| **I** | Inductor (Bottom Center-Left) | `IA` | `IN` |
| **P** | Power / Port / Plug (Bottom Center-Right) | `PA` | `PN` |
| **S** | Socket / Sensor / Switch (Top Left) | `SA` | `SN` |
| **U** | IC / Processing Unit (Top Right) | `UA` | `UN` |

Each inspection image contains exactly 6 annotations corresponding to these six locations.

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

```
[Raw Dataset]
  ├── dataset/labels_makesense.csv (264 annotations)
  ├── dataset/train/ (36 images)
  └── dataset/test/ (8 images)
         │
         ▼
[Step 1 & 2: Dataset Formatting] ──> convert_makesense_to_yolo.py
         │
         ▼
[YOLO Dataset Structure]
  ├── yolo_dataset/images/train/ (36 images)
  ├── yolo_dataset/images/val/ (8 images)
  ├── yolo_dataset/labels/train/ (36 txt files, 216 bboxes)
  ├── yolo_dataset/labels/val/ (8 txt files, 48 bboxes)
  └── data.yaml
         │
         ▼
[Step 3: Verification] ──> verify_dataset.py (Integrity & BBox check)
         │
         ▼
[Step 4 & 5: Model Training] ──> train.py (YOLO11n, 80 epochs on RTX 5070 Ti)
         │
         ▼
[Step 6: Evaluation & Metrics] ──> mAP@50: 99.5%, Precision: 97.9%, Recall: 100.0%
         │
         ▼
[Step 7: Test Inference] ──> predict.py (Visual inspection on test set)
         │
         ▼
[Step 8: Model Export] ──> best.pt ➔ best.onnx (Slimmed for edge deployment)
```

---

### Step 1: Raw Data Exploration & Spatial Analysis

1. **Source Data Analysis:**
   - Raw images: 44 total images with a resolution of `1280 x 720` pixels.
   - Annotations source: `dataset/labels_makesense.csv` containing 264 bounding box records.
   - Initial splits: 36 images in `dataset/train/` and 8 images in `dataset/test/`.

2. **Spatial Coordinate Analysis:**
   Analyzing bounding box distributions across all images revealed consistent spatial localization:
   - Component **S**: $X \approx [389, 407]$, $Y \approx [152, 240]$
   - Component **U**: $X \approx [623, 649]$, $Y \approx [183, 236]$
   - Component **C1**: $X \approx [254, 287]$, $Y \approx [395, 463]$
   - Component **I**: $X \approx [450, 469]$, $Y \approx [413, 461]$
   - Component **P**: $X \approx [612, 631]$, $Y \approx [475, 516]$
   - Component **C2**: $X \approx [757, 783]$, $Y \approx [414, 459]$

   > **Key Domain Finding:** Components are positioned in fixed jigs. Horizontal and vertical mirroring would swap asymmetrical components (e.g. flipping C1 on the left into the C2 location on the right). Therefore, training augmentations must disable flipping (`fliplr=0.0`, `flipud=0.0`).

---

### Step 2: Conversion to YOLO Format

A conversion script `convert_makesense_to_yolo.py` was executed to convert the raw MakeSense CSV data into the standard YOLO format:

1. **Coordinate Conversion Formula:**
   MakeSense provides: `[bbox_x, bbox_y, bbox_width, bbox_height]` (pixel coordinates relative to 1280x720).
   YOLO requires normalized center coordinates: `[class_id, x_center, y_center, width, height]` where all values are $\in [0, 1]$:

   $$\text{x\_center} = \frac{\text{bbox\_x} + \frac{\text{bbox\_width}}{2}}{\text{image\_width}}$$

   $$\text{y\_center} = \frac{\text{bbox\_y} + \frac{\text{bbox\_height}}{2}}{\text{image\_height}}$$

   $$\text{norm\_width} = \frac{\text{bbox\_width}}{\text{image\_width}}$$

   $$\text{norm\_height} = \frac{\text{bbox\_height}}{\text{image\_height}}$$

2. **Dataset Configuration (`data.yaml`):**
   ```yaml
   path: C:/Users/MAKERBRAINS/Downloads/Big Components Inspection/yolo_dataset
   train: images/train
   val: images/val

   names:
     0: C1A
     1: C1N
     2: C2A
     3: C2N
     4: IA
     5: IN
     6: PA
     7: PN
     8: SA
     9: SN
     10: UA
     11: UN
   ```

---

### Step 3: Dataset Integrity Verification

The dataset validation script `verify_dataset.py` checked all 44 images and label files:
- All 264 bounding boxes were verified to be strictly within $[0.0, 1.0]$.
- Class distribution across splits:

| Class | Train Set (36 images) | Val Set (8 images) | Total (44 images) |
| :--- | :---: | :---: | :---: |
| **C1A** | 25 | 5 | 30 |
| **C1N** | 11 | 3 | 14 |
| **C2A** | 25 | 5 | 30 |
| **C2N** | 11 | 3 | 14 |
| **IA** | 25 | 5 | 30 |
| **IN** | 11 | 3 | 14 |
| **PA** | 25 | 5 | 30 |
| **PN** | 11 | 3 | 14 |
| **SA** | 26 | 5 | 31 |
| **SN** | 10 | 3 | 13 |
| **UA** | 26 | 5 | 31 |
| **UN** | 10 | 3 | 13 |
| **Total Boxes** | **216** | **48** | **264** |

---

### Step 4: Model Architecture & Training Configuration

The project utilized **YOLO11 Nano (`yolo11n.pt`)**, the latest lightweight object detection architecture from Ultralytics.

#### Key Hyperparameters:
- **Architecture:** YOLO11 Nano (100 layers, 2.58M parameters, 6.4 GFLOPs)
- **Base Weights:** Pretrained ImageNet/COCO weights (`yolo11n.pt`)
- **Epochs:** 80
- **Image Size (`imgsz`):** 640
- **Batch Size:** 8
- **Device:** GPU:0 (NVIDIA RTX 5070 Ti)
- **Optimizer:** Auto (SGD/AdamW with Cosine LR schedule)
- **Patience:** 30 epochs
- **Data Augmentations:**
  - `fliplr = 0.0` (Disabled to protect component spatial alignment)
  - `flipud = 0.0` (Disabled to preserve board vertical orientation)
  - Color space jitter: Moderate HSV adjustments to simulate lighting shifts

---

### Step 5: Training Execution & Loss Convergence

Training was executed via:
```bash
python train.py --epochs 80 --batch 8 --device 0
```

#### Training Timeline:
- **Total Training Duration:** ~48 seconds across 80 epochs on RTX 5070 Ti.
- **Initial Loss (Epoch 1):** `box_loss: 1.748`, `cls_loss: 4.339`, `dfl_loss: 1.514`
- **Midway Loss (Epoch 40):** `box_loss: 0.612`, `cls_loss: 0.884`, `dfl_loss: 0.902`
- **Final Loss (Epoch 80):** `box_loss: 0.521`, `cls_loss: 0.675`, `dfl_loss: 0.848`
- Both training and validation losses converged smoothly without signs of overfitting.

---

### Step 6: Evaluation Results & Metrics

Evaluation on the independent validation set (8 images, 48 instances) produced high precision and recall:

#### Overall Performance Summary
- **Precision ($P$):** **97.94% (0.9794)**
- **Recall ($R$):** **100.00% (1.0000)**
- **mAP@0.5:** **99.50% (0.9950)**
- **mAP@0.5:0.95:** **89.60% (0.8960)**
- **Inference Speed:** **0.9 ms to 3.6 ms per image**

#### Per-Class Performance Breakdown

| Class Name | Target Component | Instances | Precision ($P$) | Recall ($R$) | mAP@0.5 | mAP@0.5:0.95 |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **All Classes** | Overall Board | **48** | **0.979** | **1.000** | **0.995** | **0.896** |
| `C1A` | Capacitor 1 Present | 5 | 0.982 | 1.000 | 0.995 | 0.891 |
| `C1N` | Capacitor 1 Absent | 3 | 0.997 | 1.000 | 0.995 | 0.896 |
| `C2A` | Capacitor 2 Present | 5 | 0.980 | 1.000 | 0.995 | 0.915 |
| `C2N` | Capacitor 2 Absent | 3 | 0.972 | 1.000 | 0.995 | 0.907 |
| `IA` | Inductor Present | 5 | 0.989 | 1.000 | 0.995 | 0.915 |
| `IN` | Inductor Absent | 3 | 0.964 | 1.000 | 0.995 | 0.962 |
| `PA` | Power Port Present | 5 | 0.992 | 1.000 | 0.995 | 0.850 |
| `PN` | Power Port Absent | 3 | 0.966 | 1.000 | 0.995 | 0.863 |
| `SA` | Socket/Switch Present| 5 | 0.981 | 1.000 | 0.995 | 0.895 |
| `SN` | Socket/Switch Absent | 3 | 0.977 | 1.000 | 0.995 | 0.863 |
| `UA` | IC Unit Present | 5 | 0.976 | 1.000 | 0.995 | 0.899 |
| `UN` | IC Unit Absent | 3 | 0.976 | 1.000 | 0.995 | 0.895 |

---

### Step 7: Test Inference & Qualitative Verification

The inference pipeline `predict.py` was executed on all test images with a confidence threshold of 0.25:
```bash
python predict.py --weights runs/train/weights/best.pt --source yolo_dataset/images/val
```

#### Qualitative Findings:
1. **Fully Populated Boards (Images 1 to 5):**
   - Correctly identified all 6 components as Available (`C1A`, `C2A`, `IA`, `PA`, `SA`, `UA`) with high confidences ($0.88 - 0.99$).
   - Zero false detections and zero missed components.

2. **Unpopulated / Bare Boards (Images 6 to 8):**
   - Correctly identified all 6 components as Missing/Absent (`C1N`, `C2N`, `IN`, `PN`, `SN`, `UN`) with high confidences ($0.82 - 0.99$).
   - Clean separation between empty solder pads and mounted components.

Annotated output images are saved in `runs/predict_test/`.

---

### Step 8: Model Export for Production Deployment (ONNX)

To facilitate cross-platform deployment on edge devices, IPCs (Industrial PCs), embedded controllers, or microservices, the best trained model was exported to ONNX:

- **Primary ONNX Files:**
  - `runs/train/weights/best.onnx` (10.1 MB)
  - `weights/best.onnx` (10.1 MB)
- **ONNX Format Version:** Opset 17 / 18
- **Graph Optimization:** Slimmed and pruned using `onnxslim`
- **Model Tensor Architecture:**
  - **Input Tensor (`images`):** Shape `[1, 3, 640, 640]`, Data Type: `float32` (normalized RGB image tensor).
  - **Output Tensor (`output0`):** Shape `[1, 16, 8400]`, Data Type: `float32`:
    - Dim 0 (`1`): Batch size.
    - Dim 1 (`16`): 4 bounding box center/dimension coordinates $(x_c, y_c, w, h)$ + 12 component class confidence scores (`C1A`, `C1N`, `C2A`, `C2N`, `IA`, `IN`, `PA`, `PN`, `SA`, `SN`, `UA`, `UN`).
    - Dim 2 (`8400`): Candidate detection anchors distributed across the 3 feature pyramid scale levels $(80 \times 80 + 40 \times 40 + 20 \times 20 = 6400 + 1600 + 400 = 8400)$.
- **Verification & Benchmark:**
  - **Integrity Check:** Passed `onnx.checker.check_model()` with zero topology errors.
  - **ONNX Runtime Speed:** Benchmark latency of **~3.2 ms** per image on test verification.
- **Runtime Compatibility:**
  - ONNX Runtime (`onnxruntime` / `onnxruntime-gpu`)
  - OpenCV DNN (`cv2.dnn.readNetFromONNX`)
  - NVIDIA TensorRT (`trtexec --onnx=best.onnx --saveEngine=best.engine`)
  - Intel OpenVINO (`mo --input_model best.onnx`)

---

### Step 9: Representative Features for Edge Impulse & INT8 Quantization

When deploying custom models using the **Edge Impulse Bring Your Own Model (BYOM)** workflow, Edge Impulse provides an optional step: **"Upload representative features (Optional)"** to automatically quantize the ONNX model to INT8 precision for accelerated on-device execution on microcontrollers and embedded processors.

#### 1. Requirements for Edge Impulse Calibration Data
- **File Format:** Single NumPy `.npy` binary file.
- **Tensor Shape:** Must strictly match the input shape of the model across $N$ representative samples:
  $$\text{Shape} = (N, 3, 640, 640)$$
- **Data Type & Range:** `float32`, normalized to $[0.0, 1.0]$.
- **Channels Order:** RGB (matching YOLO training).
- **Preprocessing:** Identical letterboxing (preserving aspect ratio with padding) as used during inference.

#### 2. Generated Feature Files
Two calibration feature sets were generated via `generate_representative_features.py`:

| File Name | Sample Count | Array Dimensions | File Size | Description |
| :--- | :---: | :---: | :---: | :--- |
| **`representative_features_val.npy`** | 8 | `(8, 3, 640, 640)` | **39.3 MB** | Clean validation set (Recommended for standard Edge Impulse upload) |
| **`representative_features.npy`** | 44 | `(44, 3, 640, 640)` | **216.3 MB** | Comprehensive full dataset (Train + Val) for full-range calibration |
| **`weights/representative_features.npy`** | 8 | `(8, 3, 640, 640)` | **39.3 MB** | Copy alongside ONNX weights |

#### 3. How to Upload to Edge Impulse Studio
1. Open your project on **[Edge Impulse](https://studio.edgeimpulse.com/)**.
2. Navigate to **Dashboard** $\rightarrow$ **Upload your model** (under "Getting started").
3. In the model upload dialog:
   - Select and upload **`weights/best.onnx`** (or `runs/train/weights/best.onnx`).
4. In the **"Upload representative features (Optional)"** field:
   - Select and upload **`representative_features_val.npy`** (or `representative_features.npy`).
5. Click **Save model**. Edge Impulse will analyze the tensor ranges and automatically calibrate the INT8 quantization weights for your target hardware (e.g. Raspberry Pi, Jetson Nano, ESP32, STM32, Alif Semiconductor, Himax, etc.).

---

## 4. How to Reproduce & Use the Pipeline

### 1. Convert Dataset
```bash
python convert_makesense_to_yolo.py
```

### 2. Verify Dataset
```bash
python verify_dataset.py
```

### 3. Train Model
```bash
python train.py --epochs 80 --batch 8 --device 0
```

### 4. Run Live Webcam Inspection
```bash
# Using the custom dashboard inspection script (recommended):
python webcam_inspect.py --cam 0 --conf 0.4

# Or using the standard YOLO CLI command:
yolo predict model=runs/train/weights/best.pt source=0 show=True conf=0.4
```

### 5. Run Predictions on Static Images
```bash
python predict.py --weights runs/train/weights/best.pt --source <path_to_images>
```

### 6. Export to ONNX Format
```bash
# Using the dedicated exporter with graph verification and runtime test:
python export_onnx.py --weights runs/train/weights/best.pt --imgsz 640 --opset 17

# Or using the Ultralytics CLI:
yolo export model=runs/train/weights/best.pt format=onnx imgsz=640 opset=17
```

### 7. Run Inference with the ONNX Model
```bash
# Using YOLO with the ONNX weights:
yolo predict model=weights/best.onnx source=yolo_dataset/images/val conf=0.4

# Or with webcam:
python webcam_inspect.py --weights weights/best.onnx --cam 0 --conf 0.4
```

### 8. Generate Representative Features for Edge Impulse (.npy)
```bash
# Generate from validation set (39.3 MB, recommended for Edge Impulse upload):
python generate_representative_features.py --source val --output representative_features_val.npy

# Generate from full dataset (216.3 MB, all 44 images):
python generate_representative_features.py --source all --output representative_features.npy
```

---

## 5. Artifacts and Generated Files Directory

```
Big Components Inspection/
├── TRAINING_STEPS.md                      # Complete documentation of all training steps
├── data.yaml                              # YOLO dataset specification
├── convert_makesense_to_yolo.py           # MakeSense CSV to YOLO dataset converter
├── verify_dataset.py                      # Dataset validation and integrity script
├── train.py                               # Model training and validation script
├── predict.py                             # Production inference script
├── webcam_inspect.py                      # Live webcam inspection dashboard script
├── export_onnx.py                         # ONNX export and verification script
├── generate_representative_features.py    # Edge Impulse .npy feature generator
├── representative_features_val.npy        # Validation calibration features (39.3 MB)
├── representative_features.npy            # Full calibration features (216.3 MB)
├── yolo_dataset/                          # Prepared YOLO dataset
│   ├── images/ (train, val)
│   └── labels/ (train, val)
├── weights/
│   ├── best.onnx                          # Production ONNX model (10.1 MB)
│   └── representative_features.npy        # Calibration features copy (39.3 MB)
└── runs/
    ├── train/
    │   ├── weights/
    │   │   ├── best.pt                    # Best PyTorch model weights (5.5 MB)
    │   │   ├── last.pt                    # Final epoch weights
    │   │   └── best.onnx                  # Production ONNX model (10.1 MB)
    │   ├── results.csv                    # Epoch-by-epoch training logs
    │   ├── results.png                    # Training and validation loss curves
    │   ├── confusion_matrix.png           # Classification confusion matrix
    │   ├── BoxF1_curve.png                # F1-confidence trade-off curve
    │   └── BoxPR_curve.png                # Precision-Recall curve
    └── predict_test/                      # Visual prediction outputs on test set
```
