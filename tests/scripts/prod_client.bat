
# RUN FROM esFrontLine PROJECT DIRECTORY
set PYTHONPATH=.;vendor
python tests/prod_client.py --settings=tests/config/prod_client.json
