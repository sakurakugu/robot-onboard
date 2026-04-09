import copy
import threading

from .models import (
    IMU状态,
    任务状态,
    位姿状态,
    健康状态,
    定位状态,
    导航状态,
    建图状态,
    机器人状态快照,
    激光雷达状态,
    运控桥状态,
    里程状态,
)


class 机器人状态存储:
    """线程安全的运行时状态存储。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = 机器人状态快照()

    def 获取快照(self) -> 机器人状态快照:
        """获取当前状态快照。"""
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def 更新健康状态(self, state: 健康状态) -> None:
        with self._lock:
            self._snapshot.健康 = copy.deepcopy(state)

    def 更新运控桥状态(self, state: 运控桥状态) -> None:
        with self._lock:
            self._snapshot.运控桥 = copy.deepcopy(state)

    def 更新位姿状态(self, state: 位姿状态) -> None:
        with self._lock:
            self._snapshot.位姿 = copy.deepcopy(state)

    def 更新里程状态(self, state: 里程状态) -> None:
        with self._lock:
            self._snapshot.里程 = copy.deepcopy(state)

    def 更新IMU状态(self, state: IMU状态) -> None:
        with self._lock:
            self._snapshot.IMU = copy.deepcopy(state)

    def 更新激光雷达状态(self, state: 激光雷达状态) -> None:
        with self._lock:
            self._snapshot.激光雷达 = copy.deepcopy(state)

    def 更新建图状态(self, state: 建图状态) -> None:
        with self._lock:
            self._snapshot.建图 = copy.deepcopy(state)

    def 更新定位状态(self, state: 定位状态) -> None:
        with self._lock:
            self._snapshot.定位 = copy.deepcopy(state)

    def 更新导航状态(self, state: 导航状态) -> None:
        with self._lock:
            self._snapshot.导航 = copy.deepcopy(state)

    def 更新任务状态(self, state: 任务状态) -> None:
        with self._lock:
            self._snapshot.任务 = copy.deepcopy(state)
