import os
import sys
import random
from pathlib import Path

import numpy as np
import torch


def get_asset_path(relative_path):
    """ Get absolute path to resource as a STRING for compatibility """
    try:
        base_path = Path(sys._MEIPASS)
    except Exception:
        current_file_path = Path(__file__).resolve()
        base_path = current_file_path.parent.parent.parent

    final_path = base_path / relative_path

    # ALWAYS return as a string using forward slashes (works on Windows too)
    # This prevents the "argument of type 'WindowsPath' is not iterable" error
    return final_path.as_posix()


def set_reproducibility(seed: int = 42):
    """Sets all relevant seeds to ensure deterministic model output."""
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    # These flags are critical for PyTorch reproducibility on GPU/CPU
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False