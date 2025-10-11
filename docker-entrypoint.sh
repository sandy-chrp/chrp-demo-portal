#!/bin/bash

python manage.py makemigrationa

python manage.py migrate

python manage.py collectstatic
