from enum import StrEnum


class BacktestHorizon(StrEnum):
    ONE_DAY = "1d"
    FIVE_DAYS = "5d"
    TWENTY_DAYS = "20d"

    @property
    def days(self) -> int:
        values = {
            BacktestHorizon.ONE_DAY: 1,
            BacktestHorizon.FIVE_DAYS: 5,
            BacktestHorizon.TWENTY_DAYS: 20,
        }
        return values[self]
