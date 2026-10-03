"""
Real-time Webcam Inspection for PCB Inspection using trained YOLO model.
Press 'q' or 'ESC' to exit.
"""
import cv2
import argparse
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, default="weights/best.onnx")
    parser.add_argument("--cam", type=int, default=0)
    parser.add_argument("--conf", type=float, default=0.30)
    args = parser.parse_args()
    
    model = YOLO(args.weights, task="detect")
    cap = cv2.VideoCapture(args.cam)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        res = model.predict(source=frame, conf=args.conf, verbose=False)
        ann = res[0].plot()
        issues = len(res[0].boxes)
        color = (0, 0, 255) if issues > 0 else (0, 255, 0)
        status = f"DEFECTS DETECTED: {issues}" if issues > 0 else "PCB STATUS: OK"
        cv2.putText(ann, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        cv2.imshow("PCB Inspection - Live Stream", ann)
        if (cv2.waitKey(1) & 0xFF) in (ord('q'), 27): break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
