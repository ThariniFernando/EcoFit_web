import os
import json
import numpy as np
import pandas as pd
import torch
from torch.utils.data import TensorDataset, DataLoader
from sklearn.metrics import classification_report, confusion_matrix

from ml.config_ml import (
    DATASET_CSV, MODEL_DIR, LSTM_MODEL_PATH, SCALER_PATH,
    TIME_COL, WARD_COL, LABEL_COL, HISTORY_LEN,
    LABEL_TO_ID, LEAKAGE_COLS
)
from ml.dataset import (
    select_feature_cols, fit_scaler, apply_scaler,
    build_windows, time_split_with_overlap
)
from ml.model_lstm import LSTMClassifier


def train():
    os.makedirs(MODEL_DIR, exist_ok=True)

    df = pd.read_csv(DATASET_CSV)

    # Parse label strings -> ids
    df[LABEL_COL] = df[LABEL_COL].astype(str).str.upper().map(LABEL_TO_ID)
    df[LABEL_COL] = df[LABEL_COL].astype(int)

    # Parse time
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], utc=True, errors="coerce")
    df = df.dropna(subset=[TIME_COL])

    feature_cols = select_feature_cols(df, TIME_COL, WARD_COL, LABEL_COL, LEAKAGE_COLS)

    # Split with overlap
    train_df, val_df, test_df = time_split_with_overlap(df, TIME_COL, history_len=HISTORY_LEN)

    # Fit scaler ONLY on train
    scaler = fit_scaler(train_df, feature_cols)
    with open(SCALER_PATH, "w", encoding="utf-8") as f:
        json.dump({"feature_cols": feature_cols, "scaler": scaler}, f, indent=2)

    # Build windows
    X_train, y_train = build_windows(train_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)
    X_val, y_val = build_windows(val_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)
    X_test, y_test = build_windows(test_df, feature_cols, LABEL_COL, WARD_COL, TIME_COL, HISTORY_LEN)

    # Scale
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)
    X_test = apply_scaler(X_test, scaler)

    # Torch loaders
    train_loader = DataLoader(TensorDataset(torch.tensor(X_train), torch.tensor(y_train)), batch_size=64, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.tensor(X_val), torch.tensor(y_val)), batch_size=256, shuffle=False)
    test_loader = DataLoader(TensorDataset(torch.tensor(X_test), torch.tensor(y_test)), batch_size=256, shuffle=False)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LSTMClassifier(input_size=len(feature_cols)).to(device)

    # Loss + optimizer
    loss_fn = torch.nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)

    best_val = 0.0
    patience = 3
    bad = 0

    for epoch in range(1, 16):
        model.train()
        total = 0.0
        n = 0

        for xb, yb in train_loader:
            xb = xb.to(device).float()
            yb = yb.to(device).long()

            opt.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

            total += float(loss.item()) * xb.size(0)
            n += xb.size(0)

        train_loss = total / max(n, 1)

        # validate
        model.eval()
        correct = 0
        totaln = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device).float()
                yb = yb.to(device).long()
                pred = model(xb).argmax(1)
                correct += int((pred == yb).sum().item())
                totaln += yb.size(0)

        val_acc = correct / max(totaln, 1)
        print(f"Epoch {epoch:02d} | train_loss={train_loss:.4f} | val_acc={val_acc:.4f}")

        if val_acc > best_val:
            best_val = val_acc
            bad = 0
            torch.save({"state_dict": model.state_dict(), "input_size": len(feature_cols)}, LSTM_MODEL_PATH)
            print("✅ saved best model:", LSTM_MODEL_PATH)
        else:
            bad += 1
            if bad >= patience:
                print("⛔ early stopping")
                break

    # TEST REPORT
    ckpt = torch.load(LSTM_MODEL_PATH, map_location=device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    y_true = []
    y_pred = []
    with torch.no_grad():
        for xb, yb in test_loader:
            xb = xb.to(device).float()
            pred = model(xb).argmax(1).cpu().numpy().tolist()
            y_pred.extend(pred)
            y_true.extend(yb.numpy().tolist())

    print("\nConfusion Matrix:\n", confusion_matrix(y_true, y_pred))
    print("\nClassification Report:\n", classification_report(y_true, y_pred, digits=4))

    return {"status": "ok", "best_val_acc": best_val, "features": feature_cols}


if __name__ == "__main__":
    print(train())