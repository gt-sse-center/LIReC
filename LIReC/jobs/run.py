'''
'''
import json
import signal
#import numpy as np
import os
import sys
from LIReC.jobs.config import configuration
from LIReC.lib.pool import WorkerPool
import logging


MOD_PATH = 'LIReC.jobs.job_%s'

def validate_config(config):
    if not isinstance(config, dict):
        return False, "Configuration should be a dictionary."
    
    if 'jobs_to_run' not in config:
        return False, "Missing 'jobs_to_run' key in configuration."

    if not isinstance(config['jobs_to_run'], list):
        return False, "'jobs_to_run' should be a list."

    for job in config['jobs_to_run']:
        if not isinstance(job, tuple) or len(job) != 2:
            return False, "'jobs_to_run' should contain tuples of (job_name, job_info)."

        job_name, job_info = job
        if not isinstance(job_name, str):
            return False, "Job name should be a string."

        if not isinstance(job_info, dict):
            return False, "Job info should be a dictionary."

        required_keys = {'args', 'run_async', 'async_cores'}
        if not all(key in job_info for key in required_keys):
            return False, "Missing required keys in job info."

        args = job_info['args']
        if not isinstance(args, dict):
            return False, "'args' should be a dictionary."

        expected_args_keys = {'degree', 'order', 'bulk', 'filters'}
        if not all(key in args for key in expected_args_keys):
            return False, "Missing required keys in args."

        filters = args['filters']
        if not isinstance(filters, dict):
            return False, "'filters' should be a dictionary."

        # Further checks can be added for filters' inner structure if necessary

    return True, "Configuration is valid."


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

        # Define a flush method that flushes the outputs
    # class FlushHandler(logging.Handler):
    #     def emit(self, record):
    #         logging.StreamHandler.emit(self, record)
    #         self.flush()

    # file_handler = FlushHandler()
    # stream_handler = FlushHandler()
    
    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def main() -> None:
    os.makedirs(os.path.join(os.getcwd(), 'logs'), exist_ok=True)
    logger = setup_logging()  # Set up logging configuration

    logger.error("sys.argv: %s", sys.argv)
    config_data = configuration
    if len(sys.argv) >= 2:
        job_config_filename = sys.argv[1]
        logger.error("job_config_filename: %s", job_config_filename)
        try:
            with open(job_config_filename, 'r') as file:
                job_config = json.load(file)
                logger.info("Loaded job configuration: %s", json.dumps(job_config, indent=4))
                valid, message = validate_config(job_config)
                logger.info("validate_config job configuration: %s", message)
                if valid:
                    config_data = job_config
        except FileNotFoundError:
            logger.error("File not found: %s", job_config_filename)
        except json.JSONDecodeError:
            logger.error("Error decoding JSON from the file: %s", job_config_filename)
        except Exception as e:
            logger.error("Error reading file %s: %s", job_config_filename, e)




    # Read from stdin if any data is present
    stdin_data = sys.stdin.readline().strip()
    if stdin_data:
        logger.info(f"Received via stdin: {stdin_data}")

    # Log to both file and stderr
    logger.info("logger.info Running run.main()")
    logger.error("logger.error This is an error message with details.")

    sys.stderr.write('Starting instance of WorkerPool...')
    worker_pool = WorkerPool()
    logger.info('worker_pool.start([(MOD_PATH % name, config) for name, config in configuration["jobs_to_run"]]):')
    logger.info([(MOD_PATH % name, config) for name, config in config_data['jobs_to_run']])


    results = worker_pool.start([(MOD_PATH % name, config) for name, config in config_data['jobs_to_run']])

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
