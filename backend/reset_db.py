"""Reset the working database to the original values before a full ticket run.

    python -m backend.reset_db
"""

import shutil

from .config import ORIGINAL_DB, WORKING_DB


def reset_db() -> None:
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)


if __name__ == "__main__":
    reset_db()
    print(f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}.")
