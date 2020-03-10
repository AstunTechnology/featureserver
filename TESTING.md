# Testing FeatureServer

## Setup

* Create a virtual environment
* Install dependencies

```
pip -r requirements.txt
```

* Run the tests:

```
python tests/tests.py
```

## Overview

Currently tests are doctests which resemble the output of an interactive session which uses various aspects of the FeatureServer API.

### PostGIS

The PostGIS DataSource tests create a temporary Postgres cluster and associated database during execution. If at any point you'd like to pause the tests and inspect the database you can use the approach [outlined here](https://github.com/walkermatt/python-postgres-testing-demo#connecting-to-the-temporary-database).
