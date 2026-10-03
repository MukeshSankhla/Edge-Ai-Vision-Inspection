"""
Convert MakeSense CSV annotations to YOLO format.
Dataset: Big Components Inspection
"""

import os
import csv
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
CSV_PATH = DATASET_DIR / "labels_makesense.csv"
TRAIN_DIR = DATASET_DIR / "train"
TEST_DIR = DATASET_DIR / "test"

YOLO_DIR = BASE_DIR / "yolo_dataset"
YOLO_IMG_TRAIN = YOLO_DIR / "images" / "train"
YOLO_IMG_VAL = YOLO_DIR / "images" / "val"
YOLO_LBL_TRAIN = YOLO_DIR / "labels" / "train"
YOLO_LBL_VAL = YOLO_DIR / "labels" / "val"

# Defined Class List (Alphabetical order of the 12 inspection classes)
CLASSES = [
    "C1A", "C1N",
    "C2A", "C2N",
    "IA", "IN",
    "PA", "PN",
    "SA", "SN",
    "UA", "UN"
]
CLASS_TO_IDX = {cls_name: idx for idx, cls_name in enumerate(CLASSES)}


def setup_directories():
    for d in [YOLO_IMG_TRAIN, YOLO_IMG_VAL, YOLO_LBL_TRAIN, YOLO_LBL_VAL]:
        d.mkdir(parents=True, exist_ok=True)


def load_annotations(csv_path):
    annotations = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_name = row["image_name"]
            if img_name not in annotations:
                annotations[img_name] = []
            annotations[img_name].append({
                "label": row["label_name"],
                "x": float(row["bbox_x"]),
                "y": float(row["bbox_y"]),
                "w": float(row["bbox_width"]),
                "h": float(row["bbox_height"]),
                "img_w": float(row["image_width"]),
                "img_h": float(row["image_height"])
            })
    return annotations


def convert_bbox_to_yolo(bbox):
    # MakeSense bbox: top-left x, top-left y, width, height
    x_center = (bbox["x"] + bbox["w"] / 2.0) / bbox["img_w"]
    y_center = (bbox["y"] + bbox["h"] / 2.0) / bbox["img_h"]
    w_norm = bbox["w"] / bbox["img_w"]
    h_norm = bbox["h"] / bbox["img_h"]
    
    # Clamp bounding box values between 0.0 and 1.0 to ensure valid YOLO labels
    x_center = max(0.0, min(1.0, x_center))
    y_center = max(0.0, min(1.0, y_center))
    w_norm = max(0.0, min(1.0, w_norm))
    h_norm = max(0.0, min(1.0, h_norm))
    
    return x_center, y_center, w_norm, h_norm


def process_split(src_dir, dest_img_dir, dest_lbl_dir, annotations, split_name):
    img_files = [f for f in os.listdir(src_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"Processing {split_name}: {len(img_files)} images found.")
    
    label_count = 0
    for img_file in img_files:
        # Copy image
        src_img_path = src_dir / img_file
        dest_img_path = dest_img_dir / img_file
        shutil.copy2(src_img_path, dest_img_path)
        
        # Prepare label txt file
        stem = Path(img_file).stem
        dest_txt_path = dest_lbl_dir / f"{stem}.txt"
        
        img_annos = annotations.get(img_file, [])
        lines = []
        for anno in img_annos:
            cls_name = anno["label"]
            if cls_name not in CLASS_TO_IDX:
                raise ValueError(f"Unknown class '{cls_name}' found in {img_file}")
            cls_idx = CLASS_TO_IDX[cls_name]
            xc, yc, w, h = convert_bbox_to_yolo(anno)
            lines.append(f"{cls_idx} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
            label_count += 1
            
        with open(dest_txt_path, "w", encoding="utf-8") as lf:
            lf.write("\n".join(lines) + ("\n" if lines else ""))
            
    print(f"Finished {split_name}: copied {len(img_files)} images, wrote {label_count} bounding boxes.")


def generate_data_yaml():
    yaml_path = BASE_DIR / "data.yaml"
    names_dict = "\n".join([f"  {idx}: {cls_name}" for idx, cls_name in enumerate(CLASSES)])
    yaml_content = f"""# Big Components Inspection - YOLO Dataset Configuration
path: {YOLO_DIR.as_posix()}
train: images/train
val: images/val

names:
{names_dict}
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"Generated data configuration at: {yaml_path}")


def main():
    print("Starting MakeSense CSV to YOLO dataset conversion...")
    setup_directories()
    annotations = load_annotations(CSV_PATH)
    print(f"Loaded annotations for {len(annotations)} images from CSV.")
    
    process_split(TRAIN_DIR, YOLO_IMG_TRAIN, YOLO_LBL_TRAIN, annotations, "TRAIN")
    process_split(TEST_DIR, YOLO_IMG_VAL, YOLO_LBL_VAL, annotations, "VAL/TEST")
    
    generate_data_yaml()
    print("Dataset conversion completed successfully!")


if __name__ == "__main__":
    main()
