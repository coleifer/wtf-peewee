from setuptools import setup


setup(
    name='wtf-peewee',
    version='3.0.1',
    url='https://github.com/coleifer/wtf-peewee/',
    license='MIT',
    author='Charles Leifer',
    author_email='coleifer@gmail.com',
    description='WTForms integration for peewee models',
    packages=['wtfpeewee'],
    zip_safe=False,
    platforms='any',
    install_requires=[
        'peewee>=3.0.0', 'wtforms',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    test_suite='runtests.runtests'
)
