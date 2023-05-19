import os
import time
import argparse
import logging
import concurrent.futures
from pathlib import Path
from tqdm import tqdm

class FileScanner:
    def __init__(self, dir_path, size_limit, days_limit, excluded_extensions, trash_dir):
        self.dir_path = Path(dir_path)
        self.size_limit = size_limit
        self.days_limit = days_limit
        self.excluded_extensions = set(excluded_extensions)
        self.trash_dir = Path(trash_dir)
        self.files_to_move = []

        logging.basicConfig(filename=str(self.trash_dir / 'file_scanner.log'), 
                            level=os.environ.get('LOGGING_LEVEL', logging.INFO),
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info('Initialized FileScanner with dir_path: %s, size_limit: %s, days_limit: %s, excluded_extensions: %s, trash_dir: %s',
                     dir_path, size_limit, days_limit, excluded_extensions, trash_dir)

    @staticmethod
    def file_age_in_days(file_path):
        return (time.time() - file_path.stat().st_mtime) / (60*60*24)

    def count_files(self):
        return sum(1 for _ in self.scan_files())

    def scan_files(self):
        for entry in self.dir_path.rglob('*'):
            if entry.is_file():
                yield entry

    def process_file(self, file_path, file_handler, pbar):
        try:
            if (file_path.stat().st_size > self.size_limit and
                self.file_age_in_days(file_path) > self.days_limit and
                file_path.suffix not in self.excluded_extensions):
                self.files_to_move.append(file_path)
                logging.info('Added file to move: %s', file_path)
                if file_handler is not None:
                    file_handler(file_path)
        except FileNotFoundError:
            logging.error('File not found: %s', file_path)
        pbar.update()

    def total_size_in_gb(self):
        total_size = sum(file_path.stat().st_size for file_path in self.files_to_move)
        return total_size / (1024 * 1024 * 1024)  # Convert bytes to gigabytes

    def move_files_to_trash(self):
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        with tqdm(total=len(self.files_to_move), desc='Moving files', ncols=70) as pbar:
            for file_path in self.files_to_move:
                try:
                    file_path.rename(self.trash_dir / file_path.name)
                    logging.info('Moved file to trash: %s', file_path)
                except OSError as e:
                    logging.error('Error moving file: %s', e)
                pbar.update()
        logging.info('Completed moving files to trash')

    def print_file(self, file_path):
        size_in_mb = file_path.stat().st_size / (1024 * 1024)
        if size_in_mb < 1024:
            print(f"Old, large file: {file_path} Size: {size_in_mb:.2f} MB")
            logging.info('Old, large file: %s Size: %.2f MB', file_path, size_in_mb)
        else:
            size_in_gb = size_in_mb / 1024
            print(f"Old, large file: {file_path} Size: {size_in_gb:.2f} GB")
            logging.info('Old, large file: %s Size: %.2f GB', file_path, size_in_gb)

def main():
    home = str(Path.home())

    parser = argparse.ArgumentParser(description="Find and remove large, old files.")
    parser.add_argument("--size", type=int, default=100, help="File size limit in MB")
    parser.add_argument("--days", type=int, default=365, help="File age limit in days")
    parser.add_argument("--dir", type=str, default=home, help="Directory to scan")
    parser.add_argument("--exclude", type=str, nargs='*', default=['.docx', '.xlsx'], help="File extensions to exclude")
    parser.add_argument("--trash", type=str, default=os.path.join(home, 'trash'), help="Directory to move files to")

    args = parser.parse_args()
    size_limit = args.size * 1024 * 1024  # Convert size from MB to bytes

    scanner = FileScanner(args.dir, size_limit, args.days, args.exclude, args.trash)
    with tqdm(total=scanner.count_files(), desc='Scanning files', ncols=70) as pbar:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(scanner.process_file, file_path, scanner.print_file, pbar) for file_path in scanner.scan_files()]
            concurrent.futures.wait(futures)
    print("Total size to be moved to trash: {:.2f} GB".format(scanner.total_size_in_gb()))
    input("Press enter to move these files to trash...")
    scanner.move_files_to_trash()

if __name__ == "__main__":
    main()
