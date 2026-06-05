import os
import csv
from pathlib import Path
from typing import List

from loguru import logger


def save_error_ids_to_csv(error_ids: List, filename: str = "error_ids") -> str:
    """
    Добавляет новые ID в конец файла (даже с дубликатами)
    """
    Path("reports").mkdir(exist_ok=True)
    filepath = f"reports/{filename}.csv"

    file_exists = os.path.exists(filepath)

    with open(filepath, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["telegram_id"])

        for id_value in error_ids:
            writer.writerow([str(id_value)])

    logger.info(f"Добавлено {len(error_ids)} ID в файл: {filepath}")
    return filepath
