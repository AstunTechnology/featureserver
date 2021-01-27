import sys
from setuptools import setup


classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS',
]

extra = {}
extra['data_files']=[('FeatureServer', ['featureserver.cfg'])]

with open('doc/Readme.txt', 'rb') as f:
    readme = f.read()
    setup(name='FeatureServer',
        version='1.12.python3',
        description='A server for geographic features on the web.',
        long_description=readme,
        author='Astun Technology',
        author_email='featureserver@astuntechnology.com',
        url='https://github.com/AstunTechnology/featureserver',
        license="MIT",
        packages=['FeatureServer', 
                    'FeatureServer.DataSource', 
                    'FeatureServer.Service',
                    'vectorformats.Formats',
                    'vectorformats',
                    'web_request'
                    ],
        scripts=['featureserver.cgi', 'featureserver.fcgi',
                'featureserver_install_config.py',
                'featureserver_http_server.py'],
        test_suite = 'tests.run_doc_tests',
        zip_safe = False,
        **extra 
    )
