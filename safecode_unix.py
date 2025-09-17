import sys
from types import SimpleNamespace
import signal
import toml
import os

config_path = os.path.join(os.path.dirname(__file__), "config.toml")
if os.path.exists(config_path):
    config = toml.load(config_path)
    TIMEOUT = config.get("timeout", 3)
else:
    TIMEOUT = 3

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Code execution timed out")

# Use signal for timeout (Unix only)
def run_cell(cell_code, test_ns):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(TIMEOUT)
    try:
        exec(cell_code, test_ns.__dict__)
    except TimeoutException:
        return "__DEADLOOP__"
    except Exception as e:
        raise e
    finally:
        signal.alarm(0)
