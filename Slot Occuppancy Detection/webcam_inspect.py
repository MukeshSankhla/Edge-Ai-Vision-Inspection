"""
Real-time Webcam Inspection for Slot Occuppancy Detection using trained YOLO classification model.
Press 'q' or 'ESC' to exit.
"""
import cv2
import argparse
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, default="weights/best.onnx")
    parser.add_argument("--cam", type=int, default=0)
    args = parser.parse_args()
    
    model = YOLO(args.weights, task="classify")
    cap = cv2.VideoCapture(args.cam)
    
    color_map = {
        "Empty": (0, 165, 255),   # Orange
        "PCB": (255, 255, 0),     # Cyan
        "PCBA": (0, 255, 0)       # Green
    }
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        res = model.predict(source=frame, imgsz=224, verbose=False)
        top1_idx = res[0].probs.top1
        conf = float(res[0].probs.top1conf)
        class_name = res[0].names[top1_idx]
        
        color = color_map.get(class_name, (255, 255, 255))
        cv2.rectangle(frame, (10, 10), (500, 70), (20, 20, 20), -1)
        cv2.putText(frame, f"SLOT STATUS: {class_name} ({conf*100:.1f}%)", (25, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                    
        cv2.imshow("Slot Occuppancy Detection - Live Stream", frame)
        if (cv2.waitKey(1) & 0xFF) in (ord('q'), 27): break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
