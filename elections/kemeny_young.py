from election import Election
from ballots.ranked import RankedBallot
from typing import Iterable
from ballot import Ballot
import itertools


class KemenyYoungElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Kemeny-Young"

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        if len(self.candidates) == 0:
            return [], "No candidates were found."
        elif len(self.candidates) > 6:
            return [], "Too many candidates for Kemeny-Young."

        lines = []

        pairwise_preference = {
            a: {b: 0 for b in self.candidates if b != a} for a in self.candidates
        }
        for ballot in ballots:
            for i, a in enumerate(ballot.ranking):
                for b in ballot.ranking[i + 1 :]:
                    pairwise_preference[a][b] += 1
                for c in self.candidates:
                    if c not in ballot.ranking:
                        pairwise_preference[a][c] += 1

        lines.append("Pairwise Preferences:")
        for a in self.candidates:
            for b in self.candidates:
                if a < b:
                    a_prefs = pairwise_preference[a][b]
                    b_prefs = pairwise_preference[b][a]
                    if a_prefs + b_prefs > 0:
                        lines.append(
                            f"- {a} vs {b}: {a_prefs} - {b_prefs} ({a_prefs / (a_prefs + b_prefs):2%} - {b_prefs / (a_prefs + b_prefs):2%})"
                        )
                    else:
                        lines.append(f"- {a} vs {b}: 0 - 0")

        best_score = -1
        best_permutation = []
        for permutation in itertools.permutations(self.candidates):
            score = 0
            for i, a in enumerate(permutation):
                for b in permutation[i + 1 :]:
                    score += pairwise_preference[a][b]
            if score > best_score:
                best_score = score
                best_permutation = [permutation]
            elif score == best_score:
                best_permutation.append(permutation)

        lines.append(f"**Best Kemeny Score**: {best_score}")
        if len(best_permutation) == 1:
            for c in best_permutation[0]:
                lines.append(f"- {c}")
        else:
            lines.append("Tie between:")
            for r in best_permutation:
                lines.append("- " + ", ".join(r))

        winners = list(set(r[0] for r in best_permutation))
        return winners, "\n".join(lines)
