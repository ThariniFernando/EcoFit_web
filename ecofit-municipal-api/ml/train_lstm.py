import os
import json
import csv
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt

from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    r2_score,
    mean_squared_error,
    mean_absolute_error,
)

from ml.config_ml import (
    DATASET_CSV,
    MODEL_DIR,
    LSTM_MODEL_PATH,
    SCALER_PATH,
    TIME_COL,
    WARD_COL,
    LABEL_COL,
    HISTORY_LEN,
    LABEL_TO_ID,
    LEAKAGE_COLS,
)
from ml.dataset import (
    select_feature_cols,
    fit_scaler,
    apply_scaler,
    build_windows,
    time_split_with_overlap,
)
from ml.model_lstm import LSTMClassifier


TRAINING_CURVE_PATH = os.path.join(MODEL_DIR, "lstm_training_curve.png")
LOSS_CURVE_PATH = os.path.join(MODEL_DIR, "lstm_loss_curve.png")
EPOCH_METRICS_JSON = os.path.join(MODEL_DIR, "lstm_epoch_metrics.json")
EPOCH_METRICS_CSV = os.path.join(MODEL_DIR, "lstm_epoch_metrics.csv")
TEST_METRICS_JSON = os.path.join(MODEL_DIR, "lstm_test_metrics.json")
CONFUSION_MATRIX_CSV = os.path.join(MODEL_DIR, "lstm_confusion_matrix.csv")
CLASSIFICATION_REPORT_TXT = os.path.join(MODEL_DIR, "lstm_classification_report.txt")
REGRESSION_STYLE_METRICS_JSON = os.path.join(MODEL_DIR, "lstm_regression_style_metrics.json")


def evaluate_model(model, loader, loss_fn, device):
    model.eval()

    total_loss = 0.0
    total_count = 0
    correct = 0

    y_true = []
    y_pred = []

    with torch.no_grad():
        for xb, yb in loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()

            logits = model(xb)
            loss = loss_fn(logits, yb)
            preds = logits.argmax(1)

            total_loss += float(loss.item()) * xb.size(0)
            total_count += xb.size(0)
            correct += int((preds == yb).sum().item())

            y_true.extend(yb.cpu().numpy().tolist())
            y_pred.extend(preds.cpu().numpy().tolist())

    avg_loss = total_loss / max(total_count, 1)
    acc = correct / max(total_count, 1)

    return {
        "loss": avg_loss,
        "acc": acc,
        "y_true": y_true,
        "y_pred": y_pred,
    }


