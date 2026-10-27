import os
import sys
from pathlib import Path

local_data = Path(__file__).resolve().parents[1] / ".localappdata"
local_data.mkdir(exist_ok=True)
os.environ["LOCALAPPDATA"] = str(local_data)
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_DISABLED"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
