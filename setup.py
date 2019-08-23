from setuptools import setup

setup(name='ms_process',
      packages=['ms_process',
                'ms_process.cli',
                'ms_process.processing',
                ],
      version='0.1.0',
      entry_points={
          'console_scripts': [
              'mzxml = ms_process.cli.mzxml:main',
              'mzml = ms_process.cli.mzml:main',
          ]
      }, install_requires=['numpy', 'scipy', 'lxml', 'tqdm', 'PyMSNumpress']
      )