from election import Election
from ballots.score import ScoreBallot


class ScoreElection(Election):
    def name(self) -> str:
        return "Score"

    def blank_ballot(self) -> ScoreBallot:
        return ScoreBallot(self)

    def tabulate(self) -> tuple[list[str], str]:
        if not self.submitted_ballots:
            return [], "No ballots were submitted."
        scores = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in scores:
                    scores[cand] += rating
        scores = {c: s / len(self.submitted_ballots) for c, s in scores.items()}
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if scores:
            max_score = max(scores.values())
            return [c for c, sc in scores.items() if sc == max_score], "\n".join(
                [f"**{c}:** {count}" for c, count in sorted_candidates]
            )
        else:
            return [], "No candidates were found."
