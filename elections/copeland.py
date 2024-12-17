from election import Election
from ballots.ranked import RankedBallot


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

    def tabulate(self) -> tuple[list[str], str]:
        if not self.candidates:
            return [], "No candidates were found."

        lines = []
        lines.append("**Pairwise Matchups:**")

        candidate_stats = {
            c: {"wins": 0, "losses": 0, "ties": 0} for c in self.candidates
        }
        for i in range(len(self.candidates)):
            for j in range(i + 1, len(self.candidates)):
                a = self.candidates[i]
                b = self.candidates[j]
                a_prefs = 0
                b_prefs = 0
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
                        a_prefs += 1
                    elif b_pos < a_pos:
                        b_prefs += 1

                if a_prefs > b_prefs:
                    result = f"{a} defeats {b}"
                    candidate_stats[a]["wins"] += 1
                    candidate_stats[b]["losses"] += 1
                elif b_prefs > a_prefs:
                    result = f"{b} defeats {a}"
                    candidate_stats[a]["losses"] += 1
                    candidate_stats[b]["wins"] += 1
                else:
                    result = f"{a} and {b} tie"
                    candidate_stats[a]["ties"] += 1
                    candidate_stats[b]["ties"] += 1

                lines.append(
                    f"- {a} vs {b}: {a_prefs} - {b_prefs} ({a_prefs / (a_prefs + b_prefs):.2%} - {b_prefs / (a_prefs + b_prefs):.2%}). {result}"
                )

        scores = {
            c: candidate_stats[c]["wins"] + 0.5 * candidate_stats[c]["ties"]
            for c in self.candidates
        }
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        lines.append("")
        lines.append("**Scores (number of head-to-head wins):**")
        for c, sc in sorted_scores:
            w = candidate_stats[c]["wins"]
            l = candidate_stats[c]["losses"]
            t = candidate_stats[c]["ties"]
            lines.append(f"- {c}: {w} wins, {l} losses, {t} ties = {sc}")

        winners = [c for c, sc in sorted_scores if sc == sorted_scores[0][1]]
        return winners, "\n".join(lines)
