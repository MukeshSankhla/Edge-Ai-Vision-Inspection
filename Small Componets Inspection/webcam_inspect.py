"""
Real-time Webcam Inspection for Small Components Inspection using trained YOLO model.
Press 'q' or 'ESC' to exit.
"""
import cv2
import argparse
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=str, default="weights/best.onnx")
    parser.add_argument("--cam", type=int, default=0)
    parser.add_argument("--conf", type=float, default=0.35)
    args = parser.parse_args()
    
    model = YOLO(args.weights, task="detect")
    cap = cv2.VideoCapture(args.cam)
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
        res = model.predict(source=frame, conf=args.conf, verbose=False)
        ann = res[0].plot()
        detected = [res[0].names[int(b.cls)] for b in res[0].boxes]
        present = sum(1 for d in detected if d.endswith('A'))
        absent = sum(1 for d in detected if d.endswith('N'))
        
        cv2.rectangle(ann, (10, 10), (600, 70), (20, 20, 20), -1)
        cv2.putText(ann, f"SMALL COMPONENTS: {len(detected)} detected", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(ann, f"Present: {present} | Absent: {absent}", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    
        cv2.imshow("Small Components Inspection - Live Stream", ann)
        if (cv2.waitKey(1) & 0xFF) in (ord('q'), 27): break
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
