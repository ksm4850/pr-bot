from models.job import ErrorSource
from services.parsers.base import ErrorParser
from services.parsers.sentry import SentryParser

# 파서 레지스트리
_PARSERS: dict[ErrorSource, ErrorParser] = {
    ErrorSource.SENTRY: SentryParser(),
}


def get_parser(source: ErrorSource) -> ErrorParser:
    """소스별 파서 반환"""
    parser = _PARSERS.get(source)
    if not parser:
        raise ValueError(f"Unknown error source: {source}")
    return parser
