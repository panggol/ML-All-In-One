# -*- coding: utf-8 -*-
"""
管道可视化

支持：
- 管道结构图（文本/ASCII）
- 管道流程图（Mermaid 格式）
"""

from typing import List, Dict, Any, Optional
from mlkit.preprocessing.pipeline import Pipeline


def plot_pipeline(
    pipeline: Pipeline,
    output_type: str = "text",
    save_path: Optional[str] = None,
) -> str:
    """
    可视化管道结构
    
    Args:
        pipeline: Pipeline 实例
        output_type: 输出类型 ("text", "mermaid", "dict")
        save_path: 保存路径
        
    Returns:
        可视化字符串 (text/mermaid) 或字典 (dict)
    """
    stages = pipeline.steps  # 直接从 pipeline.steps 获取
    
    if output_type == "dict":
        result = {
            "name": getattr(pipeline, 'name', None),
            "stages": [
                {
                    "name": name,
                    "type": step.__class__.__name__,
                    "params": step.get_params() if hasattr(step, 'get_params') else {}
                }
                for name, step in stages
            ]
        }
        if save_path:
            import json
            with open(save_path, 'w') as f:
                json.dump(result, f, indent=2)
        return result
    
    if output_type == "mermaid":
        lines = ["flowchart LR"]
        lines.append("    subgraph Pipeline")
        
        for i, (name, step) in enumerate(stages):
            node_id = f"S{i}"
            step_type = step.__class__.__name__
            node_label = f"{name}<br/>({step_type})"
            lines.append(f"        {node_id}[{node_label}]")
        
        lines.append("    end")
        
        for i in range(len(stages) - 1):
            lines.append(f"    S{i} --> S{i+1}")
        
        result = "\n".join(lines)
        if save_path:
            with open(save_path, 'w') as f:
                f.write(result)
        return result
    
    # text (ASCII)
    lines = ["=" * 50]
    lines.append(f"Pipeline: {getattr(pipeline, 'name', 'Unnamed') or 'Unnamed'}")
    lines.append("=" * 50)
    lines.append("")
    
    for i, (name, step) in enumerate(stages):
        step_type = step.__class__.__name__
        lines.append(f"Stage {i}: {name}")
        lines.append(f"  └─ {step_type}")
        
        if hasattr(step, 'get_params'):
            params = step.get_params()
            if params:
                lines.append(f"     └─ {params}")
        lines.append("")
    
    lines.append("=" * 50)
    result = "\n".join(lines)
    
    if save_path:
        with open(save_path, 'w') as f:
            f.write(result)
    
    return result


def format_pipeline_summary(pipeline: Pipeline) -> str:
    """
    格式化管道摘要信息
    
    Args:
        pipeline: Pipeline 实例
        
    Returns:
        摘要字符串
    """
    stages = pipeline.steps
    stage_names = [name for name, _ in stages]
    return f"Pipeline({' → '.join(stage_names)})"
