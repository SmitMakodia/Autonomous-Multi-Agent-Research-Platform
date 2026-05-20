import os
import sys
import builtins
import inspect
import logging
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

log_filepath = LOGS_DIR / "log.log"

class TeeStream:
    """Clones all terminal output byte-for-byte directly to log.log natively in Python."""
    def __init__(self, stream, file_path):
        self.stream = stream
        self.file_path = file_path
        self.file = open(self.file_path, 'a', encoding='utf-8')

    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
        try:
            self.file.write(data)
            self.file.flush()
        except:
            pass

    def flush(self):
        self.stream.flush()
        try:
            self.file.flush()
        except:
            pass
            
    def isatty(self):
        return False

# Override stdout and stderr to clone directly to the file!
sys.stdout = TeeStream(sys.stdout, log_filepath)
sys.stderr = TeeStream(sys.stderr, log_filepath)

# Override print to prepend file/line number cleanly
_original_print = builtins.print

def _custom_print(*args, **kwargs):
    try:
        frame = inspect.currentframe()
        caller_frame = frame.f_back if frame else None
        
        prefix = ""
        # Only inject the prefix if we are starting a fresh line!
        # If kwargs contains `end=""`, it means we are streaming, so don't inject prefix on every token!
        is_streaming = kwargs.get('end', '\n') != '\n'
        
        if caller_frame and not getattr(_custom_print, 'is_streaming_mode', False):
            file_name = os.path.basename(caller_frame.f_code.co_filename)
            line_no = caller_frame.f_lineno
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prefix = f"[{timestamp}] [{file_name}:{line_no}] "
            
        _custom_print.is_streaming_mode = is_streaming
        
        if args and prefix:
            first_arg = str(args[0])
            new_args = (prefix + first_arg,) + args[1:]
            _original_print(*new_args, **kwargs)
        else:
            _original_print(*args, **kwargs)
            
    except Exception:
        _original_print(*args, **kwargs)

_custom_print.is_streaming_mode = False
builtins.print = _custom_print

print(f"Native terminal logging active. Output is mirrored to {log_filepath}")
