"""
DTI Entry Point — Run with: python -m dti

This is the terminal you use to talk to a god.
"""

import sys
import os
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .neural_terminal import NeuralTerminal


def main():
    logging.info("DTI Entry Point started")
    terminal = NeuralTerminal()
    
    if len(sys.argv) > 1:
        logging.info("Running in command-line mode (non-interactive)")
        command = sys.argv[1]
        args = sys.argv[2:]
        try:
            terminal.execute_command(command, args)
        except Exception as e:
            logging.error(f"Error executing command: {e}")
    else:
        logging.info("Running in interactive neural terminal mode")
        try:
            terminal.run_interactive()
        except Exception as e:
            logging.error(f"Error running interactive terminal: {e}")


if __name__ == "__main__":
    main()
    logging.info("DTI Entry Point finished")
