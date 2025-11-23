# training/train_ccs.py
# Python 3.9 compatible. Comments in English.
import argparse
from pathlib import Path
from loguru import logger

# pip install ultralytics
from ultralytics import YOLO


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("CCS fine-tuning (Ultralytics YOLO)")
    p.add_argument("--data", type=str, required=True, help="Path to YOLO data.yaml")
    p.add_argument("--model", type=str, default="yolov8n.pt", help="Weights or model yaml (e.g., yolov8n.pt)")
    p.add_argument("--img", type=int, default=640, help="Train/val image size")
    p.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    p.add_argument("--batch", type=int, default=16, help="Batch size per device")
    p.add_argument("--device", type=str, default="cuda:0", help="Device: 'cuda:0' or 'cpu'")
    p.add_argument("--workers", type=int, default=8, help="Dataloader workers")
    p.add_argument("--save_dir", type=str, default="runs/train/ccs", help="Save dir")
    p.add_argument("--seed", type=int, default=0, help="Seed for reproducibility")
    p.add_argument("--lr0", type=float, default=0.01, help="Initial learning rate")
    p.add_argument("--lrf", type=float, default=0.01, help="Final lr fraction")
    p.add_argument("--weight_decay", type=float, default=0.0005, help="Weight decay")
    p.add_argument("--mosaic", type=float, default=0.5, help="Mosaic probability")
    p.add_argument("--mixup", type=float, default=0.1, help="Mixup probability")
    p.add_argument("--hsv", type=float, default=0.015, help="HSV aug intensity")
    p.add_argument("--degrees", type=float, default=0.0, help="Random rotation degrees")
    p.add_argument("--translate", type=float, default=0.1, help="Random translate")
    p.add_argument("--scale_aug", type=float, default=0.5, help="Random scale range")
    p.add_argument("--shear", type=float, default=0.0, help="Random shear degrees")
    p.add_argument("--patience", type=int, default=30, help="Early-stop patience")
    p.add_argument("--rect", action="store_true", help="Rectangular training for aspect ratio stability")
    p.add_argument("--freeze", type=int, default=0, help="Freeze N layers from backbone (0=off)")
    p.add_argument("--resume", action="store_true", help="Resume from last")
    return p


def main() -> None:
    args = build_parser().parse_args()
    Path(args.save_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Start fine-tuning: data={}, model={}, img={}, epochs={}",
                args.data, args.model, args.img, args.epochs)

    model = YOLO(args.model)

    overrides = {
        "data": args.data,
        "imgsz": args.img,
        "epochs": args.epochs,
        "batch": args.batch,
        "device": args.device,
        "workers": args.workers,
        "project": args.save_dir,
        "seed": args.seed,
        # optimizer / schedule
        "lr0": args.lr0,
        "lrf": args.lrf,
        "weight_decay": args.weight_decay,
        # augmentations (small-object friendly tuning knobs)
        "mosaic": args.mosaic,
        "mixup": args.mixup,
        "hsv_h": args.hsv,
        "hsv_s": args.hsv,
        "hsv_v": args.hsv,
        "degrees": args.degrees,
        "translate": args.translate,
        "scale": args.scale_aug,
        "shear": args.shear,
        # training behavior
        "patience": args.patience,
        "rect": args.rect,
        "resume": args.resume,
        "save": True,
        "plots": True,
        "exist_ok": True,
        "freeze": args.freeze
    }

    # Note: Ultralytics uses TAL assigner + DFL/CIoU inside by default.
    # We focus on dataset composition, augmentations, and image size.

    results = model.train(overrides=overrides)
    logger.info("Training finished. Results keys: {}", list(results.keys()) if hasattr(results, "keys") else "ok")


if __name__ == "__main__":
    main()
