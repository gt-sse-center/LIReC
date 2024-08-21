'''
'''
import signal
#import numpy as np
import os
import sys
from LIReC.jobs.config import configuration
from LIReC.lib.pool import WorkerPool
import logging


MOD_PATH = 'LIReC.jobs.job_%s'


def setup_logging():
    # Create a logger object
    logger = logging.getLogger('LIReC')
    logger.setLevel(logging.DEBUG)  # Set the logging level to debug to capture all messages

    # Create handlers for writing to file and stderr
    file_handler = logging.FileHandler('stderr.txt')
    stream_handler = logging.StreamHandler()

    # Set the level and format for both handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def main() -> None:
    os.makedirs(os.path.join(os.getcwd(), 'logs'), exist_ok=True)
    logger = setup_logging()  # Set up logging configuration

    # Log to both file and stderr
    logger.info("logger.info Running run.main()")
    logger.error("logger.error This is an error message with details.")

    sys.stderr.write('Starting instance of WorkerPool...')
    worker_pool = WorkerPool()
    sys.stderr.write('worker_pool.start([(MOD_PATH % name, config) for name, config in configuration["jobs_to_run"]]):')
    sys.stderr.write([(MOD_PATH % name, config) for name, config in configuration['jobs_to_run']])
    results = worker_pool.start([(MOD_PATH % name, config) for name, config in configuration['jobs_to_run']])

    for module_path, timings in results:
        print('-------------------------------------')
        if timings:
            print(f'module {module_path} running times:')
            print(f'min time: {min(timings)}')
            print(f'max time: {max(timings)}')
            #print(f'median time: {np.median(timings)}')
            #print(f'average time: {np.average(timings)}')
        else:
            print(f"module {module_path} didn't run! check logs")
        print('-------------------------------------')

if __name__ == '__main__':
    main()
