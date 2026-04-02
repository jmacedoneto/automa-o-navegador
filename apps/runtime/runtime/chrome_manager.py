from pathlib import Path


def chrome_user_data_dir(base_dir: str = ".runtime-profile") -> str:
    return str(Path(base_dir).resolve())
