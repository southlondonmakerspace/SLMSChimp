#!/usr/bin/env python3

import sys
import time
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(
        description='Run script and sleep for a specified number of hours.')

    parser.add_argument('-hrs', '--hours', type=int, default=12,
                        help='Number of hours to sleep between script runs')

    args = parser.parse_args()

    script = "slmschimp.py"
    arg1 = "-s"
    arg2 = "-a"

    command = ["python3", script, arg1, arg2]

    try:
        while True:
            subprocess.run(command)
            print(f"Sleeping for {args.hours} hours...")
            time.sleep(args.hours * 60 * 60)
    except KeyboardInterrupt:
        print("\n timer.py interrupted via Keyboard Interrupt. Exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
