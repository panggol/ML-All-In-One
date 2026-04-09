# -*- coding: utf-8 -*-
"""
ML Kit - Gradio Web UI v2

机器学习训练与推理平台 Web 界面 v2
基于 UI 设计规范 v1.0 实现

启动方式:
    cd ml-all-in-one
    PYTHONPATH=src python app.py

设计参考: Weights & Biases / MLflow 交互模式
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import json
import time
import traceback
from pathlib import Path
from datetime import datetime

import gradio as gr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mcolors

# 核心模块
from mlkit import create_runner, Config, BaseModel
from mlkit.config import Config
from mlkit.data import Dataset, DataLoader
from mlkit.model import create_model
from mlkit.experiment import ExperimentManager, Experiment


# =============================================================================
# 主题 & 样式
# =============================================================================

# 配色方案
COLORS = {
    "primary": "#6366F1",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "bg_dark": "#0F172A",
    "bg_card": "#1E293B",
    "border": "#334155",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "accent": "#818CF8",
}

# Gradio 暗色主题 (Gradio 6 compatible)
DARK_THEME = gr.themes.Ocean().set(
    # 深色配色
    body_background_fill_dark="#0F172A",
    background_fill_primary_dark="#0F172A",
    background_fill_secondary_dark="#1E293B",
    block_background_fill_dark="#1E293B",
    block_border_color_dark="#334155",
    panel_background_fill_dark="#1E293B",
    panel_border_color_dark="#334155",
    # 文字颜色
    body_text_color_dark="#F1F5F9",
    body_text_color_subdued_dark="#94A3B8",
    # 输入
    input_background_fill_dark="#1E293B",
    input_border_color_dark="#334155",
    # Primary button
    button_primary_background_fill_dark="#6366F1",
    button_primary_background_fill_hover_dark="#818CF8",
    button_primary_text_color_dark="#FFFFFF",
    # Secondary button
    button_secondary_background_fill_dark="#334155",
    button_secondary_text_color_dark="#F1F5F9",
    # Accent
    color_accent_soft_dark="#6366F1",
    border_color_accent_dark="#6366F1",
    # 表格
    table_odd_background_fill_dark="#1E293B",
    table_even_background_fill_dark="#0F172A",
    table_border_color_dark="#334155",
    # Stat
    stat_background_fill_dark="#334155",
)


# =============================================================================
# 全局状态
# =============================================================================

EXPERIMENTS_DIR = Path("./experiments")
EXPERIMENTS_DIR.mkdir(exist_ok=True)
CHECKPOINTS_DIR = Path("./checkpoints")
CHECKPOINTS_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path("./logs")
LOGS_DIR.mkdir(exist_ok=True)

experiment_manager = ExperimentManager(str(EXPERIMENTS_DIR))

# 全局变量：当前训练的 runner（用于停止训练）
_current_runner = {"runner": None, "stop": False}

# 加载 CSV 缓存
_csv_cache = {}


# =============================================================================
# 工具函数
# =============================================================================

def get_saved_models():
    """列出已保存的模型"""
    models = []
    for f in CHECKPOINTS_DIR.glob("*"):
        if f.suffix in [".pkl", ".pth", ".joblib"]:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            models.append({"name": f.name, "mtime": mtime, "size_mb": f.stat().st_size / 1024 / 1024})
    return models


def get_system_stats():
    """获取系统统计"""
    exp_count = len(list(EXPERIMENTS_DIR.glob("*.json")))
    model_count = len(list(CHECKPOINTS_DIR.glob("*.pkl"))) + len(list(CHECKPOINTS_DIR.glob("*.pth"))) + len(list(CHECKPOINTS_DIR.glob("*.joblib")))
    return {
        "总实验数": exp_count,
        "训练模型数": model_count,
    }


def plot_training_history(history: dict, figsize=(10, 4)) -> plt.Figure:
    """绘制训练历史曲线（暗色主题）"""
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    fig.patch.set_facecolor(COLORS["bg_card"])
    for ax in axes:
        ax.set_facecolor("#0F172A")
        ax.tick_params(colors=COLORS["text_secondary"])
        ax.xaxis.label.set_color(COLORS["text_secondary"])
        ax.yaxis.label.set_color(COLORS["text_secondary"])
        ax.title.set_color(COLORS["text_primary"])
        ax.spines["bottom"].set_color(COLORS["border"])
        ax.spines["left"].set_color(COLORS["border"])
        ax.spines["top"].set_color(COLORS["border"])
        ax.spines["right"].set_color(COLORS["border"])
        ax.grid(True, alpha=0.2, color=COLORS["border"])

    train_history = history.get("train_history", [])
    val_history = history.get("val_history", [])

    epochs = [h.get("epoch", i) for i, h in enumerate(train_history)]
    train_acc = [h.get("train_acc", 0) for h in train_history]
    val_acc = [h.get("val_acc", 0) for h in val_history]
    train_loss = [h.get("train_loss", 0) for h in train_history]
    val_loss = [h.get("val_loss", 0) for h in val_history]

    if train_acc:
        axes[0].plot(epochs, train_acc, label="Train Acc", color="#6366F1", marker="o", markersize=3)
    if val_acc:
        axes[0].plot(epochs, val_acc, label="Val Acc", color="#10B981", marker="s", markersize=3)
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Accuracy")
    axes[0].set_title("Accuracy over Epochs")
    axes[0].legend(facecolor=COLORS["bg_card"], edgecolor=COLORS["border"], labelcolor=COLORS["text_primary"])

    if train_loss:
        axes[1].plot(epochs, train_loss, label="Train Loss", color="#F59E0B", marker="o", markersize=3)
    if val_loss:
        axes[1].plot(epochs, val_loss, label="Val Loss", color="#EF4444", marker="s", markersize=3)
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss")
    axes[1].set_title("Loss over Epochs")
    axes[1].legend(facecolor=COLORS["bg_card"], edgecolor=COLORS["border"], labelcolor=COLORS["text_primary"])

    plt.tight_layout()
    return fig


def plot_multi_experiment_comparison(exp_ids: list, metric: str) -> plt.Figure:
    """绘制多实验对比曲线"""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_facecolor("#0F172A")
    ax.tick_params(colors=COLORS["text_secondary"])
    ax.xaxis.label.set_color(COLORS["text_secondary"])
    ax.yaxis.label.set_color(COLORS["text_secondary"])
    ax.title.set_color(COLORS["text_primary"])
    ax.spines["bottom"].set_color(COLORS["border"])
    ax.spines["left"].set_color(COLORS["border"])
    ax.spines["top"].set_color(COLORS["border"])
    ax.spines["right"].set_color(COLORS["border"])
    ax.grid(True, alpha=0.2, color=COLORS["border"])

    colors = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#818CF8", "#34D399"]

    for i, exp_id in enumerate(exp_ids):
        exp = experiment_manager.load_experiment(exp_id)
        if exp and exp.metrics and metric in exp.metrics:
            records = exp.metrics[metric]
            steps = [r.step for r in records]
            values = [r.value for r in records]
            color = colors[i % len(colors)]
            ax.plot(steps, values, label=exp.name, color=color, marker="o", markersize=3, linewidth=1.5)

    ax.set_xlabel("Step / Epoch")
    ax.set_ylabel(metric)
    ax.set_title(f"Experiment Comparison — {metric}")
    ax.legend(facecolor=COLORS["bg_card"], edgecolor=COLORS["border"], labelcolor=COLORS["text_primary"], loc="best")
    plt.tight_layout()
    return fig


# =============================================================================
# Tab 0: Dashboard
# =============================================================================

def dashboard_tab():
    """Dashboard 概览页面"""
    gr.Markdown("## 📊 系统概览")

    with gr.Row():
        stat_exp = gr.Number(label="📋 总实验数", value=0, interactive=False)
        stat_model = gr.Number(label="🤖 训练模型数", value=0, interactive=False)
        stat_data = gr.Number(label="📁 数据集", value=0, interactive=False)

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 🕐 最近实验")
            recent_experiments = gr.DataFrame(
                headers=["名称", "状态", "最佳指标", "耗时"],
                interactive=False,
                label="最近实验",
            )
            refresh_dashboard_btn = gr.Button("🔄 刷新", size="sm")

        with gr.Column(scale=1):
            gr.Markdown("### ⚡ 快速入口")
            quick_train_btn = gr.Button("🏋️ 新建训练", variant="primary")
            quick_exp_btn = gr.Button("🧪 实验对比", variant="secondary")
            quick_inference_btn = gr.Button("🔮 模型推理", variant="secondary")
            gr.Markdown("*使用快速入口跳转至对应 Tab*")

    def load_dashboard_stats():
        stats = get_system_stats()
        exp_count = stats["总实验数"]
        model_count = stats["训练模型数"]
        data_count = len(list(Path(".").glob("**/*.csv")))

        # 最近实验
        exps = experiment_manager.load_all()
        exp_list = sorted(exps.values(), key=lambda e: e.created_at if e.created_at else "", reverse=True)
        rows = []
        for exp in exp_list[:5]:
            best = ", ".join([f"{k}={v:.4f}" for k, v in exp.best_metrics.items()]) if exp.best_metrics else "—"
            dur = f"{exp.duration:.1f}s" if exp.duration else "—"
            rows.append({
                "名称": exp.name,
                "状态": exp.status,
                "最佳指标": best,
                "耗时": dur,
            })
        recent_df = pd.DataFrame(rows, columns=["名称", "状态", "最佳指标", "耗时"]) if rows else pd.DataFrame(columns=["名称", "状态", "最佳指标", "耗时"])

        return (
            gr.update(value=exp_count),
            gr.update(value=model_count),
            gr.update(value=data_count),
            recent_df,
        )

    refresh_dashboard_btn.click(
        load_dashboard_stats,
        outputs=[stat_exp, stat_model, stat_data, recent_experiments]
    )

    # 初始化加载
    load_dashboard_stats()

    return stat_exp, stat_model, stat_data, recent_experiments


# =============================================================================
# Tab 1: 训练
# =============================================================================

def train_tab():
    """训练页面 - 优化布局"""
    gr.Markdown("## 🏋️ 模型训练")

    with gr.Row():
        # ===== 左侧: 配置面板 =====
        with gr.Column(scale=1):
            gr.Markdown("### 📥 数据配置")
            train_file = gr.File(
                label="训练数据 (CSV)",
                file_types=[".csv"],
                height=80,
            )
            target_column = gr.Textbox(
                label="目标列名",
                placeholder="留空则自动选择最后一列",
                value="",
            )
            val_ratio = gr.Slider(0.1, 0.4, value=0.2, step=0.05, label="验证集比例")

            gr.Markdown("### 🤖 模型配置")
            model_type = gr.Dropdown(
                ["sklearn", "xgboost", "lightgbm", "pytorch"],
                label="模型类型",
                value="sklearn",
            )
            sklearn_model = gr.Dropdown(
                ["RandomForestClassifier", "RandomForestRegressor",
                 "LogisticRegression", "GradientBoostingClassifier"],
                label="Sklearn 模型",
                value="RandomForestClassifier",
            )
            task_type = gr.Dropdown(
                ["classification", "regression"],
                label="任务类型",
                value="classification",
            )

            gr.Markdown("### ⚙️ 训练参数")
            n_estimators = gr.Slider(1, 500, value=100, step=1, label="n_estimators")
            max_depth = gr.Slider(1, 50, value=10, step=1, label="max_depth")
            learning_rate = gr.Slider(0.001, 1.0, value=0.1, step=0.01, label="learning_rate")
            epochs = gr.Slider(1, 200, value=20, step=1, label="Epochs")

            gr.Markdown("### 🪝 训练监控")
            enable_logger = gr.Checkbox(label="启用日志记录", value=True)
            enable_checkpoint = gr.Checkbox(label="保存检查点", value=True)
            enable_early_stopping = gr.Checkbox(label="启用早停", value=False)
            patience = gr.Slider(3, 50, value=10, step=1, label="Patience", visible=False)
            monitor_metric = gr.Dropdown(
                ["val_acc", "val_loss", "val_f1"],
                label="监控指标",
                value="val_acc",
            )

            gr.Markdown("### 🧪 实验追踪")
            exp_name = gr.Textbox(
                label="实验名称",
                placeholder="如: baseline-v1（留空则不记录）",
                value="",
            )

            with gr.Row():
                train_btn = gr.Button("🚀 开始训练", variant="primary", size="lg")
                stop_btn = gr.Button("⏹ 停止训练", variant="stop", size="lg")

        # ===== 右侧: 结果面板 =====
        with gr.Column(scale=2):
            gr.Markdown("### 📈 训练状态")
            status_text = gr.Textbox(
                label="训练日志",
                lines=8,
                interactive=False,
                show_label=True,
            )

            gr.Markdown("### 📊 训练曲线")
            plot_output = gr.Plot(label="Loss & Accuracy")

            gr.Markdown("### 📋 训练结果")
            with gr.Row():
                result_json = gr.JSON(label="完整指标")
                model_info_json = gr.JSON(label="模型信息")

    # ===== 动态交互 =====
    def update_patience_visibility(enabled):
        return gr.update(visible=enabled)

    def update_sklearn_visibility(model_t):
        return gr.update(visible=(model_t == "sklearn"))

    enable_early_stopping.change(
        update_patience_visibility,
        inputs=[enable_early_stopping],
        outputs=[patience],
    )

    model_type.change(
        update_sklearn_visibility,
        inputs=[model_type],
        outputs=[sklearn_model],
    )

    # ===== 训练逻辑 =====
    def do_train(
        train_file, target_column, val_ratio,
        model_type, sklearn_model, task_type,
        n_estimators, max_depth, learning_rate, epochs,
        enable_logger, enable_checkpoint, enable_early_stopping,
        patience, monitor_metric, exp_name
    ):
        """执行训练"""
        _current_runner["stop"] = False

        try:
            yield "⏳ 初始化中...", None, None, None

            if train_file is None:
                yield "❌ 请先上传训练数据", None, None, None
                return

            filepath = train_file.name if hasattr(train_file, "name") else str(train_file)
            df_full = pd.read_csv(filepath)

            # 自动选择目标列
            if not target_column or target_column not in df_full.columns:
                target_column = df_full.columns[-1]

            y_full = df_full[target_column].values
            X_full = df_full.drop(columns=[target_column]).values
            feature_names = [c for c in df_full.columns if c != target_column]

            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(
                X_full, y_full, test_size=val_ratio, random_state=42
            )

            yield "⏳ 数据加载完成，正在构建 Runner...", None, None, None

            # 创建实验
            exp = None
            if exp_name:
                params = {
                    "model_type": model_type,
                    "task_type": task_type,
                    "n_estimators": int(n_estimators),
                    "max_depth": int(max_depth),
                    "epochs": int(epochs),
                    "val_ratio": val_ratio,
                    "learning_rate": float(learning_rate),
                }
                exp = experiment_manager.create_experiment(exp_name, params=params)

            config_dict = {
                "model": {
                    "type": model_type,
                    "task": task_type,
                    "model_class": sklearn_model if model_type == "sklearn" else None,
                    "n_estimators": int(n_estimators),
                    "max_depth": int(max_depth),
                    "learning_rate": float(learning_rate),
                    "random_state": 42,
                },
                "train": {
                    "epochs": int(epochs),
                    "val_interval": 1,
                },
                "hooks": {
                    "logger": enable_logger,
                    "log_dir": str(LOGS_DIR),
                    "log_interval": 1,
                    "checkpoint": enable_checkpoint,
                    "save_dir": str(CHECKPOINTS_DIR),
                    "save_best": True,
                    "monitor": monitor_metric,
                    "save_interval": 1,
                    "early_stopping": enable_early_stopping,
                    "early_stopping_patience": int(patience),
                    "early_stopping_monitor": monitor_metric,
                }
            }

            config = Config.from_dict(config_dict)
            runner = create_runner(config, experiment=exp)
            runner.train_dataset = Dataset(X_train, y_train, feature_names=feature_names)
            runner.val_dataset = Dataset(X_val, y_val, feature_names=feature_names)

            _current_runner["runner"] = runner

            yield "🏃 训练进行中...", None, None, None

            # 训练
            history = runner.train()

            if _current_runner["stop"]:
                yield "⏹ 训练已停止", None, None, None
                return

            yield "✅ 训练完成！正在生成报告...", None, None, None

            fig = plot_training_history(history)

            if exp:
                exp.finish(status="completed")
                experiment_manager.save_experiment(exp)

            last_val = history["val_history"][-1] if history["val_history"] else {}
            final_msg = f"🎉 训练完成！\n\n最终验证准确率: {last_val.get('val_acc', 'N/A')}\n训练轮数: {len(history['train_history'])}"

            result = {
                "train_history_len": len(history["train_history"]),
                "val_history_len": len(history["val_history"]),
                "final_metrics": last_val,
            }

            model_params = {
                "model_type": model_type,
                "task_type": task_type,
                "n_estimators": int(n_estimators),
                "max_depth": int(max_depth),
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "n_features": X_train.shape[1],
            }

            yield final_msg, fig, result, model_params

        except Exception as e:
            yield f"❌ 训练失败: {str(e)}\n\n{traceback.format_exc()}", None, None, None

    def do_stop():
        _current_runner["stop"] = True
        return "⏹ 已发送停止信号..."

    train_btn.click(
        do_train,
        inputs=[
            train_file, target_column, val_ratio,
            model_type, sklearn_model, task_type,
            n_estimators, max_depth, learning_rate, epochs,
            enable_logger, enable_checkpoint, enable_early_stopping,
            patience, monitor_metric, exp_name
        ],
        outputs=[status_text, plot_output, result_json, model_info_json]
    )

    stop_btn.click(do_stop, outputs=[status_text])

    return train_file


# =============================================================================
# Tab 2: 实验管理
# =============================================================================

def experiments_tab():
    """实验管理页面"""
    gr.Markdown("## 🧪 实验管理")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📋 实验列表")
            experiments_table = gr.DataFrame(
                headers=["名称", "状态", "最佳指标", "耗时(s)", "创建时间"],
                interactive=True,
                label="历史实验",
                wrap=True,
            )
            with gr.Row():
                refresh_btn = gr.Button("🔄 刷新", size="sm")
                compare_btn = gr.Button("📊 对比所选", variant="primary", size="sm")

        with gr.Column(scale=2):
            gr.Markdown("### 📈 实验详情")
            exp_detail = gr.JSON(label="实验详情")
            metric_selector = gr.Dropdown(
                ["val_acc", "val_loss", "val_f1", "train_acc", "train_loss"],
                label="选择指标",
                value="val_acc",
            )
            comparison_plot = gr.Plot(label="实验对比曲线")
            exp_report = gr.Markdown("### 📝 实验报告\n选择实验查看详细报告")

    def load_experiments():
        exps = experiment_manager.load_all()
        if not exps:
            return pd.DataFrame(columns=["名称", "状态", "最佳指标", "耗时(s)", "创建时间"])

        rows = []
        for exp_id, exp in exps.items():
            best = ", ".join([f"{k}={v:.4f}" for k, v in exp.best_metrics.items()]) if exp.best_metrics else "—"
            dur = f"{exp.duration:.1f}" if exp.duration else "—"
            created = exp.created_at.strftime("%Y-%m-%d %H:%M") if exp.created_at else "—"
            rows.append({
                "名称": exp.name,
                "状态": exp.status,
                "最佳指标": best,
                "耗时(s)": dur,
                "创建时间": created,
            })

        df = pd.DataFrame(rows, columns=["名称", "状态", "最佳指标", "耗时(s)", "创建时间"])
        return df.sort_values("创建时间", ascending=False)

    def on_select_exp(evt: gr.SelectData, exp_table):
        exps = experiment_manager.load_all()
        for exp_id, exp in exps.items():
            if exp.name == evt.value:
                return exp.to_dict()
        return {}

    def compare_selected(exp_table, selected_metric):
        if exp_table is None or len(exp_table) == 0:
            return gr.update(), "请在列表中勾选实验"

        selected_names = set()
        if hasattr(exp_table, "__iter__"):
            for row in exp_table:
                if isinstance(row, dict):
                    selected_names.add(row.get("名称", ""))
                elif isinstance(row, (list, tuple)):
                    selected_names.add(row[0])

        if not selected_names:
            return gr.update(), "请在列表中勾选实验"

        selected_ids = []
        exps = experiment_manager.load_all()
        for exp_id, exp in exps.items():
            if exp.name in selected_names:
                selected_ids.append(exp_id)

        if not selected_ids:
            return gr.update(), "未找到匹配实验"

        try:
            fig = plot_multi_experiment_comparison(selected_ids, selected_metric)
            report = experiment_manager.generate_report(selected_ids)
            return fig, report
        except Exception as e:
            return gr.update(), f"对比失败: {str(e)}"

    refresh_btn.click(load_experiments, outputs=[experiments_table])

    experiments_table.select(
        on_select_exp,
        inputs=[experiments_table],
        outputs=[exp_detail],
    )

    compare_btn.click(
        compare_selected,
        inputs=[experiments_table, metric_selector],
        outputs=[comparison_plot, exp_report],
    )

    metric_selector.change(
        compare_selected,
        inputs=[experiments_table, metric_selector],
        outputs=[comparison_plot, exp_report],
    )

    # 初始化
    load_experiments()

    return experiments_table


# =============================================================================
# Tab 3: 预处理
# =============================================================================

def preprocessing_tab():
    """预处理页面"""
    gr.Markdown("## ⚙️ 数据预处理")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 📥 数据输入")
            preprocess_file = gr.File(label="上传 CSV 文件", file_types=[".csv"], height=80)
            load_data_btn = gr.Button("📂 加载数据")

            gr.Markdown("### 🔧 预处理步骤")
            gr.Markdown("勾选需要执行的预处理操作（按顺序）")

            enable_scaler = gr.Checkbox(label="✅ 归一化/标准化 (StandardScaler)", value=True)
            scaler_type = gr.Radio(
                ["standard", "minmax", "robust"],
                label="标准化方式",
                value="standard",
                visible=True,
            )

            enable_imputer = gr.Checkbox(label="✅ 缺失值填充 (SimpleImputer)", value=True)
            imputer_strategy = gr.Dropdown(
                ["mean", "median", "most_frequent", "constant"],
                label="填充策略",
                value="mean",
                visible=True,
            )

            enable_feature_select = gr.Checkbox(label="☑️ 特征选择 (SelectKBest)", value=False)
            k_features = gr.Slider(2, 50, value=10, step=1, label="选择前 K 个特征", visible=False)

            enable_split = gr.Checkbox(label="✅ 划分训练/验证集", value=True)
            split_ratio = gr.Slider(0.1, 0.4, value=0.2, step=0.05, label="验证集比例", visible=True)

            with gr.Row():
                run_preprocess_btn = gr.Button("▶️ 执行预处理", variant="primary")
                save_result_btn = gr.Button("💾 保存结果", variant="secondary")

        with gr.Column(scale=2):
            gr.Markdown("### 📊 原始数据信息")
            original_info = gr.JSON(label="原始数据统计")
            original_preview = gr.DataFrame(label="原始数据预览 (前10行)", wrap=True)

            gr.Markdown("### 📊 预处理后数据")
            processed_preview = gr.DataFrame(label="处理后数据预览 (前10行)", wrap=True)
            preprocess_status = gr.Textbox(label="处理状态", lines=4, interactive=False)

    def update_visibility(enabled, _type="checkbox"):
        pass

    enable_scaler.change(
        lambda x: gr.update(visible=x),
        inputs=[enable_scaler],
        outputs=[scaler_type],
    )

    enable_imputer.change(
        lambda x: gr.update(visible=x),
        inputs=[enable_imputer],
        outputs=[imputer_strategy],
    )

    enable_feature_select.change(
        lambda x: gr.update(visible=x),
        inputs=[enable_feature_select],
        outputs=[k_features],
    )

    enable_split.change(
        lambda x: gr.update(visible=x),
        inputs=[enable_split],
        outputs=[split_ratio],
    )

    def do_load_data(file_obj):
        if file_obj is None:
            return gr.update(), "请上传文件"
        try:
            filepath = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            df = pd.read_csv(filepath)
            _csv_cache["original"] = df

            info = {
                "形状": f"{df.shape[0]} 行 × {df.shape[1]} 列",
                "内存占用": f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB",
                "目标列建议": df.columns[-1],
                "缺失值列": [c for c in df.columns if df[c].isnull().any()],
            }
            return info, df.head(10)
        except Exception as e:
            return gr.update(), f"加载失败: {str(e)}"

    def do_preprocess(
        enable_scaler, scaler_type,
        enable_imputer, imputer_strategy,
        enable_feature_select, k_features,
        enable_split, split_ratio
    ):
        if "original" not in _csv_cache:
            yield "❌ 请先加载数据", gr.update(), gr.update()
            return

        df = _csv_cache["original"].copy()
        target_col = df.columns[-1]
        y = df[target_col].values
        X = df.drop(columns=[target_col])

        yield "⏳ 正在预处理...", gr.update(), gr.update()

        try:
            from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
            from sklearn.impute import SimpleImputer
            from sklearn.feature_selection import SelectKBest, f_classif, f_regression
            from sklearn.model_selection import train_test_split

            steps = []

            # 缺失值填充
            if enable_imputer:
                imputer = SimpleImputer(strategy=imputer_strategy)
                X = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)
                steps.append(f"缺失值填充 ({imputer_strategy})")

            # 标准化
            if enable_scaler:
                if scaler_type == "standard":
                    scaler = StandardScaler()
                elif scaler_type == "minmax":
                    scaler = MinMaxScaler()
                else:
                    scaler = RobustScaler()
                X = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)
                steps.append(f"标准化 ({scaler_type})")

            # 特征选择
            if enable_feature_select:
                k = int(min(k_features, X.shape[1]))
                selector = SelectKBest(f_classif if y.dtype in [int, 'int64', 'int32'] or len(np.unique(y)) < 20 else f_regression, k=k)
                X = pd.DataFrame(selector.fit_transform(X, y), columns=X.columns)
                steps.append(f"特征选择 (K={k})")

            # 划分
            if enable_split:
                X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=split_ratio, random_state=42)
                steps.append(f"训练/验证划分 ({split_ratio})")

            # 合并回 DataFrame
            df_processed = X.copy()
            df_processed[target_col] = y

            _csv_cache["processed"] = df_processed
            _csv_cache["X_train"] = X_train if enable_split else X
            _csv_cache["X_val"] = X_val if enable_split else None
            _csv_cache["y_train"] = y_train if enable_split else y
            _csv_cache["y_val"] = y_val if enable_split else None

            processed_info = {
                "原始形状": df.shape,
                "处理后形状": df_processed.shape,
                "执行步骤": steps,
                "保存位置": "已缓存（点击保存）",
            }

            yield f"✅ 预处理完成！\n\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps)), df_processed.head(10), processed_info

        except Exception as e:
            yield f"❌ 预处理失败: {str(e)}", gr.update(), gr.update()

    def do_save():
        if "processed" not in _csv_cache:
            return "❌ 无预处理数据可保存"
        try:
            save_path = Path("./data/processed")
            save_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = save_path / f"processed_{timestamp}.csv"
            _csv_cache["processed"].to_csv(csv_path, index=False)
            return f"✅ 已保存至: {csv_path}"
        except Exception as e:
            return f"❌ 保存失败: {str(e)}"

    load_data_btn.click(do_load_data, inputs=[preprocess_file], outputs=[original_info, original_preview])

    run_preprocess_btn.click(
        do_preprocess,
        inputs=[
            enable_scaler, scaler_type,
            enable_imputer, imputer_strategy,
            enable_feature_select, k_features,
            enable_split, split_ratio
        ],
        outputs=[preprocess_status, processed_preview, original_info],
    )

    save_result_btn.click(do_save, outputs=[preprocess_status])

    return preprocess_file


# =============================================================================
# Tab 4: 推理
# =============================================================================

def inference_tab():
    """推理页面"""
    gr.Markdown("## 🔮 模型推理")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 🤖 模型选择")
            model_source = gr.Radio(
                ["已训练的模型", "上传模型文件"],
                label="模型来源",
                value="已训练的模型",
            )

            saved_models = gr.Dropdown(
                label="选择已训练模型",
                choices=[m["name"] for m in get_saved_models()] or ["(无已保存模型)"],
            )
            refresh_models_btn = gr.Button("🔄 刷新模型列表", size="sm")

            model_file = gr.File(
                label="上传模型文件 (.pkl, .joblib)",
                file_types=[".pkl", ".joblib"],
                visible=False,
            )

            gr.Markdown("### 📥 输入数据")
            data_mode = gr.Radio(
                ["JSON 输入", "CSV 文件", "CSV 文件路径"],
                label="数据输入方式",
                value="JSON 输入",
            )

            json_input = gr.Textbox(
                label="JSON 数据",
                placeholder='[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]',
                lines=5,
                visible=True,
            )

            csv_input_file = gr.File(
                label="上传 CSV",
                file_types=[".csv"],
                visible=False,
            )

            csv_path_input = gr.Textbox(
                label="CSV 文件路径",
                placeholder="/path/to/data.csv",
                visible=False,
            )

            predict_btn = gr.Button("🔮 执行推理", variant="primary", size="lg")

        with gr.Column(scale=2):
            gr.Markdown("### 📊 推理结果")
            prediction_output = gr.JSON(label="预测类别")
            proba_output = gr.JSON(label="预测概率")

            gr.Markdown("### 📈 批量预测统计")
            batch_stats = gr.JSON(label="统计信息")

    def refresh_models():
        models = get_saved_models()
        choices = [m["name"] for m in models] if models else ["(无已保存模型)"]
        return gr.update(choices=choices)

    def update_data_mode_visibility(mode):
        return (
            gr.update(visible=(mode == "JSON 输入")),
            gr.update(visible=(mode == "CSV 文件")),
            gr.update(visible=(mode == "CSV 文件路径")),
        )

    model_source.change(
        lambda x: [gr.update(visible=x == "已训练的模型"), gr.update(visible=x == "上传模型文件")],
        inputs=[model_source],
        outputs=[saved_models, model_file],
    )

    data_mode.change(
        update_data_mode_visibility,
        inputs=[data_mode],
        outputs=[json_input, csv_input_file, csv_path_input],
    )

    refresh_models_btn.click(refresh_models, outputs=[saved_models])

    def do_predict(model_source, model_choice, model_file, data_mode, json_input, csv_input_file, csv_path_input):
        try:
            # 加载模型
            if model_source == "已训练的模型":
                if not model_choice or model_choice == "(无已保存模型)":
                    yield {"error": "无可用模型，请先训练或上传"}, None, None
                    return
                model_path = CHECKPOINTS_DIR / model_choice
                if not model_path.exists():
                    yield {"error": f"模型文件不存在: {model_choice}"}, None, None
                    return
                import joblib
                model = joblib.load(model_path)
            else:
                if model_file is None:
                    yield {"error": "请上传模型文件"}, None, None
                    return
                filepath = model_file.name if hasattr(model_file, "name") else str(model_file)
                import joblib
                model = joblib.load(filepath)

            yield {"status": "模型加载成功"}, None, None

            # 解析数据
            if data_mode == "JSON 输入":
                data = json.loads(json_input.strip())
                X = np.array(data)
            elif data_mode == "CSV 文件":
                if csv_input_file is None:
                    yield {"error": "请上传 CSV 文件"}, None, None
                    return
                filepath = csv_input_file.name if hasattr(csv_input_file, "name") else str(csv_input_file)
                df = pd.read_csv(filepath)
                X = df.values
            else:
                if not os.path.exists(csv_path_input.strip()):
                    yield {"error": f"文件不存在: {csv_path_input}"}, None, None
                    return
                df = pd.read_csv(csv_path_input.strip())
                X = df.values

            yield {"status": "正在推理...", "input_shape": str(X.shape)}, None, None

            # 推理
            preds = model.predict(X)
            result = {"predictions": preds.tolist() if hasattr(preds, "tolist") else list(preds)}

            proba = None
            if hasattr(model, "predict_proba"):
                probas = model.predict_proba(X)
                result["probabilities"] = probas.tolist() if hasattr(probas, "tolist") else list(probas)
                proba = {"probabilities": result["probabilities"]}

            # 统计
            unique, counts = np.unique(preds, return_counts=True)
            stats = {
                "样本数": len(preds),
                "预测类别分布": dict(zip([str(u) for u in unique], counts.tolist())),
                "输入维度": X.shape[1] if len(X.shape) > 1 else 1,
            }

            yield result, proba, stats

        except Exception as e:
            yield {"error": f"推理失败: {str(e)}"}, None, None

    predict_btn.click(
        do_predict,
        inputs=[model_source, saved_models, model_file, data_mode, json_input, csv_input_file, csv_path_input],
        outputs=[prediction_output, proba_output, batch_stats],
    )

    return prediction_output


# =============================================================================
# Tab 5: 数据
# =============================================================================

def data_tab():
    """数据预览页面"""
    gr.Markdown("## 📁 数据预览")

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="上传 CSV 文件", file_types=[".csv"])
            preview_btn = gr.Button("🔍 预览数据", variant="primary")

        with gr.Column(scale=2):
            preview_info = gr.JSON(label="数据基本信息")
            preview_stats = gr.DataFrame(label="统计描述")
            preview_table = gr.DataFrame(label="数据预览 (前50行)", wrap=True)

    def do_preview(file_obj):
        if file_obj is None:
            return gr.update(), gr.update(), "请上传文件"
        try:
            filepath = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            df = pd.read_csv(filepath)

            info = {
                "形状": f"{df.shape[0]} 行 × {df.shape[1]} 列",
                "内存": f"{df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB",
                "列数": df.shape[1],
                "行数": df.shape[0],
            }

            stats_df = df.describe().T
            stats_df.index.name = "列名"
            stats_df = stats_df.reset_index()

            preview_str = f"✅ 加载成功！{df.shape[0]} 行 × {df.shape[1]} 列"

            return info, stats_df, preview_str
        except Exception as e:
            return gr.update(), gr.update(), f"❌ 加载失败: {str(e)}"

    preview_btn.click(do_preview, inputs=[file_input], outputs=[preview_info, preview_stats, preview_table])

    return file_input


# =============================================================================
# 主界面
# =============================================================================

def create_app():
    """创建 Gradio 应用"""

    with gr.Blocks(
        title="ML Kit - 机器学习全流程平台",
    ) as app:

        # 标题区
        gr.Markdown("""
        # 🤖 ML Kit
        ### 机器学习全流程平台 | 基于 Harness Engineering 构建

