"""
ONNX Model Export & Verification Script for Big Components Inspection.
Exports trained YOLO PyTorch weights to an optimized ONNX model and verifies
its input/output tensor specifications using ONNX and ONNX Runtime.
"""

import argparse
import shutil
from pathlib import Path
import numpy as np
import onnx
import onnxruntime as ort
from ultralytics import YOLO

BASE_DIR = Path(__file__).resolve().parent


def export_and_verify_onnx(
    weights_path="runs/train/weights/best.pt",
    output_dir="weights",
    imgsz=640,
    opset=17,
    dynamic=False,
    half=False,
    simplify=True
):
    weights = Path(weights_path)
    if not weights.exists():
        raise FileNotFoundError(f"Weights file not found at: {weights.resolve()}")

    print("=" * 65)
    print("  Big Components Inspection - YOLO ONNX Model Exporter")
    print("=" * 65)
    print(f"Input Weights:     {weights}")
    print(f"Image Dimension:   {imgsz}x{imgsz}")
    print(f"ONNX Opset:        {opset}")
    print(f"Dynamic Axes:      {dynamic}")
    print(f"FP16 Half:         {half}")
    print(f"Simplify / Slim:   {simplify}")
    print("=" * 65)

    # 1. Load YOLO PyTorch model
    print("\n[Step 1/4] Loading trained PyTorch model...")
    model = YOLO(str(weights))
    print(f"Model loaded: {model.task} with {len(model.names)} classes: {list(model.names.values())}")

    # 2. Export to ONNX via Ultralytics
    print("\n[Step 2/4] Exporting to ONNX format...")
    exported_path_str = model.export(
        format="onnx",
        imgsz=imgsz,
        opset=opset,
        dynamic=dynamic,
        half=half,
        simplify=simplify
    )
    exported_path = Path(exported_path_str)
    print(f"Export completed: {exported_path} ({exported_path.stat().st_size / 1e6:.2f} MB)")

    # Copy to designated output directory (e.g. weights/best.onnx)
    dest_dir = Path(output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target_onnx = dest_dir / "best.onnx"
    shutil.copy2(exported_path, target_onnx)
    print(f"Copied ONNX model to primary weights folder: {target_onnx}")

    # 3. Validate ONNX structure with ONNX library
    print("\n[Step 3/4] Validating ONNX model graph integrity...")
    onnx_model = onnx.load(str(target_onnx))
    onnx.checker.check_model(onnx_model)
    print("ONNX model checker: SUCCESS (Graph topology is valid and compliant)")

    # 4. Test inference using ONNX Runtime
    print("\n[Step 4/4] Verifying execution with ONNX Runtime...")
    session = ort.InferenceSession(str(target_onnx), providers=["CPUExecutionProvider"])
    
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    
    print("\n--- Model I/O Specifications ---")
    for i, inp in enumerate(inputs):
        print(f"  Input  [{i}]: Name = '{inp.name}', Shape = {inp.shape}, Type = {inp.type}")
    for i, out in enumerate(outputs):
        print(f"  Output [{i}]: Name = '{out.name}', Shape = {out.shape}, Type = {out.type}")

    # Run dummy tensor inference test
    input_name = inputs[0].name
    input_shape = [1, 3, imgsz, imgsz] if not dynamic else [1, 3, imgsz, imgsz]
    dtype = np.float16 if half else np.float32
    dummy_input = np.random.rand(*input_shape).astype(dtype)

    raw_output = session.run(None, {input_name: dummy_input})
    output_tensor = raw_output[0]
    print(f"\nRuntime Test Inference Result Shape: {output_tensor.shape}")
    print(f"Shape breakdown: [batch={output_tensor.shape[0]}, 4_bbox_coords + {output_tensor.shape[1] - 4}_classes = {output_tensor.shape[1]}, anchors={output_tensor.shape[2]}]")

    print("\n" + "=" * 65)
    print("ONNX Model Export & Verification Successfully Completed!")
    print(f"Exported File Locations:")
    print(f"  1. {exported_path.resolve()}")
    print(f"  2. {target_onnx.resolve()}")
    print("=" * 65)
    return str(target_onnx)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export YOLO model to ONNX format")
    parser.add_argument("--weights", type=str, default="runs/train/weights/best.pt", help="Path to best.pt weights")
    parser.add_argument("--output-dir", type=str, default="weights", help="Directory to copy exported ONNX")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image dimension (default: 640)")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version (default: 17)")
    parser.add_argument("--dynamic", action="store_true", help="Enable dynamic batch and spatial axes")
    parser.add_argument("--half", action="store_true", help="Export in FP16 precision")
    parser.add_argument("--no-simplify", action="store_true", help="Disable onnxslim/simplify")

    args = parser.parse_args()
    export_and_verify_onnx(
        weights_path=args.weights,
        output_dir=args.output_dir,
        imgsz=args.imgsz,
        opset=args.opset,
        dynamic=args.dynamic,
        half=args.half,
        simplify=not args.no_simplify
    )
