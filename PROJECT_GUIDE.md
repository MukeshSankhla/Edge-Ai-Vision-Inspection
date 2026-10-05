# Edge AI Vision Inspection System: Transforming a $60 SBC into an Industrial Inspection Station

![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/Cover.gif)

What if a $60 SBC could turn a simple webcam into a complete industrial vision inspection system? That was the idea behind this project. At the heart of the system is the **Arduino UNO Q**, a compact Linux-capable single-board computer that brings enough processing power to run modern AI workloads at the edge. Combined with **Edge Impulse**, it becomes possible to take computer-vision models developed on a PC and bring them directly onto an embedded device for real-time inspection—without relying on the cloud.

For this project, I built a **six-slot rotating vision inspection station** using the Arduino UNO Q, a webcam, and a servo motor. A board placed into one of the six slots is automatically rotated into the inspection position, where the camera captures it and the AI pipeline determines what is present and what needs to be inspected. The system first identifies whether the slot is empty, contains a bare PCB, or contains an assembled PCBA:
- **Bare PCBs** are inspected for scratches and visible surface damage.
- **Assembled PCBAs** go through component-level inspection, verifying both large components (USB-C, JST connectors, switches, power ICs, inductors) and smaller 0805 components (LEDs, resistors, capacitors).

The interesting part is that the AI models were trained separately using **YOLO** and then brought into **Edge Impulse using Bring Your Own Model (BYOM)**. Edge Impulse essentially becomes the bridge between model development and deployment—it packages the models, manages the edge inference pipeline, and makes it much easier to deploy and run the vision workload directly on the UNO Q. The result is a small, self-contained inspection station combining AI vision, robotics, and edge computing into one system.

What started as an experiment with a camera, a rotating platform, and an Arduino UNO Q turned into a miniature automated quality-inspection line—the kind of system that can continuously look at physical products, make decisions locally, and trigger the next action without needing a human to inspect every board.

![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/1.gif)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/2.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/3.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/4.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/5.JPG)

---

## 🛠️ Components

