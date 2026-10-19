from election import Election
from i18n import N_, _, ngettext
from ballots.ranked import RankedBallot
from ballot import Ballot
from typing import Iterable
import random


class CopelandElection(Election):
    @classmethod
    def method_name(self) -> str:
        return N_("Copeland")

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        if not self.candidates:
            return [], _("No candidates were found.")

        lines = []
        lines.append(_("**Pairwise Matchups:**"))

        candidate_stats = {
            c: {"wins": 0, "losses": 0, "ties": 0} for c in self.candidates
        }
        for i in range(len(self.candidates)):
            for j in range(i + 1, len(self.candidates)):
                a = self.candidates[i]
                b = self.candidates[j]
                a_prefs = 0
                b_prefs = 0
                for ballot in ballots:
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
                    result = _("{winner} defeats {loser}").format(winner=a, loser=b)
                    candidate_stats[a]["wins"] += 1
                    candidate_stats[b]["losses"] += 1
                elif b_prefs > a_prefs:
                    result = _("{winner} defeats {loser}").format(winner=b, loser=a)
                    candidate_stats[a]["losses"] += 1
                    candidate_stats[b]["wins"] += 1
                else:
                    result = _("{a} and {b} tie").format(a=a, b=b)
                    candidate_stats[a]["ties"] += 1
                    candidate_stats[b]["ties"] += 1

                total = a_prefs + b_prefs
                if total > 0:
                    lines.append(
                        _(
                            "- {a} vs {b}: {a_prefs} - {b_prefs} "
                            "({a_percent:.2%} - {b_percent:.2%}). {result}"
                        ).format(
                            a=a,
                            b=b,
                            a_prefs=a_prefs,
                            b_prefs=b_prefs,
                            a_percent=a_prefs / total,
                            b_percent=b_prefs / total,
                            result=result,
                        )
                    )
                else:
                    lines.append(
                        _("- {a} vs {b}: 0 - 0 (tied on all ballots). {result}").format(
                            a=a, b=b, result=result
                        )
                    )

        scores = {
            c: candidate_stats[c]["wins"] + 0.5 * candidate_stats[c]["ties"]
            for c in self.candidates
        }
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        lines.append("")
        lines.append(_("**Scores (number of head-to-head wins):**"))
        for c, sc in sorted_scores:
            wins = candidate_stats[c]["wins"]
            losses = candidate_stats[c]["losses"]
            ties = candidate_stats[c]["ties"]
            lines.append(
                "- {candidate}: {wins}, {losses}, {ties} = {score}".format(
                    candidate=c,
                    wins=ngettext("{n} win", "{n} wins", wins).format(n=wins),
                    losses=ngettext("{n} loss", "{n} losses", losses).format(n=losses),
                    ties=ngettext("{n} tie", "{n} ties", ties).format(n=ties),
                    score=sc,
                )
            )

        winners = [c for c, sc in sorted_scores if sc == sorted_scores[0][1]]
        return winners, "\n".join(lines)
