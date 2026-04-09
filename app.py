# -*- coding: utf-8 -*-
"""
ML Kit - Gradio Web UI

机器学习训练与推理平台 Web 界面

启动方式:
    cd ml-all-in-one
    PYTHONPATH=src python app.py

或直接:
    python app.py
"""

import sys
import os

# 确保 src 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import json
import time
import traceback
from pathlib import Path

import gradio as gr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 核心模块
from mlkit import create_runner, Config, BaseModel
from mlkit.config import Config
from mlkit.data import Dataset, DataLoader
from mlkit.model import create_model
from mlkit.experiment import ExperimentManager, Experiment


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


# =============================================================================
# 工具函数
# =============================================================================

def plot_training_history(history: dict) -> plt.Figure:
    """绘制训练历史曲线"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # 训练历史
    train_history = history.get("train_history", [])
    val_history = history.get("val_history", [])

    epochs = [h.get("epoch", i) for i, h in enumerate(train_history)]
    train_acc = [h.get("train_acc", 0) for h in train_history]
    val_acc = [h.get("val_acc", 0) for h in val_history]

    # 准确率曲线
    if train_acc:
        axes[0].plot(epochs, train_acc, label="Train Acc", marker="o")
    if val_acc:
        axes[0].plot(epochs, val_acc, label="Val Acc", marker="s")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("Accuracy")
    axes[0].set_title("Accuracy over Epochs")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 损失曲线
    train_loss = [h.get("train_loss", 0) for h in train_history]
    val_loss = [h.get("val_loss", 0) for h in val_history]

    if train_loss:
        axes[1].plot(epochs, train_loss, label="Train Loss", marker="o")
    if val_loss:
        axes[1].plot(epochs, val_loss, label="Val Loss", marker="s")
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Loss")
    axes[1].set_title("Loss over Epochs")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_experiment_comparison(exp_ids: list, metric: str) -> plt.Figure:
    """绘制实验对比曲线"""
    fig, ax = plt.subplots(figsize=(10, 6))

    for exp_id in exp_ids:
        exp = experiment_manager.load_experiment(exp_id)
        if exp and metric in exp.metrics:
            records = exp.metrics[metric]
            steps = [r.step for r in records]
            values = [r.value for r in records]
            ax.plot(steps, values, label=exp.name, marker="o")

    ax.set_xlabel("Step / Epoch")
    ax.set_ylabel(metric)
    ax.set_title(f"Experiment Comparison - {metric}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def load_csv_preview(file_obj) -> tuple:
    """加载 CSV 文件并返回预览"""
    if file_obj is None:
        return None, "请上传文件"

    try:
        # Gradio 3.x 返回文件路径，4.x 返回 UploadedFile 对象
        if hasattr(file_obj, "name"):
            filepath = file_obj.name
        else:
            filepath = str(file_obj)

        df = pd.read_csv(filepath)
        preview = f"✅ 成功加载！\n\n形状: {df.shape[0]} 行 × {df.shape[1]} 列\n\n列名:\n" + "\n".join(f"  • {c} ({df[c].dtype})" for c in df.columns)
        preview += f"\n\n前5行预览:\n{df.head().to_string()}"

        return df, preview
    except Exception as e:
        return None, f"❌ 加载失败: {str(e)}"


# =============================================================================
# Tab 1: 训练页面
# =============================================================================

def train_tab():
    """训练页面"""
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 📊 训练配置")

            # 数据上传
            train_file = gr.File(label="训练数据 (CSV)", file_types=[".csv"])
            test_file = gr.File(label="测试数据 (CSV, 可选)", file_types=[".csv"])

            # 数据配置
            target_column = gr.Textbox(label="目标列名", placeholder="如: target, label, y")

            # 模型选择
            model_type = gr.Dropdown(
                ["sklearn", "xgboost", "lightgbm", "pytorch"],
                label="模型类型",
                value="sklearn"
            )

            sklearn_model = gr.Dropdown(
                ["RandomForestClassifier", "RandomForestRegressor",
                 "LogisticRegression", "GradientBoostingClassifier"],
                label="Sklearn 模型",
                value="RandomForestClassifier",
                visible=True
            )

            task_type = gr.Radio(
                ["classification", "regression"],
                label="任务类型",
                value="classification"
            )

            # 训练参数
            gr.Markdown("### 训练参数")
            n_estimators = gr.Slider(1, 500, value=100, step=1, label="n_estimators")
            max_depth = gr.Slider(1, 30, value=10, step=1, label="max_depth")
            epochs = gr.Slider(1, 100, value=10, step=1, label="Epochs")
            val_ratio = gr.Slider(0.1, 0.4, value=0.2, step=0.05, label="验证集比例")

            # Hooks
            gr.Markdown("### 训练监控")
            enable_logger = gr.Checkbox(label="启用日志记录", value=True)
            enable_checkpoint = gr.Checkbox(label="保存检查点", value=True)
            enable_early_stopping = gr.Checkbox(label="启用早停", value=False)

            patience = gr.Slider(3, 30, value=10, step=1, label="Patience (早停)", visible=False)
            monitor_metric = gr.Dropdown(
                ["val_acc", "val_loss", "val_f1"],
                label="监控指标",
                value="val_acc",
                visible=True
            )

            # 实验名称
            exp_name = gr.Textbox(
                label="实验名称",
                placeholder="如: baseline-v1",
                value=""
            )

            # 训练按钮
            train_btn = gr.Button("🚀 开始训练", variant="primary")
            status_text = gr.Textbox(label="状态", lines=3, interactive=False)

        with gr.Column(scale=2):
            # 结果展示
            gr.Markdown("## 📈 训练结果")
            plot_output = gr.Plot(label="训练曲线")
            result_text = gr.JSON(label="训练结果 JSON")

            # 模型信息
            gr.Markdown("## 🤖 模型信息")
            model_info = gr.JSON(label="模型参数")

    # 事件绑定
    def update_visibility(task):
        return gr.update(visible=(task == "classification")), gr.update(visible=True)

    task_type.change(
        update_visibility,
        inputs=[task_type],
        outputs=[sklearn_model, enable_early_stopping]
    )

    enable_early_stopping.change(
        lambda x: gr.update(visible=x),
        inputs=[enable_early_stopping],
        outputs=[patience]
    )

    def do_train(
        train_file, test_file, target_column, model_type, sklearn_model, task_type,
        n_estimators, max_depth, epochs, val_ratio,
        enable_logger, enable_checkpoint, enable_early_stopping,
        patience, monitor_metric, exp_name
    ):
        """执行训练"""
        try:
            yield "⏳ 正在初始化训练...", None, None, None

            # 检查数据
            if train_file is None:
                yield "❌ 请先上传训练数据", None, None, None
                return

            filepath = train_file.name if hasattr(train_file, "name") else str(train_file)

            # 自动检测目标列
            df_full = pd.read_csv(filepath)
            if not target_column or target_column not in df_full.columns:
                target_column = df_full.columns[-1]  # 默认最后一列

            # 分离特征和标签
            y_full = df_full[target_column].values
            X_full = df_full.drop(columns=[target_column]).values
            feature_names = [c for c in df_full.columns if c != target_column]

            # 划分训练集和验证集
            from sklearn.model_selection import train_test_split
            X_train, X_val, y_train, y_val = train_test_split(
                X_full, y_full, test_size=val_ratio, random_state=42
            )

            yield "⏳ 正在准备数据...", None, None, None

            # 创建实验
            exp = None
            if exp_name:
                params = {
                    "model_type": model_type,
                    "task_type": task_type,
                    "n_estimators": n_estimators,
                    "max_depth": max_depth,
                    "epochs": epochs,
                    "val_ratio": val_ratio,
                }
                exp = experiment_manager.create_experiment(exp_name, params=params)

            # 构建配置
            config_dict = {
                "model": {
                    "type": model_type,
                    "task": task_type,
                    "model_class": sklearn_model if model_type == "sklearn" else None,
                    "n_estimators": int(n_estimators),
                    "max_depth": int(max_depth),
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

            yield "⏳ 正在构建 Runner...", None, None, None

            runner = create_runner(config, experiment=exp)
            runner.train_dataset = Dataset(X_train, y_train, feature_names=feature_names)
            runner.val_dataset = Dataset(X_val, y_val, feature_names=feature_names)

            yield "🏃 训练进行中...", None, None, None

            # 训练
            history = runner.train()

            yield "✅ 训练完成！正在生成报告...", history, None, None

            # 绘制曲线
            fig = plot_training_history(history)

            # 保存实验
            if exp:
                exp.finish(status="completed")
                experiment_manager.save_experiment(exp)

            # 模型信息
            model_params = {
                "model_type": model_type,
                "task_type": task_type,
                "n_estimators": int(n_estimators),
                "max_depth": int(max_depth),
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "n_features": X_train.shape[1],
            }

            result = {
                "train_history_len": len(history["train_history"]),
                "val_history_len": len(history["val_history"]),
                "final_metrics": history["val_history"][-1] if history["val_history"] else {},
            }

            yield f"🎉 训练成功！\n\n验证准确率: {history['val_history'][-1].get('val_acc', 'N/A'):.4f}" if history['val_history'] else "🎉 训练完成", fig, result, model_params

        except Exception as e:
            yield f"❌ 训练失败: {str(e)}\n\n{traceback.format_exc()}", None, None, None

    train_btn.click(
        do_train,
        inputs=[
            train_file, test_file, target_column, model_type, sklearn_model, task_type,
            n_estimators, max_depth, epochs, val_ratio,
            enable_logger, enable_checkpoint, enable_early_stopping,
            patience, monitor_metric, exp_name
        ],
        outputs=[status_text, plot_output, result_text, model_info]
    )

    return train_file, status_text, plot_output


# =============================================================================
# Tab 2: 实验管理
# =============================================================================

def experiments_tab():
    """实验管理页面"""
    gr.Markdown("## 📋 实验管理")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 实验列表")
            experiments_table = gr.DataFrame(
                label="历史实验",
                headers=["ID", "名称", "状态", "耗时(s)", "最佳指标"],
                interactive=False
            )
            refresh_btn = gr.Button("🔄 刷新实验列表")

        with gr.Column(scale=2):
            gr.Markdown("### 实验详情")
            exp_detail = gr.JSON(label="实验详情")
            exp_report = gr.Markdown("选择实验查看报告")

    def load_experiments():
        """加载实验列表"""
        exps = experiment_manager.load_all()
        if not exps:
            return pd.DataFrame(
                columns=["ID", "名称", "状态", "耗时(s)", "最佳指标"]
            )

        rows = []
        for exp_id, exp in exps.items():
            best = ", ".join([f"{k}={v:.4f}" for k, v in exp.best_metrics.items()])
            rows.append({
                "ID": exp_id[:20] + "..." if len(exp_id) > 20 else exp_id,
                "名称": exp.name,
                "状态": exp.status,
                "耗时(s)": f"{exp.duration:.1f}" if exp.duration else "N/A",
                "最佳指标": best or "N/A",
            })

        return pd.DataFrame(rows)

    def on_select_exp(evt: gr.SelectData):
        """选择实验"""
        exps = experiment_manager.load_all()
        for exp_id, exp in exps.items():
            if exp_id.startswith(evt.value[:20]) or exp_id.startswith(evt.value.replace("...", "")):
                report = experiment_manager.generate_report([exp_id])
                return exp.to_dict(), report
        return {}, "未找到实验"

    def compare_selected(exp_table):
        """对比选中的实验"""
        if exp_table is None or len(exp_table) == 0:
            return gr.update(visible=True), None

        selected_ids = []
        exps = experiment_manager.load_all()
        for row in exp_table:
            name = row.get("名称", "")
            for exp_id, exp in exps.items():
                if exp.name == name:
                    selected_ids.append(exp_id)
                    break

        if not selected_ids:
            return gr.update(visible=True), None

        metric = "val_acc"
        fig = plot_experiment_comparison(selected_ids, metric)
        report = experiment_manager.generate_report(selected_ids)
        return fig, report

    refresh_btn.click(
        load_experiments,
        outputs=[experiments_table]
    )

    experiments_table.select(
        on_select_exp,
        outputs=[exp_detail, exp_report]
    )

    return experiments_table


# =============================================================================
# Tab 3: 模型推理
# =============================================================================

def inference_tab():
    """推理页面"""
    gr.Markdown("## 🔮 模型推理")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 输入数据")

            # 模型选择
            model_source = gr.Radio(
                ["已训练的模型", "上传模型文件"],
                label="模型来源",
                value="已训练的模型"
            )

            def list_saved_models():
                """列出已保存的模型"""
                models = []
                for f in CHECKPOINTS_DIR.glob("*"):
                    if f.suffix in [".pkl", ".pth", ".joblib"]:
                        models.append(f.name)
                return models or ["(无已保存模型)"]

            saved_models = gr.Dropdown(
                label="选择已训练模型",
                choices=[],
            )
            refresh_models_btn = gr.Button("🔄 刷新模型列表", size="sm")

            model_file = gr.File(
                label="上传模型文件 (.pkl, .joblib)",
                file_types=[".pkl", ".joblib"],
                visible=False
            )

            # 数据输入
            data_input = gr.Textbox(
                label="输入数据 (JSON 数组或 CSV 路径)",
                placeholder='[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n或填写 CSV 文件路径',
                lines=5
            )

            predict_btn = gr.Button("🔮 推理", variant="primary")

        with gr.Column(scale=2):
            gr.Markdown("### 推理结果")
            prediction_output = gr.JSON(label="预测结果")
            proba_output = gr.JSON(label="预测概率")

    def list_saved_models():
        """列出已保存的模型"""
        models = []
        for f in CHECKPOINTS_DIR.glob("*"):
            if f.suffix in [".pkl", ".pth", ".joblib"]:
                models.append(f.name)
        return models or ["(无已保存模型)"]

    def refresh_models():
        return gr.update(choices=list_saved_models())

    def do_predict(model_source, model_choice, model_file, data_input):
        """执行推理"""
        try:
            # 加载模型
            if model_source == "已训练的模型" and model_choice and model_choice != "(无已保存模型)":
                model_path = CHECKPOINTS_DIR / model_choice
                if not model_path.exists():
                    yield {"error": f"模型文件不存在: {model_choice}"}, None
                    return

                import joblib
                model = joblib.load(model_path)
                yield {"status": f"已加载模型: {model_choice}"}, None

            elif model_source == "上传模型文件":
                if model_file is None:
                    yield {"error": "请上传模型文件"}, None
                    return
                filepath = model_file.name if hasattr(model_file, "name") else str(model_file)
                import joblib
                model = joblib.load(filepath)
                yield {"status": f"已上传模型: {model_file.name if hasattr(model_file, 'name') else filepath}"}, None

            else:
                yield {"error": "请先选择或上传模型"}, None
                return

            # 解析数据
            data_input = data_input.strip()
            if not data_input:
                yield {"error": "请输入数据"}, None
                return

            # 尝试 JSON 解析
            try:
                data = json.loads(data_input)
                if isinstance(data, list):
                    X = np.array(data)
                else:
                    X = pd.DataFrame(data)
            except json.JSONDecodeError:
                # 尝试作为文件路径
                if os.path.exists(data_input):
                    X = pd.read_csv(data_input).values
                else:
                    yield {"error": f"无法解析数据: {data_input[:50]}..."}, None
                    return

            yield {"status": "正在推理...", "input_shape": str(X.shape)}, None

            # 推理
            if hasattr(model, "predict"):
                preds = model.predict(X)
                result = {"predictions": preds.tolist() if hasattr(preds, "tolist") else list(preds)}

                # 概率
                if hasattr(model, "predict_proba"):
                    probas = model.predict_proba(X)
                    result["probabilities"] = probas.tolist() if hasattr(probas, "tolist") else list(probas)

                yield result, probas if "probabilities" in result else None
            else:
                yield {"error": "模型不支持 predict 方法"}, None

        except Exception as e:
            yield {"error": f"推理失败: {str(e)}"}, None

    model_source.change(
        lambda x: [gr.update(visible=x=="已训练的模型"), gr.update(visible=x=="上传模型文件")],
        inputs=[model_source],
        outputs=[saved_models, model_file]
    )

    refresh_models_btn.click(refresh_models, outputs=[saved_models])
    predict_btn.click(do_predict, inputs=[model_source, saved_models, model_file, data_input], outputs=[prediction_output, proba_output])

    return prediction_output


# =============================================================================
# Tab 4: 数据预览
# =============================================================================

def data_tab():
    """数据预览页面"""
    gr.Markdown("## 📁 数据预览")

    with gr.Row():
        with gr.Column(scale=1):
            file_input = gr.File(label="上传 CSV 文件", file_types=[".csv"])
            preview_btn = gr.Button("🔍 预览数据")

        with gr.Column(scale=2):
            preview_info = gr.Textbox(label="数据信息", lines=8, interactive=False)
            preview_table = gr.DataFrame(label="数据预览 (前100行)")

    def do_preview(file_obj):
        if file_obj is None:
            return "请上传文件", gr.update()
        try:
            filepath = file_obj.name if hasattr(file_obj, "name") else str(file_obj)
            df = pd.read_csv(filepath)

            info = f"✅ 成功加载\n\n形状: {df.shape[0]} 行 × {df.shape[1]} 列\n\n列信息:\n"
            for col in df.columns:
                info += f"  • {col}: {df[col].dtype}, 非空 {df[col].count()}/{len(df)}\n"

            return info, df.head(100)
        except Exception as e:
            return f"❌ 加载失败: {str(e)}", gr.update()

    preview_btn.click(do_preview, inputs=[file_input], outputs=[preview_info, preview_table])

    return file_input


# =============================================================================
# 主界面
# =============================================================================

def create_app():
    """创建 Gradio 应用"""

    with gr.Blocks(
        title="ML Kit - 机器学习训练平台",
    ) as app:

        # 标题
        gr.Markdown("""
        # 🤖 ML Kit - 机器学习全流程平台

        基于 Harness Engineering 理念构建的 ML 训练平台。
        支持多种模型、自动实验追踪、Gradio Web UI。
        """)

        # Tab 页面
        with gr.Tabs():
            with gr.Tab("🏋️ 训练", id="train"):
                train_tab()

            with gr.Tab("📋 实验", id="experiments"):
                experiments_tab()

            with gr.Tab("🔮 推理", id="inference"):
                inference_tab()

            with gr.Tab("📁 数据", id="data"):
                data_tab()

        # 底部信息
        gr.Markdown("""
        ---
        ### 使用说明

        1. **训练**: 上传 CSV 数据 → 配置参数 → 开始训练
        2. **实验**: 查看历史实验 → 对比结果
        3. **推理**: 选择模型 → 输入数据 → 获取预测

        模型文件保存在 `./checkpoints/`，实验记录保存在 `./experiments/`
        """)

    return app


def main():
    """启动应用"""
    app = create_app()

    print("""
    ╔══════════════════════════════════════════════════╗
    ║         ML Kit - Gradio UI 启动中...            ║
    ║                                                  ║
    ║  本地访问: http://localhost:7860                 ║
    ║  网络访问: http://0.0.0.0:7860                   ║
    ║                                                  ║
    ║  按 Ctrl+C 停止服务                              ║
    ╚══════════════════════════════════════════════════╝
    """)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )


if __name__ == "__main__":
    main()
