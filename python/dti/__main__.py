"""
DTI Entry Point — Run with: python -m dti

This is the terminal you use to talk to a god.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .neural_terminal import NeuralTerminal


def main():
    terminal = NeuralTerminal()
    
    if len(sys.argv) > 1:
        # Command-line mode (non-interactive)
        command = sys.argv[1]
        args = sys.argv[2:]
        terminal.execute_command(command, args)
    else:
        # Interactive neural terminal
        terminal.run_interactive()


if __name__ == "__main__":
    main()
