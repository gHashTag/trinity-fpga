#!/usr/bin/env python3
"""F0.2: Train CIFAR-10 CNN and export trained weights for GF16 benchmark."""
import torch
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as T
import torchvision.datasets as datasets
import os

# Architecture: Conv(3→16)→ReLU→Pool → Conv(16→32)→ReLU→Pool → FC(2048→128) → FC(128→10)
# Expected sizes: conv1_w=1440, conv1_b=16, conv2_w=4608, conv2_b=32, fc1_w=262144, fc1_b=128, fc2_w=1280, fc2_b=10
# Total: 268,650 floats × 4 bytes = 1,074,600 bytes

class SmallCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(3, 16, 3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        # FC1: 32*8*8 = 2048, FC2: 128*10 = 1280
        self.fc1 = nn.Linear(2048, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        # Conv1: 32x32x32 -> 16x16x16
        x = self.conv1(x)
        x = torch.relu(x)
        x = self.pool(x)  # 16x16

        # Conv2: 16x16x16 -> 32x16x16
        x = self.conv2(x)
        x = torch.relu(x)
        x = self.pool(x)  # 16x8

        # Flatten: 2048 -> FC1 input
        x = x.view(x.size(0), -1)

        # FC1
        x = self.fc1(x)
        x = self.fc2(x)

        return x

def train_cifar10(epochs=20, lr=0.001, data_dir="data", weights_path="models/cifar10_cnn_weights.bin"):
    """Train CNN on CIFAR-10 for 20 epochs and export weights."""
    print("Training CNN on CIFAR-10...")

    # Transforms
    transform_train = T.Compose([T.RandomHorizontalFlip(), T.ToTensor()])
    transform_test = T.Compose([T.ToTensor()])

    # Download CIFAR-10 dataset if not exists
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
        print(f"Downloading CIFAR-10...")

    # Download training data (5 batches)
    trainset = torchvision.datasets.CIFAR10(root=data_dir, train=True, download=True, transform=transform_train)

    # Download test data
    testset = torchvision.datasets.CIFAR10(root=data_dir, train=False, download=True, transform=transform_test)

    # Data loaders
    trainloader = torch.utils.data.DataLoader(trainset, batch_size=128, shuffle=True)
    testloader = torch.utils.data.DataLoader(testset, batch_size=256, shuffle=False)

    print(f"Training set: {len(trainset):, len(testset):}")

    # Create model
    model = SmallCNN()
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    # Training loop
    for epoch in range(epochs):
        model.train()
        model.eval()

        # Test accuracy on training set
        correct = 0
        total = 0
        with torch.no_grad():
            for imgs, labels in trainloader:
                outputs = model(imgs)
                _, pred = torch.max(outputs, dim=1)[1]
                correct += (pred == labels).sum().item()
                total += labels.size(0)

        train_acc = 100.0 * correct / total
        print(f"Epoch {epoch+1}/{epochs} - Train acc: {train_acc:.2f}%")

    # Final test
    model.eval()
    test_correct = 0
    test_total = 0
    with torch.no_grad():
        for imgs, labels in testloader:
                outputs = model(imgs)
                _, pred = torch.max(outputs, dim=1)[1]
                test_correct += (pred == labels).sum().item()
                test_total += labels.size(0)

    test_acc = 100.0 * test_correct / test_total
    print(f"Test accuracy: {test_acc:.2f}%")

    # Export weights
    export_weights(model, weights_path)
    print(f"Weights exported to: {weights_path}")

    # Save metrics
    metrics = {"test_accuracy": test_acc, "train_accuracy": train_acc, "epochs": epochs}
    import json
    with open("results/baseline_cifar10_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("Metrics saved to: results/baseline_cifar10_metrics.json")

def export_weights(model, path):
    """Export model weights to binary file (little-endian f32)."""
    # Collect all weights in order
    weights = []

    # conv1 weights: 16x3x3x3 = 1440
    w1 = model.conv1.weight.data.cpu().numpy()
    b1 = model.conv1.bias.data.cpu().numpy()
    weights.append(w1.flatten())
    weights.append(b1)

    # conv2 weights: 32x16x3x3 = 4608
    w2 = model.conv2.weight.data.cpu().numpy()
    b2 = model.conv2.bias.data.cpu().numpy()
    weights.append(w2.flatten())
    weights.append(b2)

    # fc1 weights: 128x2048 = 262144
    w3 = model.fc1.weight.data.cpu().numpy()
    b3 = model.fc1.bias.data.cpu().numpy()
    weights.append(w3.flatten())

    # fc2 weights: 128x10 = 1280
    w4 = model.fc2.weight.data.cpu().numpy()
    b4 = model.fc2.bias.data.cpu().numpy()
    weights.append(w4)

    # Expected total: 268,650 floats = 1,074,600 bytes
    print(f"Total weights: {len(weights)} floats")

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Write to binary (little-endian)
    with open(path, 'wb') as f:
        for w in weights:
            # PyTorch saves floats in little-endian by default
            f.write(w.tobytes())

    file_size = os.path.getsize(path)
    print(f"Wrote {file_size} bytes")

    if file_size != 1074600:
        print(f"WARNING: Expected 1,074,600 bytes, got {file_size}")

if __name__ == "__main__":
    train_cifar10()
