import logging
import os
import time
import subprocess
import platform
from datetime import datetime
from typing import Dict, Any, Optional
from ctypes import CDLL, c_uint, byref, create_string_buffer, cast, POINTER, c_int32, c_int64
from ctypes.util import find_library

import psutil

try:
    import GPUtil

    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False

logger = logging.getLogger(__name__)


class SystemService:
    """系统监控服务 - 专注于CPU、内存、磁盘、GPU使用率"""

    def __init__(self):
        self.start_time = time.time()
        self._libc = None
        self._init_sysctl()

    def _init_sysctl(self):
        """初始化sysctl接口"""
        try:
            self._libc = CDLL(find_library('c'))
        except Exception:
            self._libc = None

    def _sysctl(self, name: str, output_type=str):
        """通过sysctl获取系统信息"""
        if not self._libc:
            return None
        
        try:
            size = c_uint(0)
            # 找出缓冲区大小
            self._libc.sysctlbyname(name.encode(), None, byref(size), None, 0)
            # 创建缓冲区
            buf = create_string_buffer(size.value)
            # 重新运行，提供缓冲区
            self._libc.sysctlbyname(name.encode(), buf, byref(size), None, 0)
            
            if output_type in (str, 'str'):
                return buf.value.decode() if buf.value else None
            if output_type in (int, 'int'):
                if size.value == 4:
                    return cast(buf, POINTER(c_int32)).contents.value
                if size.value == 8:
                    return cast(buf, POINTER(c_int64)).contents.value
            if output_type == 'raw':
                return buf.raw
        except Exception:
            return None

    def _get_cpu_usage_info(self) -> Dict[str, Any]:
        """获取CPU使用率信息"""
        try:
            # 获取总体CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 获取每个核心的使用率
            cpu_percent_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
            
            # 获取CPU基本信息
            cpu_count_physical = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            
            # 获取负载平均值（如果可用）
            load_avg = None
            if hasattr(os, 'getloadavg'):
                load_avg = os.getloadavg()
            
            return {
                'usage_percent': cpu_percent,
                'usage_per_core': cpu_percent_per_core,
                'count_physical': cpu_count_physical,
                'count_logical': cpu_count_logical,
                'load_average': load_avg,
                'status': 'available'
            }
        except Exception as e:
            logger.error(f"Failed to get CPU usage info: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def get_system_resources(self) -> Dict[str, Any]:
        """获取系统资源使用率信息"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_info = {
                'usage_percent': cpu_percent
            }

            # 内存使用率
            memory = psutil.virtual_memory()
            memory_info = {
                'percent': memory.percent
            }

            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_info = {
                'percent': round((disk.used / disk.total) * 100, 2)
            }

            # GPU使用率
            gpu_info = self._get_gpu_usage_info()

            return {
                'cpu': cpu_info,
                'memory': memory_info,
                'disk': disk_info,
                'gpu': gpu_info,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get system resources: {str(e)}")
            return {'error': str(e)}

    def _get_gpu_usage_info(self) -> Dict[str, Any]:
        """获取GPU使用率信息"""
        
        # 方法1: 使用GPUtil获取独立显卡信息（NVIDIA/AMD等）
        if GPU_AVAILABLE:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    # 如果有多个GPU，返回平均使用率
                    total_usage = sum(gpu.load * 100 for gpu in gpus)
                    average_usage = round(total_usage / len(gpus), 2)
                    
                    # 获取第一个GPU的详细信息作为代表
                    main_gpu = gpus[0]
                    return {
                        'usage_percent': average_usage,
                        'available': True,
                        'type': 'discrete',
                        'name': main_gpu.name,
                        'memory_used': main_gpu.memoryUsed,
                        'memory_total': main_gpu.memoryTotal,
                        'memory_percent': round((main_gpu.memoryUsed / main_gpu.memoryTotal) * 100, 2),
                        'temperature': main_gpu.temperature
                    }
            except Exception as e:
                logger.debug(f"GPUtil failed: {str(e)}")
        
        # 方法2: 检测Apple Silicon或其他集成GPU
        try:
            cpu_brand = self._sysctl('machdep.cpu.brand_string')
            if cpu_brand and any(chip in cpu_brand for chip in ['Apple M1', 'Apple M2', 'Apple M3']):
                # Apple Silicon集成GPU - 标记为可用但无法获取使用率
                return {
                    'usage_percent': 0,
                    'available': True,
                    'type': 'integrated',
                    'name': 'Apple Silicon GPU',
                    'note': '集成GPU，无法获取实时使用率'
                }
        except Exception:
            pass
        
        # 方法3: 通过系统信息检测其他GPU
        try:
            if platform.system() == 'Darwin':  # macOS
                result = subprocess.run(['system_profiler', 'SPDisplaysDataType'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    output = result.stdout
                    if 'Metal' in output or 'GPU' in output:
                        return {
                            'usage_percent': 0,
                            'available': True,
                            'type': 'system_detected',
                            'note': '系统检测到GPU但无法获取详细信息'
                        }
            elif platform.system() == 'Linux':
                # Linux系统可以尝试其他GPU检测方法
                try:
                    result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'], 
                                          capture_output=True, text=True, timeout=3)
                    if result.returncode == 0:
                        usage = float(result.stdout.strip())
                        return {
                            'usage_percent': usage,
                            'available': True,
                            'type': 'nvidia_smi',
                            'note': '通过nvidia-smi获取'
                        }
                except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
                    pass
        except Exception:
            pass
        
        # 如果所有方法都失败
        return {
            'usage_percent': 0, 
            'available': False,
            'note': '未检测到GPU或GPU不支持'
        }

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """获取进程信息"""
        try:
            process = psutil.Process(pid)

            # 基本信息
            info = {
                'pid': process.pid,
                'name': process.name(),
                'status': process.status(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                'cpu_percent': process.cpu_percent(),
                'memory_percent': process.memory_percent(),
                'num_threads': process.num_threads()
            }

            # 内存信息
            memory_info = process.memory_info()
            info['memory'] = {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'rss_mb': round(memory_info.rss / (1024 ** 2), 2),
                'vms_mb': round(memory_info.vms / (1024 ** 2), 2)
            }

            # 网络连接
            try:
                connections = process.connections()
                info['connections'] = len(connections)
                info['listening_ports'] = [
                    conn.laddr.port for conn in connections
                    if conn.status == psutil.CONN_LISTEN
                ]
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                info['connections'] = 0
                info['listening_ports'] = []

            return info

        except psutil.NoSuchProcess:
            return None

    def check_port_availability(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            connections = psutil.net_connections()
            for conn in connections:
                if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                    return False
            return True
        except Exception as e:
            logger.error(f"Failed to check port availability: {str(e)}")
            return False

    def find_available_port(self, start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
        """找到可用端口"""
        for port in range(start_port, end_port + 1):
            if self.check_port_availability(port):
                return port
        return None

    def kill_process(self, pid: int, force: bool = False) -> bool:
        """终止进程"""
        try:
            process = psutil.Process(pid)

            if force:
                process.kill()
            else:
                process.terminate()

            # 等待进程结束
            try:
                process.wait(timeout=10)
            except psutil.TimeoutExpired:
                if not force:
                    # 如果优雅关闭失败，强制终止
                    process.kill()
                    process.wait(timeout=5)

            return True

        except psutil.NoSuchProcess:
            return True  # 进程已经不存在
        except Exception as e:
            logger.error(f"Failed to terminate process PID {pid}: {str(e)}")
            return False

    def get_system_load(self) -> Dict[str, Any]:
        """获取系统负载信息"""
        try:
            # CPU负载
            cpu_percent = psutil.cpu_percent(interval=1)

            # 内存负载
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 磁盘I/O
            disk_io = psutil.disk_io_counters()

            # 网络I/O
            network_io = psutil.net_io_counters()

            # 进程数量
            process_count = len(psutil.pids())

            # 负载等级评估
            load_level = self._calculate_load_level(cpu_percent, memory_percent)

            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_io': {
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count
                } if disk_io else None,
                'network_io': {
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv
                },
                'process_count': process_count,
                'load_level': load_level,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get system load: {str(e)}")
            return {'error': str(e)}

    def _calculate_load_level(self, cpu_percent: float, memory_percent: float) -> str:
        """计算负载等级"""
        max_usage = max(cpu_percent, memory_percent)

        if max_usage < 30:
            return 'low'
        elif max_usage < 60:
            return 'medium'
        elif max_usage < 80:
            return 'high'
        else:
            return 'critical'

    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状况"""
        try:
            health_checks = []
            overall_status = 'healthy'

            # CPU检查
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_status = 'healthy' if cpu_percent < 80 else 'warning' if cpu_percent < 95 else 'critical'
            health_checks.append({
                'component': 'cpu',
                'status': cpu_status,
                'value': cpu_percent,
                'message': f'CPU使用率: {cpu_percent}%'
            })

            # 内存检查
            memory = psutil.virtual_memory()
            memory_status = 'healthy' if memory.percent < 80 else 'warning' if memory.percent < 95 else 'critical'
            health_checks.append({
                'component': 'memory',
                'status': memory_status,
                'value': memory.percent,
                'message': f'内存使用率: {memory.percent}%'
            })

            # 磁盘检查
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_status = 'healthy' if disk_percent < 80 else 'warning' if disk_percent < 95 else 'critical'
            health_checks.append({
                'component': 'disk',
                'status': disk_status,
                'value': disk_percent,
                'message': f'磁盘使用率: {disk_percent:.1f}%'
            })

            # 确定总体状态
            if any(check['status'] == 'critical' for check in health_checks):
                overall_status = 'critical'
            elif any(check['status'] == 'warning' for check in health_checks):
                overall_status = 'warning'

            return {
                'status': overall_status,
                'checks': health_checks,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"System health check failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
