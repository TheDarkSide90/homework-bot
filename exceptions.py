"""Файл с ошибками."""


class WrongAPIResponseError(Exception):
    """Ошибка другого ответа от API."""


class APIResponseError(Exception):
    """Ошибка запроса API."""