---

        """.strip())

        # Tab 页面
        with gr.Tabs():
            with gr.Tab("📊 Dashboard", id="dashboard"):
                dashboard_tab()

            with gr.Tab("🏋️ 训练", id="train"):
                train_tab()

            with gr.Tab("🧪 实验", id="experiments"):
                experiments_tab()

            with gr.Tab("⚙️ 预处理", id="preprocess"):
                preprocessing_tab()

            with gr.Tab("🔮 推理", id="inference"):
                inference_tab()

            with gr.Tab("📁 数据", id="data"):
                data_tab()

        # 底部信息
        gr.Markdown("""
        ---

        **ML Kit** | 数据目录: `./data/` | 模型目录: `./checkpoints/` | 实验目录: `./experiments/`

        使用问题？查看 `examples/` 目录或阅读 `CLAUDE.md`
        """)

    return app


def main():
    """启动应用"""
    app = create_app()

    print("""
    ╔══════════════════════════════════════════════════════╗
    ║        ML Kit - Gradio UI v2 启动中...               ║
    ║                                                      ║
    ║  本地访问: http://localhost:7860                    ║
    ║  网络访问: http://0.0.0.0:7860                       ║
    ║                                                      ║
    ║  按 Ctrl+C 停止服务                                  ║
    ╚══════════════════════════════════════════════════════╝
    """)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        theme=DARK_THEME,
    )


if __name__ == "__main__":
    main()
