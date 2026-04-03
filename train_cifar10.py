#!/usr/bin/env python3
"""
Train CIFAR-10 CNN and save weights in binary format for Zig benchmark.
"""

import numpy as np
import pickle
import tarfile
import os
import urllib.request
from datetime import datetime

# Download CIFAR-10 if needed
def download_cifar10():
    url = "https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz"
    filename = "cifar-10-python.tar.gz"

    if os.path.exists(filename):
        print(f"Found {filename}")
        return filename

    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, filename)
    print(f"Downloaded {filename}")
    return filename

# Extract CIFAR-10
def extract_cifar10(tar_path):
    if os.path.exists("cifar-10-batches-py"):
        print("cifar-10-batches-py already exists")
        return

    print("Extracting CIFAR-10...")
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(".")
    print("Extracted")

# Load CIFAR-10 data
def load_cifar10_data():
    def load_batch(filename):
        with open(f"cifar-10-batches-py/{filename}", "rb") as f:
            batch = pickle.load(f, encoding="latin1")
        data = batch["data"].astype(np.float32) / 255.0
        labels = np.array(batch["labels"])
        return data, labels

    # Load training data
    train_data = []
    train_labels = []
    for i in range(1, 6):
        data, labels = load_batch(f"data_batch_{i}")
        train_data.append(data)
        train_labels.append(labels)

    train_x = np.concatenate(train_data, axis=0)
    train_y = np.concatenate(train_labels, axis=0)

    # Load test data
    test_x, test_y = load_batch("test_batch")

    # Reshape: (N, 3072) -> (N, 3, 32, 32) -> (N, 32, 32, 3) for TensorFlow
    train_x = train_x.reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)
    test_x = test_x.reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)

    return (train_x, train_y), (test_x, test_y)

# Simple CNN model
class CNN:
    def __init__(self):
        # Conv1: 3x3x3 -> 16
        self.conv1_w = np.random.randn(3, 3, 3, 16).astype(np.float32) * np.sqrt(2.0 / (3 * 3 * 3))
        self.conv1_b = np.zeros(16, dtype=np.float32)

        # Conv2: 3x3x16 -> 32
        self.conv2_w = np.random.randn(3, 3, 16, 32).astype(np.float32) * np.sqrt(2.0 / (16 * 3 * 3))
        self.conv2_b = np.zeros(32, dtype=np.float32)

        # FC1: 2048 -> 128 (after 2x2 pooling twice: 32->16->8, so 8*8*32=2048)
        self.fc1_w = np.random.randn(2048, 128).astype(np.float32) * np.sqrt(2.0 / 2048)
        self.fc1_b = np.zeros(128, dtype=np.float32)

        # FC2: 128 -> 10
        self.fc2_w = np.random.randn(128, 10).astype(np.float32) * np.sqrt(2.0 / 128)
        self.fc2_b = np.zeros(10, dtype=np.float32)

    def conv2d(self, x, w, b, stride=1, padding=1):
        # Simplified conv2d
        N, H, W, C_in = x.shape
        kH, kW, C_in2, C_out = w.shape

        H_out = (H + 2 * padding - kH) // stride + 1
        W_out = (W + 2 * padding - kW) // stride + 1

        # Pad input
        x_pad = np.pad(x, ((0,0), (padding, padding), (padding, padding), (0,0)), mode='constant')

        out = np.zeros((N, H_out, W_out, C_out), dtype=np.float32)

        for n in range(N):
            for h in range(H_out):
                for w_idx in range(W_out):
                    for c_out in range(C_out):
                        for c_in in range(C_in):
                            for kh in range(kH):
                                for kw in range(kW):
                                    h_pad = h * stride + kh
                                    w_pad = w_idx * stride + kw
                                    out[n, h, w_idx, c_out] += x_pad[n, h_pad, w_pad, c_in] * w[kh, kw, c_in, c_out]
                        out[n, h, w_idx, c_out] += b[c_out]
        return out

    def relu(self, x):
        return np.maximum(0, x)

    def maxpool2d(self, x, size=2, stride=2):
        N, H, W, C = x.shape
        H_out = H // stride
        W_out = W // stride
        out = np.zeros((N, H_out, W_out, C), dtype=np.float32)
        for n in range(N):
            for h in range(H_out):
                for w_idx in range(W_out):
                    for c in range(C):
                        out[n, h, w_idx, c] = np.max(x[n, h*stride:(h+1)*stride, w_idx*stride:(w_idx+1)*stride, c])
        return out

    def forward(self, x):
        # Conv1 + ReLU + Pool
        x = self.conv2d(x, self.conv1_w, self.conv1_b)
        x = self.relu(x)
        x = self.maxpool2d(x)  # 32->16

        # Conv2 + ReLU + Pool
        x = self.conv2d(x, self.conv2_w, self.conv2_b)
        x = self.relu(x)
        x = self.maxpool2d(x)  # 16->8

        # Flatten
        x = x.reshape(x.shape[0], -1)  # 8*8*32 = 2048

        # FC1 + ReLU
        x = x @ self.fc1_w + self.fc1_b
        x = self.relu(x)

        # FC2
        x = x @ self.fc2_w + self.fc2_b

        return x

    def save_weights(self, path):
        """Save weights in binary format for Zig benchmark."""
        # Layout: conv1_w (1440 floats) -> conv1_b (16 floats) ->
        #         conv2_w (4608 floats) -> conv2_b (32 floats) ->
        #         fc1_w (262144 floats) -> fc1_b (128 floats) ->
        #         fc2_w (1280 floats) -> fc2_b (10 floats)

        # Transpose conv weights from (kH, kW, C_in, C_out) to (C_out, kH, kW, C_in) for Zig
        conv1_w_t = self.conv1_w.transpose(3, 0, 1, 2).flatten()  # 16 * 3 * 3 * 3 = 1440
        conv2_w_t = self.conv2_w.transpose(3, 0, 1, 2).flatten()  # 32 * 3 * 3 * 16 = 4608

        # Ensure models directory exists
        os.makedirs("models", exist_ok=True)

        with open(path, "wb") as f:
            f.write(conv1_w_t.tobytes())  # 1440 floats
            f.write(self.conv1_b.tobytes())  # 16 floats
            f.write(conv2_w_t.tobytes())  # 4608 floats
            f.write(self.conv2_b.tobytes())  # 32 floats
            f.write(self.fc1_w.tobytes())  # 262144 floats
            f.write(self.fc1_b.tobytes())  # 128 floats
            f.write(self.fc2_w.tobytes())  # 1280 floats
            f.write(self.fc2_b.tobytes())  # 10 floats

        print(f"Saved weights to {path} ({os.path.getsize(path)} bytes)")

