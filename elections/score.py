from election import Election
from ballots.score import ScoreBallot
from ballot import Ballot
from typing import Iterable
import random


class ScoreElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Score"

    def blank_ballot(self) -> ScoreBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return ScoreBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        ballots = list(ballots)
        if not ballots:
            return [], "No ballots were submitted."
        scores = {c: 0 for c in self.candidates}
        for ballot in ballots:
            for cand, rating in ballot.ratings.items():
                if cand in scores:
                    scores[cand] += rating
        scores = {c: s / len(ballots) for c, s in scores.items()}
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if scores:
            max_score = max(scores.values())
            return [c for c, sc in scores.items() if sc == max_score], "\n".join(
                [f"**{c}:** {count}" for c, count in sorted_candidates]
            )
        else:
            return [], "No candidates were found."
