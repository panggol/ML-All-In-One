

def test_performance_monitor_hook():
    """测试性能监控 Hook 基本功能"""
    from mlkit.hooks import PerformanceMonitorHook

    hook = PerformanceMonitorHook(interval=0.1, log_to_stdout=True)
    assert hook.interval == 0.1
    assert hook.log_to_stdout is True
    assert hook.record_to_experiment is False
    assert hook._psutil is not None  # psutil 可用
    # GPU 默认不可用（测试环境无 GPU）
    print("PerformanceMonitorHook 基本功能正常")
