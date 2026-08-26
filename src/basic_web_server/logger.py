import logging


def create_logger(log_name, log_level):
    logger = logging.getLogger(log_name)

    # Avoid adding duplicate handlers when multiple Server objects are created.
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(threadName)s | "
        "%(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler("basic_web_server.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger