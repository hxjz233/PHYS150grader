"""
Utility functions for handling matplotlib and plotting in student code.
"""
import warnings

def configure_matplotlib_if_needed(cell_code: str, namespace: dict) -> None:
    """Configure matplotlib for non-interactive backend if plotting code is detected.
    
    Args:
        cell_code: The code to check for plotting-related imports/usage
        namespace: The namespace dictionary where the code will run
    """
    if 'plot' in cell_code or 'plt' in cell_code or 'matplotlib' in cell_code:
        setup_code = """
import os
import warnings
os.environ['MPLBACKEND'] = 'Agg'
# Suppress UserWarning about non-interactive backend
warnings.filterwarnings('ignore', category=UserWarning, message='.*non-interactive.*')
"""
        try:
            exec(setup_code, namespace)
        except Exception:
            pass  # Ignore any setup errors

def cleanup_matplotlib(namespace: dict) -> None:
    """Clean up matplotlib figures if they exist.
    
    Args:
        namespace: The namespace dictionary where the code ran
    """
    if 'plt' in namespace or 'matplotlib.pyplot' in namespace:
        cleanup_code = """
try:
    if 'plt' in globals():
        plt.close('all')
    elif 'matplotlib.pyplot' in globals():
        matplotlib.pyplot.close('all')
except Exception:
    pass  # Ignore cleanup errors
"""
        try:
            exec(cleanup_code, namespace)
        except Exception:
            pass  # Ignore cleanup errors