"""
性能监控 Hook（PerformanceMonitorHook）单元测试

覆盖：初始化、CPU 采样、内存采样、GPU 采样（mock）
"""
import time
import threading
from unittest.mock import MagicMock, patch

import pytest


class TestPerformanceMonitorHookInit:
    """PerformanceMonitorHook 初始化测试"""

    def test_performance_monitor_init_default(self):
        """测试默认参数初始化"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()

        assert hook.interval == 5.0
        assert hook.log_to_stdout is True
        assert hook.record_to_experiment is False
        assert hook.experiment is None
        assert hook._has_gpu is not None  # 自动检测

    def test_performance_monitor_init_custom(self):
        """测试自定义参数初始化"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(
            interval=2.0,
            log_to_stdout=False,
            record_to_experiment=True,
        )

        assert hook.interval == 2.0
        assert hook.log_to_stdout is False
        assert hook.record_to_experiment is True

    def test_performance_monitor_init_experiment(self):
        """测试绑定 Experiment 实例"""
        from mlkit.hooks import PerformanceMonitorHook

        mock_exp = MagicMock()
        hook = PerformanceMonitorHook(
            interval=1.0,
            record_to_experiment=True,
            experiment=mock_exp,
        )

        assert hook.experiment is mock_exp
        assert hook.record_to_experiment is True

    def test_performance_monitor_psutil_available(self):
        """测试 psutil 可用性检测"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        assert hook._psutil is not None  # psutil 应该被成功导入


class TestPerformanceMonitorCPUSampling:
    """CPU 采样测试"""

    def test_sample_cpu_returns_float(self):
        """测试 CPU 采样返回浮点数"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.01)
        cpu_pct = hook._sample_cpu()

        assert isinstance(cpu_pct, float)
        assert 0.0 <= cpu_pct <= 100.0  # CPU 使用率范围

    def test_sample_cpu_accumulates_samples(self):
        """测试 CPU 采样数据被正确累积"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.01)

        # 连续采样多次
        for _ in range(5):
            hook._sample_cpu()

        assert len(hook._cpu_samples) == 5
        assert all(isinstance(v, float) for v in hook._cpu_samples)

    def test_sample_cpu_mock(self):
        """测试 CPU 采样使用 psutil"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()

        # 替换 _psutil.cpu_percent
        original = hook._psutil.cpu_percent
        hook._psutil.cpu_percent = MagicMock(return_value=75.5)

        result = hook._sample_cpu()

        hook._psutil.cpu_percent = original  # 恢复
        assert result == 75.5
        assert 75.5 in hook._cpu_samples


class TestPerformanceMonitorMemorySampling:
    """内存采样测试"""

    def test_sample_memory_returns_float(self):
        """测试内存采样返回浮点数（GB）"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.01)
        mem_gb = hook._sample_memory()

        assert isinstance(mem_gb, float)
        assert mem_gb >= 0.0  # 内存使用量非负

    def test_sample_memory_accumulates_samples(self):
        """测试内存采样数据被正确累积"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.01)

        for _ in range(3):
            hook._sample_memory()

        assert len(hook._mem_samples) == 3

    def test_sample_memory_mock(self):
        """测试内存采样使用 psutil.virtual_memory"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()

        # Mock virtual_memory
        mock_vm = MagicMock()
        mock_vm.used = 8 * (1024**3)  # 8 GB
        original = hook._psutil.virtual_memory
        hook._psutil.virtual_memory = MagicMock(return_value=mock_vm)

        result = hook._sample_memory()

        hook._psutil.virtual_memory = original  # 恢复
        mock_vm.used  # 验证访问过
        # 8 GB = 8 * 1024^3 bytes = 8.0 GB
        assert abs(result - 8.0) < 0.01


class TestPerformanceMonitorGPUSampling:
    """GPU 采样测试（有/无 GPU 环境）"""

    def test_sample_gpu_no_gpu(self):
        """测试无 GPU 时返回 0.0"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        # 强制无 GPU
        hook._has_gpu = False

        result = hook._sample_gpu()
        assert result == 0.0

    def test_sample_gpu_with_torch_mock(self):
        """测试有 GPU 时通过 torch.cuda 采样（mock）"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        hook._has_gpu = True

        with patch.object(hook, "_torch") as mock_torch:
            mock_dev = MagicMock()
            mock_dev.total_memory = 16 * (1024**3)  # 16 GB
            mock_torch.cuda.get_device_properties = MagicMock(
                return_value=mock_dev
            )
            mock_torch.cuda.memory_allocated = MagicMock(
                return_value=4 * (1024**3)
            )  # 4 GB used

            result = hook._sample_gpu()

            # 4GB / 16GB = 25%
            assert abs(result - 25.0) < 0.1
            assert 25.0 in hook._gpu_samples


class TestPerformanceMonitorReset:
    """重置功能测试"""

    def test_reset_clears_all_samples(self):
        """测试 _reset 清空所有采样数据"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        # 填充一些数据
        hook._sample_cpu()
        hook._sample_memory()
        hook._cpu_samples.append(50.0)
        hook._mem_samples.append(4.0)
        hook._gpu_samples.append(30.0)
        hook._speed_samples.append(1000.0)
        hook._total_samples_processed = 5000

        hook._reset()

        assert len(hook._cpu_samples) == 0
        assert len(hook._mem_samples) == 0
        assert len(hook._gpu_samples) == 0
        assert len(hook._speed_samples) == 0
        assert hook._total_samples_processed == 0