# Training
def train(model, train_x, train_y, epochs=20, batch_size=128):
    N = train_x.shape[0]
    num_batches = N // batch_size

    for epoch in range(epochs):
        epoch_loss = 0
        correct = 0

        for batch_idx in range(num_batches):
            start = batch_idx * batch_size
            end = start + batch_size
            x_batch = train_x[start:end]
            y_batch = train_y[start:end]

            # Forward
            logits = model.forward(x_batch)

            # Cross-entropy loss
            exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

            # Loss
            loss = -np.log(probs[np.arange(batch_size), y_batch] + 1e-7).mean()
            epoch_loss += loss

            # Accuracy
            preds = np.argmax(logits, axis=1)
            correct += np.sum(preds == y_batch)

            # Backward (simplified - just SGD)
            lr = 0.01 * (0.95 ** epoch)

            # Gradient for FC2
            dlogits = probs
            dlogits[np.arange(batch_size), y_batch] -= 1
            dlogits /= batch_size

            # Gradient for FC2
            fc1_out = model.relu(model.maxpool2d(model.relu(model.conv2d(
                model.maxpool2d(model.relu(model.conv2d(x_batch, model.conv1_w, model.conv1_b))),
                model.conv2_w, model.conv2_b))))
            fc1_flat = fc1_out.reshape(batch_size, -1)

            grad_fc2_w = fc1_flat.T @ dlogits
            grad_fc2_b = np.sum(dlogits, axis=0)

            # Backprop through FC2
            dfc1 = dlogits @ model.fc2_w.T
            dfc1[fc1_flat <= 0] = 0  # ReLU grad

            # Update FC2
            model.fc2_w -= lr * grad_fc2_w
            model.fc2_b -= lr * grad_fc2_b

            # Gradient for FC1
            grad_fc1_w = fc1_flat.T @ dfc1
            grad_fc1_b = np.sum(dfc1, axis=0)

            model.fc1_w -= lr * grad_fc1_w
            model.fc1_b -= lr * grad_fc1_b

        acc = correct / N
        avg_loss = epoch_loss / num_batches
        print(f"Epoch {epoch+1}/{epochs}: Loss={avg_loss:.4f}, Acc={acc*100:.2f}%")

# Main
def main():
    print("=" * 60)
    print("CIFAR-10 CNN Training for Zig Benchmark")
    print("=" * 60)

    # Download and extract
    tar_path = download_cifar10()
    extract_cifar10(tar_path)

    # Load data
    print("\nLoading CIFAR-10 data...")
    (train_x, train_y), (test_x, test_y) = load_cifar10_data()
    print(f"Train: {train_x.shape}, Test: {test_x.shape}")

    # Create model
    model = CNN()

    # Train
    print("\nTraining...")
    train(model, train_x, train_y, epochs=20)

    # Save weights
    model.save_weights("models/cifar10_cnn_weights.bin")

    # Evaluate on test set
    print("\nEvaluating on test set...")
    test_logits = model.forward(test_x)
    test_preds = np.argmax(test_logits, axis=1)
    test_acc = np.mean(test_preds == test_y)
    print(f"Test Accuracy: {test_acc*100:.2f}%")

    # Save metrics
    metrics = {
        "test_accuracy": float(test_acc),
        "epochs": 20,
        "timestamp": datetime.now().isoformat()
    }
    import json
    with open("results/baseline_cifar10_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("\nDone!")

if __name__ == "__main__":
    main()
