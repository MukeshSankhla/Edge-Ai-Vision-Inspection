"""
Generate representative features (.npy) for Edge Impulse model upload and INT8 quantization.
Prepares normalized calibration tensors matching YOLO input specification [N, 3, 640, 640].
"""

import argparse
from pathlib import Path
import cv2
import numpy as np
from ultralytics.data.augment import LetterBox

BASE_DIR = Path(__file__).resolve().parent


def preprocess_image(img_path, imgsz=640):
    """
    Apply standard YOLO letterboxing, BGR-to-RGB conversion, and [0.0, 1.0] normalization.
    Returns tensor with shape (3, imgsz, imgsz) and dtype np.float32.
    """
    img = cv2.imread(str(img_path))
    if img is None:
        raise ValueError(f"Failed to read image at: {img_path}")

    # 1. Letterbox resize with padding to target square dimension
    letterbox = LetterBox((imgsz, imgsz), auto=False, stride=32)
    img_lb = letterbox(image=img)

    # 2. Convert BGR (OpenCV) to RGB (PyTorch/YOLO/ONNX)
    img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)

    # 3. Normalize pixel values from [0, 255] to [0.0, 1.0]
    img_norm = img_rgb.astype(np.float32) / 255.0

    # 4. Transpose from HWC (Height, Width, Channels) to CHW (Channels, Height, Width)
    img_chw = np.transpose(img_norm, (2, 0, 1))
    return img_chw


def generate_representative_features(
    source="all",
    imgsz=640,
    output_path="representative_features.npy",
    weights_copy_path="weights/representative_features.npy"
):
    print("=" * 65)
    print("  Big Components Inspection - Edge Impulse Feature Generator")
    print("=" * 65)
    print(f"Dataset Source:     {source}")
    print(f"Target Resolution:  {imgsz}x{imgsz}")
    print(f"Output File:        {output_path}")
    print("=" * 65)

    # Collect source images
    val_dir = BASE_DIR / "yolo_dataset" / "images" / "val"
    train_dir = BASE_DIR / "yolo_dataset" / "images" / "train"

    image_paths = []
    if source in ("val", "validation"):
        image_paths = sorted(list(val_dir.glob("*.jpg")))
    elif source in ("train", "training"):
        image_paths = sorted(list(train_dir.glob("*.jpg")))
    elif source in ("all", "both"):
        # Combine both validation and training for optimal quantization calibration
        image_paths = sorted(list(val_dir.glob("*.jpg")) + list(train_dir.glob("*.jpg")))
    else:
        src_path = Path(source)
        if src_path.is_dir():
            image_paths = sorted(list(src_path.glob("*.jpg")) + list(src_path.glob("*.png")))
        else:
            raise ValueError(f"Unknown source option: {source}")

    if not image_paths:
        raise FileNotFoundError(f"No images found for source '{source}'")

    print(f"\nProcessing {len(image_paths)} images for calibration dataset...")

    feature_list = []
    for idx, p in enumerate(image_paths):
        tensor = preprocess_image(p, imgsz=imgsz)
        feature_list.append(tensor)
        if (idx + 1) % 10 == 0 or (idx + 1) == len(image_paths):
            print(f"  Processed [{idx+1}/{len(image_paths)}] {p.name}")

    # Stack into single numpy array of shape (N, 3, imgsz, imgsz)
    features_array = np.stack(feature_list, axis=0)

    print("\n--- Calibration Array Specifications ---")
    print(f"  Array Shape:   {features_array.shape} (N_samples={features_array.shape[0]}, Channels={features_array.shape[1]}, H={features_array.shape[2]}, W={features_array.shape[3]})")
    print(f"  Data Type:     {features_array.dtype}")
    print(f"  Value Range:   [{features_array.min():.4f}, {features_array.max():.4f}]")
    print(f"  Mean Value:    {features_array.mean():.4f}")
    print(f"  Std Deviation: {features_array.std():.4f}")

    # Save to primary destination
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(out_file), features_array)
    file_size_mb = out_file.stat().st_size / 1e6
    print(f"\nSaved representative features to: {out_file.resolve()} ({file_size_mb:.2f} MB)")

    # Save copy to weights/ folder if requested
    if weights_copy_path:
        copy_file = Path(weights_copy_path)
        copy_file.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(copy_file), features_array)
        print(f"Saved secondary copy to:         {copy_file.resolve()}")

    # Verify loading integrity
    loaded = np.load(str(out_file))
    assert loaded.shape == features_array.shape, "Integrity check failed: Shape mismatch!"
    assert loaded.dtype == features_array.dtype, "Integrity check failed: Dtype mismatch!"
    print("Verification check: SUCCESS (File reloaded and validated perfectly)")

    print("\n" + "=" * 65)
    print("Ready to upload to Edge Impulse:")
    print("  1. Model File:                   weights/best.onnx")
    print(f"  2. Representative Features File: {output_path}")
    print("=" * 65)
    return str(out_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate representative features .npy for Edge Impulse")
    parser.add_argument("--source", type=str, default="all", choices=["val", "train", "all"], help="Image source ('val', 'train', or 'all')")
    parser.add_argument("--imgsz", type=int, default=640, help="Input dimension matching model (default: 640)")
    parser.add_argument("--output", type=str, default="representative_features.npy", help="Output .npy file path")

    args = parser.parse_args()
    generate_representative_features(
        source=args.source,
        imgsz=args.imgsz,
        output_path=args.output
    )
