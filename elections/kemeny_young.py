from election import Election
from i18n import N_, _, ngettext
from ballots.ranked import RankedBallot
from typing import Iterable
from ballot import Ballot
import itertools
import random

MAX_CANDIDATES = 6


class KemenyYoungElection(Election):
    @classmethod
    def method_name(self) -> str:
        return N_("Kemeny-Young")

    @classmethod
    def validate_method_params(
        cls, params: dict[str, str], candidates: list[str]
    ) -> str | None:
        if len(candidates) > MAX_CANDIDATES:
            return ngettext(
                "Kemeny-Young supports at most {n} candidate.",
                "Kemeny-Young supports at most {n} candidates.",
                MAX_CANDIDATES,
            ).format(n=MAX_CANDIDATES)
        return None

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        if len(self.candidates) == 0:
            return [], _("No candidates were found.")
        elif len(self.candidates) > MAX_CANDIDATES:
            return [], _("Too many candidates for Kemeny-Young.")

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

        lines.append(_("Pairwise Preferences:"))
        for a in self.candidates:
            for b in self.candidates:
                if a < b:
                    a_prefs = pairwise_preference[a][b]
                    b_prefs = pairwise_preference[b][a]
                    if a_prefs + b_prefs > 0:
                        lines.append(
                            f"- {a} vs {b}: {a_prefs} - {b_prefs} ({a_prefs / (a_prefs + b_prefs):.2%} - {b_prefs / (a_prefs + b_prefs):.2%})"
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

        lines.append(_("**Best Kemeny Score**: {score}").format(score=best_score))
        if len(best_permutation) == 1:
            for c in best_permutation[0]:
                lines.append(f"- {c}")
        else:
            lines.append(_("Tie between:"))
            for r in best_permutation:
                lines.append("- " + ", ".join(r))

        winners = list(set(r[0] for r in best_permutation))
        return winners, "\n".join(lines)
