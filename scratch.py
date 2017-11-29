import json
import os
import storage
import datetime
import time

dt = datetime.datetime.now() - datetime.timedelta(days=365)
print(time.time() - dt.timestamp())
