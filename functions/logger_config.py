"""
This module sets up colorlog with appropriate formatters for development
and production environments. Provides colored, structured logging output
with context information for debugging.
"""

import logging
import sys
from typing import Optional

import colorlog


def _safe_console_stream():
    """Return stdout configured to tolerate Unicode log messages on Windows."""
    stream = sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (TypeError, ValueError, OSError):
            pass
    return stream


def setup_logger(
    name: str = "source-bruh",
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return a logger with colorlog formatting.
    
    Features:
    - Color-coded log levels (DEBUG=cyan, INFO=green, WARNING=yellow, ERROR=red, CRITICAL=red/bold)
    - Timestamp with milliseconds
    - Module name and line number
    - Function name
    - Clean, readable format
    
    Args:
        name: Logger name (default: "source-bruh")
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Falls back to environment variable LOG_LEVEL or INFO
        log_file: Optional file path to also log to a file
        
    Returns:
        Configured logger instance
        
    Example:
        >>> from logger_config import setup_logger
        >>> logger = setup_logger(__name__)
        >>> logger.info("Server started")
        >>> logger.error("Failed to connect", exc_info=True)
    """
    # Determine log level
    if level is None:
        import os
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    log_level = getattr(logging, level, logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Console handler with color
    console_handler = colorlog.StreamHandler(_safe_console_stream())
    console_handler.setLevel(log_level)
    
    # Color formatter
    console_format = (
        "%(log_color)s%(levelname)-8s%(reset)s "
        "%(cyan)s%(asctime)s%(reset)s "
        "%(blue)s[%(name)s:%(lineno)d]%(reset)s "
        "%(purple)s%(funcName)s%(reset)s "
        "%(white)s%(message)s%(reset)s"
    )
    
    color_formatter = colorlog.ColoredFormatter(
        console_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bold',
        },
        secondary_log_colors={},
        style='%'
    )
    
    console_handler.setFormatter(color_formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified) - no colors
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        
        file_format = (
            "%(levelname)-8s %(asctime)s [%(name)s:%(lineno)d] "
            "%(funcName)s - %(message)s"
        )
        file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the standard configuration.
    
    If the logger doesn't exist, it will be created with default settings.
    
    Args:
        name: Logger name (typically __name__ from calling module)
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


def log_function_call(logger: logging.Logger, func_name: str, **kwargs):
    """
    Log a function call with its parameters.
    
    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function parameters to log
        
    Example:
        >>> logger = get_logger(__name__)
        >>> log_function_call(logger, "search", query="test", top_k=10)
    """
    params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.debug(f"→ {func_name}({params})")


def log_exception(logger: logging.Logger, message: str, exc: Exception):
    """
    Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        message: Context message describing where the error occurred
        exc: The exception instance
        
    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_exception(logger, "Failed to process image", e)
    """
    logger.error(f"{message}: {exc.__class__.__name__}: {str(exc)}", exc_info=True)


def log_api_request(logger: logging.Logger, method: str, path: str, user_id: Optional[str] = None):
    """
    Log an incoming API request.
    
    Args:
        logger: Logger instance
        method: HTTP method (GET, POST, etc.)
        path: Request path
        user_id: Optional user ID for authenticated requests
    """
    user_info = f" [user:{user_id}]" if user_id else ""
    logger.info(f"⬅  {method} {path}{user_info}")


def log_api_response(logger: logging.Logger, method: str, path: str, status_code: int, duration_ms: float):
    """
    Log an API response.
    
    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
    """
    level = logging.INFO if status_code < 400 else logging.ERROR
    logger.log(level, f"➡  {method} {path} → {status_code} ({duration_ms:.2f}ms)")


# Initialize default logger
default_logger = setup_logger()
