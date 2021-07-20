python3 -m pip install --upgrade jinja2
python3 -m pip install --upgrade dateparser
python3 -m pip install --upgrade psutil
python3 -m pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 -m pip install --upgrade PyDriller
python3 -m pip install --upgrade pyinstaller
python3 -m pip install --upgrade python-dateutil
python3 -m pip install --upgrade elasticsearch

brew tap elastic/tap
brew install elastic/tap/elasticsearch-full
brew install elastic/tap/kibana-full