"""
task_runner.py
==============
Entry point only. All logic lives in runner/.

See runner/loop.py for the database access model and startup notes.
"""

from runner.loop import run_loop

if __name__ == "__main__":
    run_loop()
