from election import Election
from ballots.simple import SimpleBallot
from ballot import Ballot
from typing import Iterable
import random


class PluralityElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Plurality"

    def blank_ballot(self) -> SimpleBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return SimpleBallot(self.election_id, candidates, multiple_votes=False)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in ballots:
            for candidate in ballot.votes:
                if candidate in counts:
                    counts[candidate] += 1
        sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if counts:
            max_score = max(counts.values())
            return [c for c, sc in counts.items() if sc == max_score], "\n".join(
                [f"**{c}:** {count}" for c, count in sorted_candidates]
            )
        else:
            return [], "No candidates were found."
