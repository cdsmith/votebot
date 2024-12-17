import abc
from typing import Any, Dict


class Ballot(abc.ABC):
    @abc.abstractmethod
    def copy(self) -> "Ballot":
        """Return a copy of the ballot.  Mutable fields should be copied."""
        pass

    @abc.abstractmethod
    def render_interim(self, session_id: int) -> Dict[str, Any]:
        """Return a dictionary representation of the ballot as Discord message fields."""
        pass

    @abc.abstractmethod
    def render_submitted(self) -> Dict[str, Any]:
        """Return a dictionary representation of the ballot as Discord message fields."""
        pass
