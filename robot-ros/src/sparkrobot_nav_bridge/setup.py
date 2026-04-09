from pathlib import Path
import os

from setuptools import setup


package_name = "sparkrobot_nav_bridge"


setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [str(Path("resource") / package_name)]),
        (os.path.join("share", package_name), ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="elric",
    maintainer_email="elric@example.com",
    description="机器狗运行时与 ROS2 导航栈的桥接节点",
    license="MIT",
    entry_points={
        "console_scripts": [
            "runtime_bridge_node = sparkrobot_nav_bridge.runtime_bridge_node:main",
        ],
    },
)
