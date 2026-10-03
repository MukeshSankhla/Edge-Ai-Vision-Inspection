"""
YOLO Training Script for Big Components Inspection.
Uses Ultralytics YOLO11n on NVIDIA GPU.
"""

import argparse
from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent
DATA_YAML = BASE_DIR / "data.yaml"


def train_model(
    model_name="yolo11n.pt",
    epochs=80,
    imgsz=640,
    batch=8,
    device="0",
    patience=30,
    project="runs",
    name="train",
    export_onnx=True
):
    print("=" * 60)
    print("  Big Components Inspection - YOLO Model Training")
    print("=" * 60)
    print(f"Base Model:       {model_name}")
    print(f"Data Config:      {DATA_YAML}")
    print(f"Epochs:           {epochs}")
    print(f"Image Size:       {imgsz}")
    print(f"Batch Size:       {batch}")
    print(f"Device:           {device}")
    print(f"Patience:         {patience}")
    print(f"Target Output:    {project}/{name}")
    print("=" * 60)

    # 1. Initialize YOLO model with pretrained weights
    print(f"\n[Step 1/4] Loading base model '{model_name}'...")
    model = YOLO(model_name)

    # 2. Train the model
    # Note: fliplr=0.0 and flipud=0.0 are critical for PCB inspection
    # as component positions (e.g. C1 vs C2) are spatially fixed.
    print("\n[Step 2/4] Commencing model training...")
    train_results = model.train(
        data=str(DATA_YAML),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        patience=patience,
        fliplr=0.0,
        flipud=0.0,
        project=project,
        name=name,
        exist_ok=True,
        plots=True,
        save=True,
        verbose=True
    )
    print("\nTraining completed successfully!")

    # 3. Validate the model on validation set
    print("\n[Step 3/4] Running detailed evaluation on validation set...")
    val_results = model.val(
        data=str(DATA_YAML),
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=f"{name}_val",
        exist_ok=True,
        plots=True
    )

    print("\n--- Validation Performance Metrics ---")
    map50 = val_results.box.map50
    map50_95 = val_results.box.map
    precision = val_results.box.mp
    recall = val_results.box.mr
    print(f"Precision (P):       {precision:.4f}")
    print(f"Recall (R):          {recall:.4f}")
    print(f"mAP@0.5:             {map50:.4f}")
    print(f"mAP@0.5:0.95:        {map50_95:.4f}")

    # 4. Export model to ONNX for edge deployment
    if export_onnx:
        print("\n[Step 4/4] Exporting best model to ONNX format...")
        try:
            best_weight = Path(project) / name / "weights" / "best.pt"
            best_model = YOLO(str(best_weight))
            onnx_path = best_model.export(format="onnx", imgsz=imgsz, dynamic=False)
            print(f"Exported ONNX model to: {onnx_path}")
        except Exception as e:
            print(f"ONNX export notice: {e}")

    print("\n" + "=" * 60)
    print("Training and evaluation workflow complete!")
    print(f"Weights saved at: {Path(project) / name / 'weights'}")
    print("=" * 60)
    return train_results, val_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO for Big Components Inspection")
    parser.add_argument("--model", type=str, default="yolo11n.pt", help="Pretrained model weights")
    parser.add_argument("--epochs", type=int, default=80, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image dimension")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--device", type=str, default="0", help="CUDA device index or 'cpu'")
    parser.add_argument("--patience", type=int, default=30, help="Early stopping patience")
    parser.add_argument("--no-onnx", action="store_true", help="Skip ONNX export")
    
    args = parser.parse_args()
    train_model(
        model_name=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        patience=args.patience,
        project="runs",
        name="train",
        export_onnx=not args.no_onnx
    )
