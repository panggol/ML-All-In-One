#!/usr/bin/env python3
import sys
sys.path.insert(0, 'src')

import mlkit
print(f"mlkit version: {mlkit.__version__}")

# Test core imports
from mlkit import create_runner, Config, BaseModel, SKLearnModel, Hook
from mlkit.hooks import LoggerHook, CheckpointHook, EarlyStoppingHook
from mlkit.config import Config
from mlkit.data import Dataset
from mlkit.model import create_model

# Create a simple dataset
import numpy as np
from sklearn.datasets import make_classification

print("Creating sample data...")
X, y = make_classification(n_samples=1000, n_features=20, n_informative=15,
                           n_redundant=5, n_classes=2, random_state=42)

# Split
from sklearn.model_selection import train_test_split
X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

# Create config
print("Creating runner...")
config = Config.from_dict({
    'model': {
        'type': 'sklearn',
        'task': 'classification',
        'model_class': 'RandomForestClassifier',
        'n_estimators': 10,
        'max_depth': 5,
        'random_state': 42
    },
    'train': {'epochs': 3},
    'hooks': {
        'logger': True,
        'log_dir': './logs',
        'log_interval': 1,
        'checkpoint': False,
        'early_stopping': False,
    }
})

runner = create_runner(config)
runner.train_dataset = Dataset(X_train, y_train)
runner.val_dataset = Dataset(X_val, y_val)

print("Training...")
history = runner.train()
print(f"Train history: {len(history['train_history'])} epochs")
print(f"Val history: {len(history['val_history'])} epochs")

# Predict
print("Predicting...")
preds = runner.predict(X_val[:10])
print(f"Predictions: {preds}")

# Test Experiment system
print("\nTesting Experiment system...")
from mlkit.experiment import ExperimentManager, Experiment
manager = ExperimentManager("./experiments")
exp = manager.create_experiment("test-exp-001", params={"lr": 0.01, "depth": 5})
print(f"Experiment created: {exp.name}")
report = manager.generate_report([exp.id])
print(f"Experiment report generated OK")

print("\n✅ All tests passed - ml-all-in-one is fully operational!")
