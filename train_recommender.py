#!/usr/bin/env python3
import os
import sys
import subprocess

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manage_py = os.path.join(base_dir, "manage.py")
    args = [sys.executable, manage_py, "train_recommender", *sys.argv[1:]]

    try:
        result = subprocess.run(args, check=True)
        sys.exit(result.returncode)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        sys.exit(1)
