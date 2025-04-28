import json
from warnings import catch_warnings
from functools import wraps, partial
from decimal import Decimal
from typing import Any
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_masking import DataMasking
from aws_lambda_powertools.utilities.data_masking.provider import BaseProvider


def mockup_logger():
    class logger(object):
        pass

    logger.info = logger.warning = logger.error = logger.exception = logger.debug = (
        logger.critical
    ) = lambda d: print(d)
    return logger


def ensure_logger(logger=None):
    if logger is None:
        return mockup_logger()
    return logger


def decimal_serializer(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        obj = str(obj)
    return obj


def is_valid_json_string(json_string: str) -> bool:
    """Check if a string is a valid JSON object"""
    if isinstance(json_string, str):
        try:
            result = json.loads(json_string)
            return isinstance(result, dict)
        except json.JSONDecodeError:
            return False


# Create a decorator that will be used to decorate all the logging methods of the Logger class from aws_lambda_powertools
# The decorator takes the log message and removes the fields that are specified in the masked_fields parameter
def log_masking_decorator(masked_fields: list[str]):
    def decorator(func):
        @wraps(func)
        def wrapper(self, msg, *args, **kwargs):
            # We can only mask the fields if the message is a dictionary or a string containing a JSON object
            if is_valid_json_string(msg) or isinstance(msg, dict):
                # DataMasker erase method, raises a lot of warning messages when it is set to not raise an exception
                # On missing fields. But we don't want to see these warnings either, so we ignore them
                with catch_warnings(action="ignore"):
                    msg = self.data_masker.erase(msg, fields=masked_fields)
            return func(self, msg, *args, **kwargs)

        return wrapper

    return decorator


# Create a function that applies the log_masking_decorator to all the logging methods of the Logger class from aws_lambda_powertools
def decorate_log_methods(decorator):
    def decorate(cls):
        for attr in dir(cls):
            if callable(getattr(cls, attr)) and attr in [
                "info",
                "error",
                "warning",
                "exception",
                "debug",
                "critical",
            ]:
                setattr(cls, attr, decorator(getattr(cls, attr)))
        return cls

    return decorate


# Create a Custom Logger class that inherits from the Logger class from aws_lambda_powertools
# The Custom Logger class will have the log_masking_decorator applied to all the logging methods
@decorate_log_methods(
    log_masking_decorator(
        masked_fields=[
            "$.[*].phoneNumber",
            "$..[*].phoneNumber",
            "$.[*].name",
            "$..[*].name",
        ]
    )
)
class CustomLogger(Logger):
    def __init__(self):
        super().__init__()
        self.datamasking_provider = BaseProvider(
            json_serializer=partial(json.dumps, default=decimal_serializer),
            json_deserializer=json.loads,
        )
        self.data_masker = DataMasking(
            provider=self.datamasking_provider, raise_on_missing_field=False
        )
