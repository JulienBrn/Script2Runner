from setuptools import setup, find_packages


setup(
    name='Script2Runner',
    packages=find_packages(where='src'),
    package_data={
        "Script2Runner.package_data": ["*"],
    },
    entry_points={
        'console_scripts': [
            'Script2Runner = Script2Runner:run',
        ]
    },
    version='0.1',
    license='MIT',
    description = 'My package description',
    description_file = "README.md",
    author="Julien Braine",
    author_email='julienbraine@yahoo.fr',
    url='https://github.com/JulienBrn/Script2Runner',
    download_url = 'https://github.com/JulienBrn/Script2Runner.git',
    package_dir={'': 'src'},
    keywords=['python'],
    install_requires=[],
    #['pandas', 'matplotlib', 'PyQt5', "sklearn", "scikit-learn", "scipy", "numpy", "tqdm", "beautifullogger", "statsmodels", "mat73", "psutil"],
    python_requires=">=3.10"
)