- 1× [Arduino UNO Q](https://www.arduino.cc/product-uno-q)
- 1× [DF Metal Geared 15Kg Standard Servo 270° (DSS-M15S)](https://www.dfrobot.com/product-1177.html)
- 1× [Logitech C270 HD Webcam](https://www.logitech.com/en-in/shop/p/c270-hd-webcam.960-000584)
- 1× [WS2812B RGB LED Module](https://robu.in/product/ws2812b-rgb-addressable-led-module/)
- 1× [USB Hub](https://www.amazon.in/dp/B0BR3M8XHK?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1)
- Fasteners & Screws: 4× M2 screws, 4× M3×10mm screws, 4× M3×4mm screws, Servo horn screws


![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/6.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/7.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/8.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/9.JPG)

---

## 📐 CAD & 3D Printing

![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/10.png)

To turn the electronics and vision system into a proper standalone inspection station, I designed a custom enclosure in Fusion 360. The design is split into five 3D-printed parts, with each part having a specific role in the system:

- **Main Body**: Houses the Arduino UNO Q and the 360°/270° servo motor.
- **Rotating Plate**: Mounts directly to the servo shaft using the metal horn supplied with the servo. This plate provides the six slots where the PCBs are placed during inspection.
- **Vertical Pole & Pole Mount**: Mounted on the body to act as the rigid housing for the webcam module as well as the RGB status LED.
- **Pole Cover**: Sits on top of the pole to retain the LED and wiring cleanly.
- **Dome Diffuser**: Sits over the RGB LED to spread the light and provide a uniform visual status indicator.

All five parts were designed with easy assembly and accessibility in mind, so the electronics can be installed and serviced without having to redesign the entire enclosure. I 3D-printed the complete enclosure on my **Bambu Lab P1S** using **PLA Pro** and standard print settings. This made it possible to quickly iterate on the mechanical design and build a compact, clean-looking enclosure around the vision inspection system.

* **Fusion 360 Design URL:** [Autodesk Viewer / Download](https://a360.co/4xOSRFz)

![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/11.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/12.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/13.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/14.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/15.JPG)

---

## 🔧 Assembly Guide

### Servo Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/16.JPG)
Start with the 3D-printed Body and the DF DSS-M15S servo. Place the servo into the dedicated mounting slot in the body and align the screw holes with the mounting points. Once aligned, secure the servo using the four screws supplied with the servo. Make sure the servo is firmly mounted and does not move inside the enclosure, as any mechanical play can affect the positioning accuracy of the rotating plate.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/17.JPG)

### Arduino UNO Q Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/18.JPG)
Next, install the Arduino UNO Q inside the 3D-printed Body. Align the board with the printed standoffs and make sure the USB Type-C port lines up with the opening in the enclosure. Once everything is correctly aligned, secure the Arduino UNO Q using four M2 screws.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/19.JPG)

### Pole Mount Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/20.JPG)
Take the 3D-printed Pole and Pole Mount and align the two parts together. Secure them using 2 × M3 × 10 mm screws. Make sure the pole is firmly attached, as it will hold the camera and LED assembly above the rotating inspection plate.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/21.JPG)

### Camera & LED Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/23.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/22.JPG)
1. For the camera, first remove the camera PCB from the Logitech C270 housing, leaving the camera module and PCB exposed.
2. Take the camera PCB and carefully slide it into the designated slot inside the 3D-printed Pole. Align the camera with the opening at the top of the pole and route the USB/camera wires through the hollow section of the pole. This keeps the wiring hidden and gives the assembly a clean appearance.
3. Next, prepare the WS2812B RGB LED by soldering three wires to it:
   - **GND**
   - **5V**
   - **S-IN** (Data)
4. Route these wires through the hollow section of the pole as well.
5. Now take the Pole Cover and mount the WS2812B LED into the dedicated LED opening. Apply a small amount of glue to secure the LED in place.
6. Finally, snap the Pole Cover onto the top of the Pole. The cover should fit securely. If the fit is slightly loose, apply a small amount of quick-setting glue to hold it in place.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/24.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/25.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/26.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/27.JPG)

### Connections
To connect the WS2812B RGB LED and the servo motor to the Arduino UNO Q, first prepare a few header pins and solder the connections as follows:

| Peripheral | Connection Wire | Arduino UNO Q Header Pin |
| :--- | :--- | :--- |
| **Servo GND & LED GND** | Solder together to a single header pin | **GND** |
| **Servo 5V & LED 5V** | Solder together to a single header pin | **5V** |
| **Servo Signal** | Signal wire to header pin | **Pin 9** |
| **LED S-IN (Data)** | Data wire to header pin | **Pin 8** |

![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/28.JPG)

### Pole and Body Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/29.JPG)
Now it's time to attach the completed Pole Assembly to the main Body. Align the Pole Assembly with the mounting points on the Body and make sure the camera USB cable is correctly routed through the designated opening. Before tightening the screws, neatly manage the excess camera and RGB LED wires inside the Body so they do not interfere with the servo or rotating mechanism.

Once everything is properly aligned and the wiring is clear, secure the Pole Assembly to the Body using 2 × M3 × 10 mm screws.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/30.JPG)

### Rotating Plate Assembly
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/31.JPG)
1. Take the 3D-printed Rotating Plate and the servo horn that came with the servo. Align the servo horn with the mounting points on the Rotating Plate and snap it into position.
2. Secure the servo horn to the Rotating Plate using 4 × M3 × 4 mm screws.
3. Next, take the completed Rotating Plate assembly and align the servo horn with the servo shaft already mounted in the Body. Carefully press the assembly onto the servo shaft, making sure it is properly seated and aligned.
4. Finally, use the servo screw supplied with the servo to secure the Rotating Plate assembly to the servo shaft.
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/32.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/33.JPG)
![Cover](https://raw.githubusercontent.com/MukeshSankhla/Edge-Ai-Vision-Inspection/main/Images/34.JPG)
And that's it! The mechanical assembly is complete.

---

## 🧠 Training the Machine Learning Models

As mentioned earlier, for this project I am using a custom battery charging and discharging circuit PCB, but the same approach can be applied to almost any PCB or PCBA depending on your inspection requirements.

The first step is to build the dataset for each of the four vision models. Since the final system will use the same webcam and camera position, it is important to capture the training images using the same camera and setup that will be used during the actual inspection. I connected the webcam to my PC, opened the Camera app, and captured multiple images of the different inspection conditions. I captured images of an empty slot, bare PCB, and assembled PCBA, along with different examples of the defects and components that I wanted the models to learn. In general, having more representative images for each condition gives the model more examples to learn from and can help improve its ability to generalize.

Once the images were collected, I imported the dataset into [Make Sense](https://www.makesense.ai/), an online annotation tool, and started labeling the images according to the requirements of each model.

### Model Classes & Annotations

1. **Slot Occupancy Model (Image Classification):**
   - `Empty`
   - `PCB`
   - `PCBA`

2. **PCB Inspection Model (Object Detection):**
   - `Issue / Scratch` — Used to identify visible scratches or damage on the PCB surface.

3. **PCBA Big Component Inspection Model (Object Detection):**
   Classes based on the component type and whether the component is present (`A` = Available) or missing (`N` = Not Available):
   - `SA` / `SN` — SMD Switch Available / Not Available
   - `UA` / `UN` — USB Type-C Available / Not Available
   - `C1A` / `C1N`, `C2A` / `C2N` — JST Connector 1/2 Available / Not Available
   - `IA` / `IN` — Inductor Available / Not Available
   - `PA` / `PN` — Power IC Available / Not Available

4. **PCBA Small Component Inspection Model (Object Detection for 0805 components):**
   - `L1A` / `L1N`, `L2A` / `L2N` — LEDs
   - `C1A` / `C1N` through `C7A` / `C7N` — Capacitors
   - `R1A` / `R1N`, `R3A` / `R3N`, `R4A` / `R4N`, `R5A` / `R5N` — Resistors

This naming convention makes it easier for the final application to understand not only which component it is looking at, but also whether that component is present or missing.

After annotating all the images, I exported the annotations from Make Sense as a single CSV file. This labeled dataset is then used as the foundation for training the individual machine-learning models.

### Dataset Organization

Before moving on to model training, make sure the datasets are organized properly. Since we are training four different models, I recommend keeping each model's dataset completely separate:

```text
Main Folder/
│
├── Slot Occupancy/
│   └── dataset/
│       ├── training/
│       ├── testing/
│       └── Label.csv
│
├── PCB Inspection/
│   └── dataset/
│       ├── training/
│       ├── testing/
│       └── Label.csv
│
├── PCBA Big Comp Inspection/
│   └── dataset/
│       ├── training/
│       ├── testing/
│       └── Label.csv
│
└── PCBA Small Comp Inspection/
    └── dataset/
        ├── training/
        ├── testing/
        └── Label.csv
```

Each model has its own dataset folder, containing separate training and testing images along with the corresponding `Label.csv` file. Keeping the four datasets isolated is important because each model has a different purpose and different set of classes.

---

## 🎯 Preparing the Dataset for YOLO Training

Once the images have been captured and annotated in MakeSense, the next step is to convert the dataset into the format required by YOLO. The original dataset contains the captured images and the `labels_makesense.csv` annotation file. For the example Big Component Inspection model, the dataset contains 44 images and 264 bounding-box annotations, split into 36 training images and 8 testing images.

The MakeSense annotations are then converted into the standard YOLO dataset structure:

```text
yolo_dataset/
│
├── images/
│   ├── train/
│   └── val/
│
├── labels/
│   ├── train/
│   └── val/
│
└── data.yaml
```

Before training, run a dataset verification step to make sure the images and annotations are valid. This checks that the bounding boxes are correctly formatted and remain within the valid image boundaries.

> [!IMPORTANT]
> One critical detail in this project is that the components are mounted in fixed physical positions on the PCB. Because of this, **horizontal and vertical image flipping were disabled during augmentation**. Flipping the image could effectively swap components from one side of the PCB to another and teach the model an incorrect spatial relationship.

---

## 🚀 Training & Evaluating the YOLO Model

### Training the YOLO Model
For this project, I used **YOLO11 Nano (`yolo11n.pt`)**, a lightweight object-detection model that is well suited for edge deployment. The model was trained for 80 epochs with an image size of 640 × 640, a batch size of 8, and an NVIDIA RTX 5070 Ti GPU.

The training was executed using:
```bash
python train.py --epochs 80 --batch 8 --device 0
```

The training process took approximately 48 seconds for 80 epochs on the RTX 5070 Ti. During training, the model learns the visual characteristics of each component and the difference between the Available (A) and Not Available/Missing (N) classes.

### Evaluating and Testing the YOLO Model
After training the YOLO model, the next step is to evaluate its performance using the validation dataset.

For the example Big Component Inspection model:
- **Precision:** 97.94%
- **Recall:** 100%
- **mAP@0.5:** 99.50%
- **mAP@0.5:0.95:** 89.60%

After checking the numerical metrics, I also performed test inference on the images to visually verify the detections. The model correctly identified all six large components on fully populated boards and classified the corresponding components as missing on bare/unpopulated boards. Visual verification confirms that bounding boxes are correctly positioned and that the model detects the expected components before moving to deployment.

---

## 🔄 Exporting the YOLO Model to ONNX

Once the YOLO model has been trained and tested successfully, the next step is to export the best model into ONNX (Open Neural Network Exchange) format:

- **Saved Path:** `runs/train/weights/best.onnx`
- **Model Size:** ~10.1 MB
- **Opset Version:** 17/18
- **Graph Optimization:** Optimized using `onnxslim` to reduce unnecessary overhead while keeping the trained model intact.
- **Input Shape:** `[1, 3, 640, 640]` in `float32` format.
- **Output Shape:** `[1, 16, 8400]`, containing bounding-box coordinates and confidence scores for the 12 large-component classes.
- **Inference Speed:** ~3.2 ms per image in ONNX Runtime.

---

## 🌐 Importing the YOLO Model into Edge Impulse (BYOM)

The same training process is followed for the other inspection models. Once the models are exported to ONNX, we bring them into Edge Impulse using Bring Your Own Model (BYOM).

### Creating the Edge Impulse Project
1. Open [Edge Impulse Studio](https://studio.edgeimpulse.com/) and log into your account.
2. Click **Create New Project** and enter a name.
3. In the project dashboard, click **Upload your Model**.
4. Select the `weights/best.onnx` file generated during the YOLO training process.
5. When Edge Impulse asks whether you want performance characteristics (latency, RAM, ROM) for a specific device, select **Yes**.
6. Select **Arduino Uno Q** as the target device.
7. Click **Upload**.

### Configuring the Imported Model
Use the following settings:
- **Model Input:** Image
- **Model Output:** Object Detection
- **Resize Mode:** Fit Long Axis
- **Output Layer:** YOLOv11 (Coordinates in absolute values)
- **Output Labels:** Match the class names used when training the YOLO model.
- Click **Save**.

### Why Use Edge Impulse If We Already Have a YOLO Model?
1. **Customization:** With BYOM, we are not restricted to only models trained inside Edge Impulse. We can train separate YOLO models specifically for slot occupancy, PCB inspection, and PCBA component inspection using standard PyTorch/Ultralytics pipelines.
2. **Performance Optimization:** Edge Impulse profiles and optimizes the model specifically for the target hardware (Qualcomm QRB2210 Linux MPU on the Arduino UNO Q).
3. **Faster Deployment:** Packaging models into standalone `.eim` executable binaries removes external Python runtime overhead and makes deployment seamless.
4. **Flexibility:** Keeps a modular workflow:
   $$\text{Custom Dataset} \rightarrow \text{YOLO Training} \rightarrow \text{Validation} \rightarrow \text{ONNX} \rightarrow \text{Edge Impulse BYOM} \rightarrow \text{Arduino UNO Q Deployment}$$

### Testing and Building the Model
- In Edge Impulse, upload validation images to **Data Acquisition**, go to **Model Testing**, and click **Classify All**.
- You can also use **Live Classification** directly in the browser to point your webcam at the PCB/PCBA and inspect real-time predictions.
- On the **Deployment** page, select **Arduino UNO Q** and click **Build** to download the standalone `.eim` executable binary.

#### Public Model Links
- [Slot Occupancy Model](https://studio.edgeimpulse.com/public/1123393/live)
- [PCB Defect Inspection Model](https://studio.edgeimpulse.com/public/1125264/live)
- [PCBA Big Component Inspection Model](https://studio.edgeimpulse.com/public/1125284/live)
- [PCBA Small Component Inspection Model](https://studio.edgeimpulse.com/public/1125307/live)

---

## ⚡ Deploying the Vision Inspection System on Arduino UNO Q

With all four `.eim` files ready, we deploy the complete system to the Arduino UNO Q:

```text
BMS EIM Vision Inspection/
│
├── arduino_firmware/
│   └── bms_servo_led/
│       └── bms_servo_led.ino
│
├── models/
│   ├── slot-occupancy.eim
│   ├── pcb-inspection.eim
│   ├── big-components-inspection.eim
│   └── small-components-inspection.eim
│
├── snapshots/
├── bms_eim_vision_inspection.py
├── requirements.txt
└── README.md
```

### Inspection Pipeline Flow
1. **Camera Acquisition:** The webcam continuously captures the inspection area.
2. **Slot Occupancy:** Stage 1 runs `slot-occupancy.eim`.
   - If **Empty**: Inspection for this slot is skipped.
   - If **PCB**: Runs `pcb-inspection.eim` to check for scratches and defects.
   - If **PCBA**: Runs `big-components-inspection.eim` and `small-components-inspection.eim` to verify all components.
3. **PASS / FAIL Logic:** Determines pass/fail status based on missing parts or detected defects.
4. **Hardware Action:** Sends RPC commands to the Arduino firmware to set the WS2812B RGB LED color and rotate the servo turntable to the next slot.
5. **Web Dashboard:** Hosts a live interface on port 5000 to display camera frames, bounding boxes, and pass/fail counts.

```
Camera ──> Slot Occupancy ──> PCB/PCBA Inspection ──> PASS/FAIL ──> RGB LED ──> Rotate to Next Slot
```

### Arduino UNO Q Dual-Domain Architecture (MPU + MCU)
The UNO Q features two separate processors:
- **Qualcomm MPU (Linux):** Runs the Python application, webcam capture, Edge Impulse `.eim` models, inspection logic, and Flask web dashboard.
- **STM32U585 MCU (Zephyr / Arduino):** Handles real-time hardware execution: servo motor PWM on Pin 9 and WS2812B addressable LED data on Pin 8.

Communication uses Arduino's **MessagePack RPC bridge** via a Unix domain socket:

```text
Python Application (MPU)
          ↓
Arduino Router (/var/run/arduino-router.sock)
          ↓
MessagePack RPC
          ↓
STM32U585 MCU (Zephyr)
          ↓
Servo (Pin 9) + WS2812B RGB LED (Pin 8)
```

This clean separation allows the Linux MPU to focus on computer vision and inference, while the MCU handles deterministic real-time hardware timing.

---

## 🚀 Step-by-Step Setup & Execution

### 1. Flash Arduino Firmware
1. Open the Arduino IDE on your computer.
2. Open [`bms_servo_led.ino`](file:///c:/Users/MAKERBRAINS/Downloads/Edge%20Ai%20Vision%20Inspection/BMS%20EIM%20Vision%20Inspection/arduino_firmware/bms_servo_led/bms_servo_led.ino) located in:
   `BMS EIM Vision Inspection/arduino_firmware/bms_servo_led/bms_servo_led.ino`
3. Select board **Arduino UNO Q** and the corresponding port.
4. Click **Upload**.
5. Once complete, the RGB LED illuminates **green** and the turntable positions itself to **home (0°)**.

### 2. Aligning the Rotating Plate
Check whether the first slot is aligned with the camera. If it is slightly off, loosen the center servo horn screw, manually rotate the plate to exact center, and re-tighten. This sets the mechanical home position.

### 3. Deploying to the Arduino UNO Q
1. Connect the Arduino UNO Q to a powered USB hub and connect the webcam to the same hub.
2. Identify your UNO Q's IP address (e.g., `192.168.1.18`).
3. Copy the project folder to the UNO Q using `scp`:
   ```bash
   scp -r "BMS EIM Vision Inspection" arduino@192.168.1.18:~/Downloads/
   ```
4. SSH into the UNO Q:
   ```bash
   ssh arduino@192.168.1.18
   ```
5. Set up the Python environment:
   ```bash
   cd ~/Downloads/"BMS EIM Vision Inspection"
   sudo apt update
   sudo apt install python3 python3-venv python3-pip -y
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   chmod +x models/*.eim
   ```
6. Start the inspection application:
   ```bash
   python bms_eim_vision_inspection.py --source 0
   ```
   *(If your webcam is assigned to a different index, try `--source 1` or `--source 2`).*

### 4. Running the Application on Subsequent Boots
```bash
ssh arduino@192.168.1.18
cd ~/Downloads/"BMS EIM Vision Inspection"
source .venv/bin/activate
python bms_eim_vision_inspection.py --source 0
```

### 5. Accessing the Web Dashboard
Open any browser on the local network and navigate to:
```text
http://192.168.1.18:5000/
```

The web dashboard displays:
- Live inspection camera stream with detection overlays
- Current slot number and inspection status (Empty, PCB, PCBA, Pass/Fail)
- Manual turntable indexing and home calibration controls
- Captured defect snapshots and inspection history

---

## 🏁 Conclusion

This project demonstrates how edge AI turns low-cost hardware into an industrial-grade vision inspection station. By combining mechanical 3D design, custom YOLO11 models, Edge Impulse BYOM packaging, and the dual-brain Arduino UNO Q, we created a self-contained, real-time AOI system that operates entirely offline without cloud dependencies.

The core workflow:
$$\text{Define Inspection} \rightarrow \text{Design Hardware} \rightarrow \text{Collect Data} \rightarrow \text{Train YOLO} \rightarrow \text{Optimize via BYOM} \rightarrow \text{Deploy to UNO Q} \rightarrow \text{Automate}$$

This blueprint can be directly adapted for manufacturing quality control, assembly verification, packaging inspection, sorting, and edge robotics.

---

## 📚 Project Resources

- **GitHub Repository:** [Edge AI Vision Inspection](https://github.com/MukeshSankhla/Edge-Ai-Vision-Inspection)
- **CAD Design (Fusion 360):** [Enclosure & Turntable Model](https://a360.co/4xOSRFz)
- **Edge Impulse Public Models:**
  - [Slot Occupancy Detection](https://studio.edgeimpulse.com/public/1123393/live)
  - [PCB Defect Inspection](https://studio.edgeimpulse.com/public/1125264/live)
  - [PCBA Big Component Inspection](https://studio.edgeimpulse.com/public/1125284/live)
  - [PCBA Small Component Inspection](https://studio.edgeimpulse.com/public/1125307/live)
