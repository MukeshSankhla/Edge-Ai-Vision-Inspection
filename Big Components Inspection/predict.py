"""
Inference script for Big Components Inspection using trained YOLO model.
Runs predictions on test images and visualizes detected components.
"""

import argparse
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent


def run_inference(
    weights="runs/train/weights/best.pt",
    source="yolo_dataset/images/val",
    output="runs/predict_test",
    conf=0.25,
    save=True
):
    print("=" * 60)
    print("  Big Components Inspection - YOLO Inference & Testing")
    print("=" * 60)
    print(f"Model Weights:  {weights}")
    print(f"Source Folder:  {source}")
    print(f"Output Folder:  {output}")
    print(f"Confidence:     {conf}")
    print("=" * 60)

    model = YOLO(weights)
    results = model.predict(
        source=str(source),
        conf=conf,
        save=save,
        project=str(Path(output).parent),
        name=Path(output).name,
        exist_ok=True
    )

    print(f"\nCompleted inference on {len(results)} images.")
    for idx, r in enumerate(results):
        img_name = Path(r.path).name
        boxes = r.boxes
        detected_classes = [r.names[int(cls_id)] for cls_id in boxes.cls]
        confs = [f"{float(c):.2f}" for c in boxes.conf]
        print(f"[{idx+1}/{len(results)}] {img_name}:")
        print(f"    Detected ({len(detected_classes)}): {list(zip(detected_classes, confs))}")

    print(f"\nVisual results saved to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run inference with trained YOLO model")
    parser.add_argument("--weights", type=str, default="runs/train/weights/best.pt")
    parser.add_argument("--source", type=str, default="yolo_dataset/images/val")
    parser.add_argument("--output", type=str, default="runs/predict_test")
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    run_inference(
        weights=args.weights,
        source=args.source,
        output=args.output,
        conf=args.conf
    )
