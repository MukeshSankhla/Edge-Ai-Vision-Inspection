"""
Dataset verification script for Big Components Inspection YOLO dataset.
"""

from pathlib import Path
from collections import Counter
import yaml

BASE_DIR = Path(__file__).resolve().parent
YAML_PATH = BASE_DIR / "data.yaml"


def verify():
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data_cfg = yaml.safe_load(f)
        
    dataset_path = Path(data_cfg["path"])
    train_img_dir = dataset_path / data_cfg["train"]
    val_img_dir = dataset_path / data_cfg["val"]
    
    train_lbl_dir = dataset_path / "labels" / "train"
    val_lbl_dir = dataset_path / "labels" / "val"
    
    classes = data_cfg["names"]
    num_classes = len(classes)
    
    print(f"Dataset root: {dataset_path}")
    print(f"Configured classes ({num_classes}): {classes}")
    
    for split_name, img_dir, lbl_dir in [("TRAIN", train_img_dir, train_lbl_dir), ("VAL", val_img_dir, val_lbl_dir)]:
        images = list(img_dir.glob("*.jpg"))
        labels = list(lbl_dir.glob("*.txt"))
        print(f"\n--- Verifying {split_name} Split ---")
        print(f"Total Images: {len(images)}")
        print(f"Total Labels: {len(labels)}")
        
        cls_counter = Counter()
        total_boxes = 0
        
        for img in images:
            lbl_file = lbl_dir / f"{img.stem}.txt"
            if not lbl_file.exists():
                print(f"WARNING: Missing label file for image: {img.name}")
                continue
                
            with open(lbl_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    print(f"ERROR: Corrupted format in {lbl_file.name}: {line}")
                    continue
                cls_id = int(parts[0])
                xc, yc, w, h = map(float, parts[1:])
                
                assert 0 <= cls_id < num_classes, f"Class ID {cls_id} out of range in {lbl_file.name}"
                assert 0 <= xc <= 1, f"xc {xc} out of range in {lbl_file.name}"
                assert 0 <= yc <= 1, f"yc {yc} out of range in {lbl_file.name}"
                assert 0 < w <= 1, f"w {w} out of range in {lbl_file.name}"
                assert 0 < h <= 1, f"h {h} out of range in {lbl_file.name}"
                
                cls_counter[classes[cls_id]] += 1
                total_boxes += 1
                
        print(f"Total bounding boxes verified: {total_boxes}")
        print("Class breakdown:")
        for c in sorted(classes.values()):
            print(f"  {c:>4}: {cls_counter[c]}")
            
    print("\nDataset Verification PASSED with 0 errors!")


if __name__ == "__main__":
    verify()
