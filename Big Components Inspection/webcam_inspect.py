"""
Real-time Webcam Inspection for Big Components Inspection using trained YOLO model.
Press 'q' or 'ESC' to exit the webcam stream.
"""

import argparse
import time
import cv2
from ultralytics import YOLO

# Component definitions
COMPONENTS = ["C1", "C2", "I", "P", "S", "U"]


def run_webcam(
    weights="runs/train/weights/best.pt",
    camera_index=0,
    conf=0.4,
    imgsz=640,
    device="0"
):
    print("=" * 60)
    print("  Big Components Inspection - Real-Time Webcam Stream")
    print("=" * 60)
    print(f"Model:        {weights}")
    print(f"Camera Index: {camera_index}")
    print(f"Confidence:   {conf}")
    print("Controls:     Press 'q' or 'ESC' to exit.")
    print("=" * 60)

    # Load YOLO model
    model = YOLO(weights)

    # Open webcam
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Error: Could not open camera with index {camera_index}.")
        print("Try changing --cam index (e.g., --cam 1) if you have an external webcam.")
        return

    # Set camera resolution (optional request to hardware)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Warning: Failed to grab frame from camera.")
            break

        curr_time = time.time()
        fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
        prev_time = curr_time

        # Run inference
        results = model.predict(
            source=frame,
            conf=conf,
            imgsz=imgsz,
            device=device,
            verbose=False
        )

        annotated_frame = results[0].plot()

        # Parse detected components status
        detected_classes = [results[0].names[int(box.cls)] for box in results[0].boxes]
        
        status_text = []
        for comp in COMPONENTS:
            if f"{comp}A" in detected_classes:
                status_text.append(f"{comp}: PRESENT")
            elif f"{comp}N" in detected_classes:
                status_text.append(f"{comp}: ABSENT")
            else:
                status_text.append(f"{comp}: ?")

        # Draw HUD dashboard
        cv2.rectangle(annotated_frame, (10, 10), (700, 75), (20, 20, 20), -1)
        cv2.putText(
            annotated_frame,
            f"FPS: {fps:.1f} | Big Components Inspection",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 255),
            2
        )
        cv2.putText(
            annotated_frame,
            " | ".join(status_text),
            (20, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1
        )

        cv2.imshow("Big Components AOI Inspection - Webcam", annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # 'q' or ESC
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Webcam stream stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Big Components Inspection on Webcam")
    parser.add_argument("--weights", type=str, default="runs/train/weights/best.pt", help="Path to model weights")
    parser.add_argument("--cam", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument("--conf", type=float, default=0.40, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution")
    parser.add_argument("--device", type=str, default="0", help="GPU index or 'cpu'")

    args = parser.parse_args()
    run_webcam(
        weights=args.weights,
        camera_index=args.cam,
        conf=args.conf,
        imgsz=args.imgsz,
        device=args.device
    )
