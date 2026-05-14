from pathlib import Path
import os

from setuptools import setup


package_name = "sparkrobot_dog_bridge"
package_dir = Path(package_name)
package_data_files = [
    str(path.relative_to(package_dir))
    for path in (package_dir / "vendor").rglob("*")
    if path.is_file()
]


setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    package_data={
        package_name: package_data_files,
    },
    include_package_data=True,
    data_files=[
        ("share/ament_index/resource_index/packages", [str(Path("resource") / package_name)]),
        (os.path.join("share", package_name), ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=False,
    maintainer="elric",
    maintainer_email="elric@example.com",
    description="机器狗 SDK 与 ROS2 之间的桥接节点",
    license="MIT",
    entry_points={
        "console_scripts": [
            "dog_bridge_node = sparkrobot_dog_bridge.dog_bridge_node:main",
        ],
    },
)
