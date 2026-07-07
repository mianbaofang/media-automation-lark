import os
import sys

# 让 tests/ 能 import scripts/ 下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
