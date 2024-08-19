import subprocess
import sys
import time
import threading


def install_system_dependencies():
    # Install system packages
    subprocess.check_call("sudo yum -y update", shell=True)
    subprocess.check_call("sudo yum -y groupinstall 'Development Tools'", shell=True)
    subprocess.check_call("sudo yum -y install openssl-devel bzip2-devel libffi-devel postgresql-devel", shell=True)

def install_python():
    # Download and install Python 3.8.10
    subprocess.check_call("wget https://www.python.org/ftp/python/3.8.10/Python-3.8.10.tgz", shell=True)
    subprocess.check_call("tar xvf Python-3.8.10.tgz", shell=True)
    subprocess.check_call("cd Python-3.8.10 && ./configure --enable-optimizations && sudo make altinstall", shell=True)

def install_lirec():
    # Install LIReC from GitHub
    subprocess.check_call([sys.executable, "-m", "pip", "install", "git+https://github.com/RamanujanMachine/LIReC.git"])

def print_status():
    while True:
        print("LIReC is running...")
        time.sleep(30)  # Sleep for 30 seconds

def run_lirec():
    # Assuming LIReC has an entry point in its package
    # Run LIReC (same as from run_jobs.py)
    from LIReC.jobs import run
    print("Running run.main()")
    run.main()

def main():
    # install_system_dependencies()
    #install_python()
    # print_status()
    # install_lirec()
    # run_lirec()

    # Start the print_status function in a background thread
    # status_thread = threading.Thread(target=print_status, daemon=True)
    # status_thread.start()

    # The rest of the functions can now execute without being blocked by print_status
    # install_python()
    # install_lirec()
    run_lirec()

if __name__ == "__main__":
    main()
