from setuptools import find_packages, setup

setup(
	name="galcom-utils",
	version="0.1.0",
	description="Shared utility helpers for Galcom services",
	python_requires=">=3.10",
	packages=find_packages(include=["galcom_utils", "galcom_utils.*"]),
	install_requires=[
		"python-logging-loki>=0.3.1",
		"redis>=4.0.0",
		"rx>=3.0.0",
		"python-socketio>=5.0.0",
		"pyserial>=3.5",
	],
)
