from election import Election
from i18n import N_, _
from ballots.ranked import RankedBallot
from ballot import Ballot
from typing import Iterable
import random


class RankedPairsElection(Election):
    @classmethod
    def method_name(self) -> str:
        return N_("Ranked Pairs")

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        pairwise = {
            (a, b): 0 for a in self.candidates for b in self.candidates if a != b
        }
        for ballot in ballots:
            for i, a in enumerate(ballot.ranking):
                for b in ballot.ranking[i + 1 :]:
                    pairwise[(a, b)] += 1
                unranked = set(self.candidates) - set(ballot.ranking)
                for b in unranked:
                    pairwise[(a, b)] += 1

        lines = []
        lines.append(_("**Pairwise Matchups:**"))

        margins = {}
        for a, b in pairwise.keys():
            a_wins = pairwise[(a, b)]
            b_wins = pairwise[(b, a)]
            if a_wins > b_wins:
                if a < b:
                    lines.append(
                        _("- {winner} defeats {loser}: {wins}-{losses}").format(
                            winner=a, loser=b, wins=a_wins, losses=b_wins
                        )
                    )
                margins[(a, b)] = a_wins - b_wins
            elif b_wins > a_wins:
                if a < b:
                    lines.append(
                        _("- {winner} defeats {loser}: {wins}-{losses}").format(
                            winner=b, loser=a, wins=b_wins, losses=a_wins
                        )
                    )
                margins[(b, a)] = b_wins - a_wins
            else:
                if a < b:
                    lines.append(
                        _("- {a} and {b} tie: {a_votes}-{b_votes}").format(
                            a=a, b=b, a_votes=a_wins, b_votes=b_wins
                        )
                    )

        lines.append("")
        lines.append(_("**Locked rankings:**"))

        locked_pairs = []

        def reachable(x, y):
            visited = set()
            stack = [x]
            while stack:
                node = stack.pop()
                if node == y:
                    return True
                visited.add(node)
                stack.extend(
                    [
                        dest
                        for src, dest in locked_pairs
                        if src == node and dest not in visited
                    ]
                )

        for a, b in sorted(margins, key=margins.get, reverse=True):
            if not reachable(b, a):
                lines.append(f"- {a} > {b}")
                locked_pairs.append((a, b))
            else:
                lines.append(
                    _(
                        "- Ignoring {a} > {b} because it contradicts stronger "
                        "preferences"
                    ).format(a=a, b=b)
                )

        beat_counts = {c: 0 for c in self.candidates}
        for winner, loser in locked_pairs:
            beat_counts[loser] += 1

        lines.append("")
        lines.append(_("**Final ordering:**"))

        last_score = None
        rank = 0
        winners = []
        for i, (c, score) in enumerate(sorted(beat_counts.items(), key=lambda x: x[1])):
            if score != last_score:
                rank = i + 1
            lines.append(f"{rank}. {c}")
            if rank == 1:
                winners.append(c)

        return winners, "\n".join(lines)
