#!/usr/bin/env python3
"""
Train ArchIdx Encoder on Catastrophe Data

Phase 3: Train the encoder to learn from 32 real catastrophes.

This trains the ArchIdx encoder (from ArchIdx/src/encoder/) using
DarkSeer's catastrophe dataset.

The trained encoder will:
1. Better identify which invariants matter most
2. Learn combinations that predict catastrophes
3. Generalize to novel vulnerability types
"""

import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
from pathlib import Path
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from training.dataset import DarkSeerDataset, load_catastrophes, load_safe_commits, TrainingExample


# Simple feedforward network for now (can be replaced with ArchIdx encoder later)
class CatastropheClassifier(nn.Module):
    """
    Classifier for catastrophic changes.
    
    This is a simplified version. In production, this would be
    the full ArchIdx hierarchical encoder.
    """
    
    def __init__(self, input_dim: int):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(128, 64),
            nn.ReLU(),
        )
        
        # Two heads: classification + regression
        self.classifier = nn.Linear(64, 1)  # Is catastrophic?
        self.regressor = nn.Linear(64, 1)   # Severity score
    
    def forward(self, x):
        features = self.encoder(x)
        is_catastrophic = torch.sigmoid(self.classifier(features))
        severity = torch.sigmoid(self.regressor(features))
        return is_catastrophic, severity


def train_epoch(model, dataloader, optimizer, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    
    for batch in tqdm(dataloader, desc="Training"):
        features = batch['features'].to(device)
        labels = batch['is_catastrophic'].to(device)
        severity = batch['severity'].to(device)
        
        # Forward pass
        pred_catastrophic, pred_severity = model(features)
        
        # Loss: Binary cross-entropy + MSE
        loss_classification = nn.BCELoss()(pred_catastrophic, labels)
        loss_regression = nn.MSELoss()(pred_severity, severity)
        loss = loss_classification + 0.5 * loss_regression  # Weight regression less
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        
        # Accuracy
        predicted = (pred_catastrophic > 0.5).float()
        correct += (predicted == labels).sum().item()
        total += labels.size(0)
    
    avg_loss = total_loss / len(dataloader)
    accuracy = correct / total
    
    return avg_loss, accuracy


def validate(model, dataloader, device):
    """Validate the model."""
    model.eval()
    total_loss = 0
    correct = 0
    total = 0
    
    all_preds = []
    all_labels = []
    all_ids = []
    
    with torch.no_grad():
        for batch in dataloader:
            features = batch['features'].to(device)
            labels = batch['is_catastrophic'].to(device)
            severity = batch['severity'].to(device)
            
            pred_catastrophic, pred_severity = model(features)
            
            loss_classification = nn.BCELoss()(pred_catastrophic, labels)
            loss_regression = nn.MSELoss()(pred_severity, severity)
            loss = loss_classification + 0.5 * loss_regression
            
            total_loss += loss.item()
            
            predicted = (pred_catastrophic > 0.5).float()
            correct += (predicted == labels).sum().item()
            total += labels.size(0)
            
            # Store for analysis
            all_preds.extend(pred_catastrophic.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_ids.extend(batch['example_id'])
    
    avg_loss = total_loss / len(dataloader)
    accuracy = correct / total
    
    return avg_loss, accuracy, all_preds, all_labels, all_ids


def main():
    """Train the catastrophe detector."""
    
    print("=" * 70)
    print("  DarkSeer / ArchIdx Training Pipeline")
    print("  Phase 3: Train encoder on catastrophe data")
    print("=" * 70)
    print()
    
    # Paths
    catastrophe_path = Path(__file__).parent.parent / "data" / "training" / "catastrophes.json"
    safe_commits_path = Path("/Users/jonhays/DarkSeer-v3/data/safe_commits.json")
    
    # Check data exists
    if not catastrophe_path.exists():
        print(f"❌ Catastrophe data not found: {catastrophe_path}")
        print("   Run: python scripts/collect_training_data.py")
        return 1
    
    # Load data
    print("📂 Loading training data...")
    catastrophes = load_catastrophes(catastrophe_path)
    print(f"   Loaded {len(catastrophes)} catastrophes")
    
    # Load safe commits if available
    safe_examples = []
    if safe_commits_path.exists():
        print(f"   ⚠️  Safe commits don't have code yet (would need git fetch)")
        print(f"   Training on catastrophes only for now")
        # safe_examples = load_safe_commits(safe_commits_path, max_count=100)
    else:
        print(f"   ⚠️  Safe commits not found (training on catastrophes only)")
    
    # Combine
    all_examples = catastrophes + safe_examples
    print(f"\n✅ Total examples: {len(all_examples)}")
    print(f"   Catastrophic: {len(catastrophes)}")
    print(f"   Safe: {len(safe_examples)}")
    print(f"   Class balance: {len(catastrophes)/(len(all_examples)) * 100:.1f}% catastrophic")
    
    # Create dataset
    print("\n🔧 Building dataset...")
    dataset = DarkSeerDataset(all_examples)
    
    # Split train/val
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
    
    print(f"   Train: {train_size} examples")
    print(f"   Val: {val_size} examples")
    
    # Dataloaders
    train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=8, shuffle=False)
    
    # Model
    input_dim = dataset.get_feature_dim()
    print(f"\n🧠 Model architecture:")
    print(f"   Input dim: {input_dim}")
    print(f"   Encoder: 256 → 128 → 64")
    print(f"   Heads: Classification (binary) + Regression (severity)")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"   Device: {device}")
    
    model = CatastropheClassifier(input_dim).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # Training loop
    num_epochs = 50
    best_val_acc = 0.0
    
    print(f"\n🚀 Training for {num_epochs} epochs...")
    print()
    
    history = {
        'train_loss': [],
        'train_acc': [],
        'val_loss': [],
        'val_acc': [],
    }
    
    for epoch in range(num_epochs):
        print(f"Epoch {epoch+1}/{num_epochs}")
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device)
        
        # Validate
        val_loss, val_acc, preds, labels, ids = validate(model, val_loader, device)
        
        # Log
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        
        print(f"  Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f}")
        print(f"  Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            model_path = Path(__file__).parent.parent / "models" / "catastrophe_detector.pth"
            model_path.parent.mkdir(exist_ok=True)
            torch.save(model.state_dict(), model_path)
            print(f"  ✅ Saved best model (acc: {best_val_acc:.4f})")
        
        print()
    
    # Final results
    print("=" * 70)
    print("  TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nBest validation accuracy: {best_val_acc:.4f}")
    print(f"Final train accuracy: {history['train_acc'][-1]:.4f}")
    print(f"Final validation accuracy: {history['val_acc'][-1]:.4f}")
    
    # Save history
    history_path = Path(__file__).parent.parent / "models" / "training_history.json"
    with open(history_path, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"\n💾 Model saved to: models/catastrophe_detector.pth")
    print(f"📊 History saved to: models/training_history.json")
    
    # Analyze validation errors
    print("\n" + "=" * 70)
    print("  VALIDATION ANALYSIS")
    print("=" * 70)
    
    _, _, preds, labels, ids = validate(model, val_loader, device)
    
    # Find misclassifications
    for i, (pred, label, ex_id) in enumerate(zip(preds, labels, ids)):
        pred_class = 1 if pred > 0.5 else 0
        true_class = int(label)
        
        if pred_class != true_class:
            print(f"\n❌ Misclassified: {ex_id}")
            print(f"   Predicted: {'Catastrophic' if pred_class == 1 else 'Safe'} ({pred:.3f})")
            print(f"   Actual: {'Catastrophic' if true_class == 1 else 'Safe'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

