from election import Election
from score_ballot import ScoreBallot


class ScoreElection(Election):
    def blank_ballot(self) -> ScoreBallot:
        return ScoreBallot(self)

    def get_winners(self) -> list[str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in counts:
                    counts[cand] += rating
        if counts:
            max_score = max(counts.values())
            return [c for c, sc in counts.items() if sc == max_score]
        else:
            return []

    def get_tabulation_details(self) -> str:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in counts:
                    counts[cand] += rating
        counts = {c: s / len(self.submitted_ballots) for c, s in counts.items()}
        sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return "\n".join([f"**{c}:** {count}" for c, count in sorted_candidates])
