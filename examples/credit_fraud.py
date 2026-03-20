# -*- coding: utf-8 -*-
"""
信用卡欺诈检测 - 极度不平衡数据训练示例

数据集特点：
- 284,807 笔交易
- 492 笔欺诈 (0.17%)
- 28 个特征 (PCA 后的 V1-V28)
- Amount 和 Time 特征

本示例模拟类似的数据分布
"""

import sys
sys.path.insert(0, 'src/mlkit')

import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_auc_score,
    precision_recall_curve,
    average_precision_score
)

from mlkit import create_runner, Config, ImbalanceHandler


def create_credit_card_data():
    """
    创建类似信用卡欺诈的数据集
    极度不平衡：正类仅占 0.17%
    """
    print("=" * 60)
    print("创建信用卡欺诈数据集（极度不平衡）")
    print("=" * 60)
    
    X, y = make_classification(
        n_samples=100000,          # 10万条
        n_features=30,             # 30个特征
        n_informative=20,
        n_redundant=10,
        n_classes=2,
        weights=[0.9983, 0.0017], # 极度不平衡：0.17% 正类
        random_state=42,
        flip_y=0.01
    )
    
    print(f"总样本数: {len(y)}")
    print(f"正类(欺诈): {np.sum(y == 1)} ({100*np.mean(y):.2f}%)")
    print(f"负类(正常): {np.sum(y == 0)} ({100*np.mean(y == 0):.2f}%)")
    
    return X, y


def main():
    # 1. 创建数据
    X, y = create_credit_card_data()
    
    # 2. 划分训练集测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    
    print(f"\n训练集: {len(y_train)}, 正类: {np.sum(y_train == 1)}")
    print(f"测试集: {len(y_test)}, 正类: {np.sum(y_test == 1)}")
    
    # 3. 处理不平衡 - 使用多种方法对比
    print("\n" + "=" * 60)
    print("对比不同处理方法")
    print("=" * 60)
    
    methods = [
        ('原始数据(无处理)', None),
        ('SMOTE', 'smote'),
        ('ADASYN', 'adasyn'),
        ('SMOTE+ENN', 'smoteenn'),
        ('SMOTE+TL', 'smotetomek'),
    ]
    
    results = []
    
    for name, method in methods:
        print(f"\n--- {name} ---")
        
        if method:
            X_train_balanced, y_train_balanced = ImbalanceHandler.handle(
                X_train, y_train, method=method, random_state=42
            )
            print(f"处理后: {len(y_train_balanced)}, 正类: {np.sum(y_train_balanced == 1)}")
        else:
            X_train_balanced, y_train_balanced = X_train, y_train
        
        # 4. 创建配置 - 使用 XGBoost
        config_dict = {
            'model': {
                'type': 'xgboost',
                'objective': 'binary:logistic',
                'max_depth': 6,
                'n_estimators': 100,
                'learning_rate': 0.1,
                'scale_pos_weight': len(y_train[y_train==0]) / len(y_train[y_train==1]),  # 处理不平衡
                'tree_method': 'hist',
                'random_state': 42
            },
            'train': {
                'epochs': 5,
            },
        }
        
        config = Config.from_dict(config_dict)
        runner = create_runner(config)
        
        from mlkit.data import Dataset
        runner.train_dataset = Dataset(X_train_balanced, y_train_balanced)
        
        # 5. 训练
        print("训练中...")
        history = runner.train()
        
        # 6. 评估
        y_pred = runner.predict(X_test)
        y_pred_proba = runner.predict_proba(X_test)[:, 1] if hasattr(runner.predict_proba(X_test), 'shape') else runner.predict(X_test)
        
        # 计算指标
        try:
            auc = roc_auc_score(y_test, y_pred_proba)
        except:
            auc = 0.5
            
        try:
            ap = average_precision_score(y_test, y_pred_proba)
        except:
            ap = 0
            
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()
        
        print(f"\n测试集结果:")
        print(f"  AUC-ROC: {auc:.4f}")
        print(f"  Average Precision: {ap:.4f}")
        print(f"  混淆矩阵: TP={tp}, TN={tn}, FP={fp}, FN={fn}")
        print(f"  召回率: {tp/(tp+fn):.4f}")
        
        results.append({
            'method': name,
            'auc': auc,
            'ap': ap,
            'recall': tp/(tp+fn) if (tp+fn) > 0 else 0,
            'precision': tp/(tp+fp) if (tp+fp) > 0 else 0
        })
    
    # 7. 总结
    print("\n" + "=" * 60)
    print("方法对比总结")
    print("=" * 60)
    print(f"{'方法':<20} {'AUC':<10} {'AP':<10} {'召回率':<10} {'精确率':<10}")
    print("-" * 60)
    for r in results:
        print(f"{r['method']:<20} {r['auc']:<10.4f} {r['ap']:<10.4f} {r['recall']:<10.4f} {r['precision']:<10.4f}")
    
    # 8. 持续训练演示
    print("\n" + "=" * 60)
    print("XGBoost 持续训练演示")
    print("=" * 60)
    
    # 第一轮训练
    print("\n第一轮: 基础训练 (50棵树)")
    config_dict = {
        'model': {
            'type': 'xgboost',
            'objective': 'binary:logistic',
            'max_depth': 5,
            'n_estimators': 50,
            'learning_rate': 0.1,
            'scale_pos_weight': len(y_train[y_train==0]) / len(y_train[y_train==1]),
            'tree_method': 'hist',
            'random_state': 42
        },
    }
    config = Config.from_dict(config_dict)
    runner = create_runner(config)
    runner.train_dataset = Dataset(X_train, y_train)
    history1 = runner.train()
    
    # 获取第一轮的 booster
    booster1 = runner.model.model.get_booster()
    
    # 第二轮：增加树继续训练
    print("\n第二轮: 增加50棵树继续训练")
    config_dict['model']['n_estimators'] = 100  # 增加到100棵
    runner2 = create_runner(Config.from_dict(config_dict))
    runner2.train_dataset = Dataset(X_train, y_train)
    
    # 设置上一轮的模型
    runner2.model.model.set_params(xgb_model=booster1)
    history2 = runner2.train()
    
    # 评估持续训练效果
    y_pred_cont = runner2.predict(X_test)
    auc_cont = roc_auc_score(y_test, y_pred_cont)
    print(f"持续训练后 AUC: {auc_cont:.4f}")
    
    print("\n✅ 演示完成!")


if __name__ == '__main__':
    main()