class TestPerformanceMonitorLifecycle:
    """生命周期钩子测试"""

    def test_before_run_starts_monitor_thread(self):
        """测试 before_run 启动监控线程"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.05, log_to_stdout=False)
        mock_runner = MagicMock()
        mock_runner.num_epochs = 1
        mock_runner.current_epoch = 0

        hook.before_run(mock_runner)

        assert hook._stop_event is not None
        assert hook._monitor_thread is not None
        assert hook._monitor_thread.is_alive()

        # 清理
        hook._stop()

    def test_after_run_stops_monitor(self):
        """测试 after_run 停止监控线程"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook(interval=0.05, log_to_stdout=False)
        mock_runner = MagicMock()
        mock_runner.num_epochs = 1
        mock_runner.current_epoch = 0

        hook.before_run(mock_runner)
        hook.after_run(mock_runner)

        # 线程应该已停止
        assert not hook._monitor_thread.is_alive()

    def test_after_epoch_records_metrics(self):
        """测试 after_epoch 记录指标到 Experiment"""
        from mlkit.hooks import PerformanceMonitorHook

        mock_exp = MagicMock()
        hook = PerformanceMonitorHook(
            interval=0.01,
            record_to_experiment=True,
            experiment=mock_exp,
        )

        # 填充一些采样数据
        hook._sample_cpu()
        hook._sample_memory()
        hook._cpu_samples = [50.0, 60.0, 55.0]
        hook._mem_samples = [4.0, 4.2, 4.1]

        mock_runner = MagicMock()
        mock_runner.num_epochs = 1
        mock_runner.current_epoch = 1

        hook.after_epoch(mock_runner, epoch=1, logs={})

        # 验证记录了指标
        assert mock_exp.record_metric.called
        calls = mock_exp.record_metric.call_args_list
        metric_names = [c[0][0] for c in calls]
        assert "cpu_avg" in metric_names or "cpu_peak" in metric_names


class TestPerformanceMonitorSpeedEstimate:
    """速度估算测试"""

    def test_estimate_speed_with_progress(self):
        """测试有进度时的速度估算"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        hook._epoch_start_time = time.time() - 2.0  # 2 秒前
        hook._total_samples_processed = 1000
        hook._epoch_samples = 0

        speed = hook._estimate_speed(MagicMock())
        assert speed is not None
        assert speed >= 0.0
        # 1000 samples / 2 seconds
        assert speed > 0

    def test_estimate_speed_no_elapsed_time(self):
        """测试时间太短时返回 None"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        hook._epoch_start_time = time.time()  # 刚刚开始
        hook._total_samples_processed = 0
        hook._epoch_samples = 0

        speed = hook._estimate_speed(MagicMock())
        assert speed is None


class TestPerformanceMonitorLogSummary:
    """日志汇总测试"""

    def test_log_summary_with_data(self, capsys):
        """测试 _log_summary 输出正确格式"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        hook._cpu_samples = [50.0, 60.0, 55.0]
        hook._mem_samples = [4.0, 4.2, 5.0]
        hook._speed_samples = [1000.0, 1100.0]

        hook._log_summary()

        captured = capsys.readouterr()
        # 有数据时应输出 Performance 汇总
        assert "Performance" in captured.out or "CPU" in captured.out

    def test_log_summary_no_data(self, capsys):
        """测试无数据时不输出"""
        from mlkit.hooks import PerformanceMonitorHook

        hook = PerformanceMonitorHook()
        hook._cpu_samples.clear()

        hook._log_summary()

        captured = capsys.readouterr()
        # 空数据不输出 Performance 汇总
        assert "CPU" not in captured.out
