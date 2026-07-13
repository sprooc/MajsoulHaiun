from app.sources.majsoul.locator import MajsoulLocator


class ReplayFetchUnavailable(Exception):
    pass


class MajsoulReplayFetcher:
    async def fetch(self, locator: MajsoulLocator) -> bytes:
        raise ReplayFetchUnavailable("No anonymous raw-replay resolver is available for this record.")
