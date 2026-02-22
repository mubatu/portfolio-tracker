from dataclasses import dataclass


@dataclass(frozen=True)
class MarketConfig:
    code: str
    currency: str
    country: str
    yfinance_suffix: str
    benchmark_candidates: tuple[str, ...]


# Central backend market registry.
# Add new markets here (e.g. NYSE/NASDAQ) with benchmark candidates
# that represent exchange open days on yfinance.
MARKETS: dict[str, MarketConfig] = {
    "BIST": MarketConfig(
        code="BIST",
        currency="TRY",
        country="TR",
        yfinance_suffix=".IS",
        benchmark_candidates=("XU100.IS", "^XU100"),
    ),
}


def get_market_config(market_code: str | None) -> MarketConfig | None:
    if not market_code:
        return None
    return MARKETS.get(market_code.upper())


def get_market_benchmark_candidates(market_code: str | None) -> tuple[str, ...]:
    config = get_market_config(market_code)
    if config is None:
        return ()
    return config.benchmark_candidates
