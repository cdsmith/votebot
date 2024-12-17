from election import Election
from ranked_ballot import RankedBallot


class CopelandElection(Election):
    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def get_winners(self) -> list[str]:
        scores, _ = self.compute_copeland_scores()
        if scores:
            max_score = max(scores.values())
            return [c for c, sc in scores.items() if sc == max_score]
        else:
            return []

    def compute_copeland_scores(self):
        scores = {c: 0 for c in self.candidates}
        pair_results = {}
        sorted_candidates = sorted(self.candidates)
        for i in range(len(sorted_candidates)):
            for j in range(i + 1, len(sorted_candidates)):
                a = sorted_candidates[i]
                b = sorted_candidates[j]
                a_wins = 0
                b_wins = 0
                for ballot in self.submitted_ballots.values():
                    a_pos = (
                        ballot.ranking.index(a)
                        if a in ballot.ranking
                        else len(ballot.ranking)
                    )
                    b_pos = (
                        ballot.ranking.index(b)
                        if b in ballot.ranking
                        else len(ballot.ranking)
                    )
                    if a_pos < b_pos:
                        a_wins += 1
                    elif b_pos < a_pos:
                        b_wins += 1

                if a_wins > b_wins:
                    scores[a] += 1
                elif b_wins > a_wins:
                    scores[b] += 1
                else:
                    scores[a] += 0.5
                    scores[b] += 0.5

                pair_results[(a, b)] = (a_wins, b_wins)
        return scores, pair_results

    def get_tabulation_details(self) -> str:
        scores, pair_results = self.compute_copeland_scores()

        candidate_stats = {
            c: {"wins": 0, "losses": 0, "ties": 0} for c in self.candidates
        }

        lines = []
        lines.append("**Pairwise Matchups:**")
        for (a, b), (a_wins, b_wins) in sorted(pair_results.items()):
            if a_wins > b_wins:
                result = f"{a} defeats {b}"
                candidate_stats[a]["wins"] += 1
                candidate_stats[b]["losses"] += 1
            elif b_wins > a_wins:
                result = f"{b} defeats {a}"
                candidate_stats[b]["wins"] += 1
                candidate_stats[a]["losses"] += 1
            else:
                result = f"{a} ties {b}"
                candidate_stats[a]["ties"] += 1
                candidate_stats[b]["ties"] += 1

            lines.append(
                f"- {a} vs {b}: {a_wins} ({a_wins / (a_wins + b_wins):.2%}) - {b_wins} ({b_wins / (a_wins + b_wins):.2%}). {result}"
            )

        lines.append("")
        lines.append("**Scores (number of head-to-head wins):**")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for c, sc in sorted_scores:
            w = candidate_stats[c]["wins"]
            l = candidate_stats[c]["losses"]
            t = candidate_stats[c]["ties"]
            lines.append(f"- {c}: {w} wins, {l} losses, {t} ties = {sc}")

        return "\n".join(lines)
