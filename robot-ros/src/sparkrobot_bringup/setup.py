from glob import glob
from pathlib import Path
import os

from setuptools import setup


package_name = "sparkrobot_bringup"


setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [str(Path("resource") / package_name)]),
        (os.path.join("share", package_name), ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="elric",
    maintainer_email="elric@example.com",
    description="机器狗 N10P 激光雷达与导航 bringup 封装",
    license="MIT",
)