def save_epoch_metrics_csv(history, path):
    fieldnames = ["epoch", "train_loss", "train_acc", "val_loss", "val_acc"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in history:
            writer.writerow(row)


def save_confusion_matrix_csv(cm, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in cm:
            writer.writerow(row)


def plot_accuracy_curves(history, save_path):
    epochs = [x["epoch"] for x in history]
    train_acc = [x["train_acc"] for x in history]
    val_acc = [x["val_acc"] for x in history]

    plt.figure(figsize=(10, 6))
    plt.plot(epochs, train_acc, label="Training Accuracy")
    plt.plot(epochs, val_acc, label="Validation Accuracy")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.title("Training and Validation Accuracy")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()


def plot_loss_curves(history, save_path):
    epochs = [x["epoch"] for x in history]
    train_loss = [x["train_loss"] for x in history]
    val_loss = [x["val_loss"] for x in history]

    plt.figure(figsize=(10, 6))
    plt.plot(epochs, train_loss, label="Training Loss")
    plt.plot(epochs, val_loss, label="Validation Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Training and Validation Loss")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    plt.close()


def compute_regression_style_metrics(y_true, y_pred):
    y_true_arr = np.array(y_true, dtype=np.float32)
    y_pred_arr = np.array(y_pred, dtype=np.float32)

    r2 = r2_score(y_true_arr, y_pred_arr)
    rmse = np.sqrt(mean_squared_error(y_true_arr, y_pred_arr))
    mae = mean_absolute_error(y_true_arr, y_pred_arr)

    # avoid divide by zero in MAPE
    denom = np.where(y_true_arr == 0, 1.0, y_true_arr)
    mape = np.mean(np.abs((y_true_arr - y_pred_arr) / denom)) * 100.0

    return {
        "r2": round(float(r2), 6),
        "rmse": round(float(rmse), 6),
        "mae": round(float(mae), 6),
        "mape_percent": round(float(mape), 6),
    }


def train():
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = pd.read_csv(DATASET_CSV)

    # Parse label strings -> ids
    df[LABEL_COL] = df[LABEL_COL].astype(str).str.upper().map(LABEL_TO_ID)
    df = df.dropna(subset=[LABEL_COL])
    df[LABEL_COL] = df[LABEL_COL].astype(int)

    # Parse time
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], utc=True, errors="coerce")
    df = df.dropna(subset=[TIME_COL])

    feature_cols = select_feature_cols(df, TIME_COL, WARD_COL, LABEL_COL, LEAKAGE_COLS)

    # Split with overlap
    train_df, val_df, test_df = time_split_with_overlap(
        df,
        TIME_COL,
        history_len=HISTORY_LEN
    )

    # Fit scaler ONLY on train
    scaler = fit_scaler(train_df, feature_cols)
    with open(SCALER_PATH, "w", encoding="utf-8") as f:
        json.dump({"feature_cols": feature_cols, "scaler": scaler}, f, indent=2)

    # Build windows
    X_train, y_train = build_windows(train_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)
    X_val, y_val = build_windows(val_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)
    X_test, y_test = build_windows(test_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)

    if len(X_train) == 0 or len(X_val) == 0 or len(X_test) == 0:
        raise ValueError("One of the datasets has zero windows. Check dataset generation and split logic.")

    # Scale
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)
    X_test = apply_scaler(X_test, scaler)

    # Dataloaders
    train_loader = DataLoader(
        TensorDataset(torch.tensor(X_train), torch.tensor(y_train)),
        batch_size=64,
        shuffle=True,
    )
    val_loader = DataLoader(
        TensorDataset(torch.tensor(X_val), torch.tensor(y_val)),
        batch_size=256,
        shuffle=False,
    )
    test_loader = DataLoader(
        TensorDataset(torch.tensor(X_test), torch.tensor(y_test)),
        batch_size=256,
        shuffle=False,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LSTMClassifier(input_size=len(feature_cols)).to(device)

    loss_fn = torch.nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    best_val = 0.0
    patience = 3
    bad = 0

    history = []

    for epoch in range(1, 16):
        model.train()

        total_loss = 0.0
        total_count = 0
        correct = 0

        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()

            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

            preds = logits.argmax(1)

            total_loss += float(loss.item()) * xb.size(0)
            total_count += xb.size(0)
            correct += int((preds == yb).sum().item())

        train_loss = total_loss / max(total_count, 1)
        train_acc = correct / max(total_count, 1)

        # Validation
        val_result = evaluate_model(model, val_loader, loss_fn, device)
        val_loss = val_result["loss"]
        val_acc = val_result["acc"]

        row = {
            "epoch": epoch,
            "train_loss": round(train_loss, 6),
            "train_acc": round(train_acc, 6),
            "val_loss": round(val_loss, 6),
            "val_acc": round(val_acc, 6),
        }
        history.append(row)

        print(
            f"Epoch {epoch:02d} | "
            f"train_loss={train_loss:.4f} | train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} | val_acc={val_acc:.4f}"
        )

        if val_acc > best_val:
            best_val = val_acc
            bad = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "input_size": len(feature_cols),
                },
                LSTM_MODEL_PATH,
            )
            print("✅ saved best model:", LSTM_MODEL_PATH)
        else:
            bad += 1
            if bad >= patience:
                print("⛔ early stopping")
                break

    # Save epoch history
    with open(EPOCH_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    save_epoch_metrics_csv(history, EPOCH_METRICS_CSV)
    plot_accuracy_curves(history, TRAINING_CURVE_PATH)
    plot_loss_curves(history, LOSS_CURVE_PATH)

    # Load best model for test
    ckpt = torch.load(LSTM_MODEL_PATH, map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    test_result = evaluate_model(model, test_loader, loss_fn, device)
    y_true = test_result["y_true"]
    y_pred = test_result["y_pred"]

    cm = confusion_matrix(y_true, y_pred)
    report = classification_report(y_true, y_pred, digits=4)

    # Classification metrics
    test_metrics = {
        "accuracy": round(accuracy_score(y_true, y_pred), 6),
        "precision_macro": round(precision_score(y_true, y_pred, average="macro", zero_division=0), 6),
        "recall_macro": round(recall_score(y_true, y_pred, average="macro", zero_division=0), 6),
        "f1_macro": round(f1_score(y_true, y_pred, average="macro", zero_division=0), 6),
        "best_val_acc": round(best_val, 6),
        "num_features": len(feature_cols),
        "num_train_windows": int(len(X_train)),
        "num_val_windows": int(len(X_val)),
        "num_test_windows": int(len(X_test)),
    }

    with open(TEST_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(test_metrics, f, indent=2)

    # Regression-style metrics
    regression_style_metrics = compute_regression_style_metrics(y_true, y_pred)
    with open(REGRESSION_STYLE_METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(regression_style_metrics, f, indent=2)

    save_confusion_matrix_csv(cm, CONFUSION_MATRIX_CSV)

    with open(CLASSIFICATION_REPORT_TXT, "w", encoding="utf-8") as f:
        f.write(report)

    print("\nConfusion Matrix:\n", cm)
    print("\nClassification Report:\n", report)

    print("\nClassification Metrics:")
    for k, v in test_metrics.items():
        print(f"{k}: {v}")

    print("\nRegression-Style Metrics:")
    for k, v in regression_style_metrics.items():
        print(f"{k}: {v}")

    print("\n✅ Saved files:")
    print("Training accuracy curve:", TRAINING_CURVE_PATH)
    print("Loss curve:", LOSS_CURVE_PATH)
    print("Epoch metrics JSON:", EPOCH_METRICS_JSON)
    print("Epoch metrics CSV:", EPOCH_METRICS_CSV)
    print("Test metrics JSON:", TEST_METRICS_JSON)
    print("Regression-style metrics JSON:", REGRESSION_STYLE_METRICS_JSON)
    print("Confusion matrix CSV:", CONFUSION_MATRIX_CSV)
    print("Classification report TXT:", CLASSIFICATION_REPORT_TXT)

    return {
        "status": "ok",
        "best_val_acc": best_val,
        "features": feature_cols,
        "training_curve": TRAINING_CURVE_PATH,
        "loss_curve": LOSS_CURVE_PATH,
        "epoch_metrics_json": EPOCH_METRICS_JSON,
        "epoch_metrics_csv": EPOCH_METRICS_CSV,
        "test_metrics_json": TEST_METRICS_JSON,
        "regression_style_metrics_json": REGRESSION_STYLE_METRICS_JSON,
    }


if __name__ == "__main__":
    print(train())