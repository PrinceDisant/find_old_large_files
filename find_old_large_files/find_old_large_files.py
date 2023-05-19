import os
import time
import argparse
import logging
import concurrent.futures
from pathlib import Path
from tqdm import tqdm

class FileScanner:
    def __init__(self, dir_path, size_limit, days_limit, excluded_extensions, trash_dir):
        self.dir_path = dir_path
        self.size_limit = size_limit
        self.days_limit = days_limit
        self.excluded_extensions = excluded_extensions
        self.trash_dir = trash_dir
        self.files_to_move = []  # Store the files to be moved

        # Set up logging
        logging.basicConfig(filename=os.path.join(self.trash_dir, 'file_scanner.log'), 
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info('Initialized FileScanner with dir_path: %s, size_limit: %s, days_limit: %s, excluded_extensions: %s, trash_dir: %s',
                     dir_path, size_limit, days_limit, excluded_extensions, trash_dir)

    @staticmethod
    def file_age_in_days(file_path):
        return (time.time() - os.path.getmtime(file_path)) / (60*60*24)

    def count_files(self):
        count = 0
        for _, _, filenames in os.walk(self.dir_path):
            count += len(filenames)
        logging.info('Total files in dir_path: %s', count)
        return count

    def scan_files(self, file_handler=None):
        num_files = self.count_files()
        with tqdm(total=num_files, desc='Scanning files', ncols=70) as pbar:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = []
                for foldername, subfolders, filenames in os.walk(self.dir_path):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        futures.append(executor.submit(self.process_file, file_path, file_handler, pbar))
                concurrent.futures.wait(futures)

    def process_file(self, file_path, file_handler, pbar):
        try:
            if (os.path.getsize(file_path) > self.size_limit and
                self.file_age_in_days(file_path) > self.days_limit and
                not Path(file_path).suffix in self.excluded_extensions):
                self.files_to_move.append(file_path)  # Add to files to be moved
                logging.info('Added file to move: %s', file_path)
                if file_handler is not None:
                    file_handler(file_path)
        except FileNotFoundError:
            logging.error('File not found: %s', file_path)
        pbar.update()

    def move_files_to_trash(self):
        os.makedirs(self.trash_dir, exist_ok=True)
        with tqdm(total=len(self.files_to_move), desc='Moving files', ncols=70) as pbar:
            for file_path in self.files_to_move:
                try:
                    os.rename(file_path, os.path.join(self.trash_dir, os.path.basename(file_path)))
                    logging.info('Moved file to trash: %s', file_path)
                except Exception as e:
                    logging.error('Error moving file: %s', e)
                pbar.update()
        logging.info('Completed moving files to trash')

    def print_file(self, file_path):
        size_in_mb = os.path.getsize(file_path) / (1024 * 1024)
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
    scanner.scan_files(scanner.print_file)
    print("Total size to be moved to trash: {:.2f} GB".format(scanner.total_size_in_gb()))
    input("Press enter to move these files to trash...")
    scanner.move_files_to_trash()  # Move files to trash


if __name__ == "__main__":
    main()
