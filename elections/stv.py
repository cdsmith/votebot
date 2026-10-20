import random
from fractions import Fraction
from typing import Iterable
from election import Election
from i18n import N_, _, ngettext
from ballots.ranked import RankedBallot
from ballot import Ballot

NUMBER_OF_WINNERS = N_("Number of Winners")


def _votes(x: Fraction) -> str:
    """Format a possibly fractional vote count, e.g. 123 or 12.33."""
    return f"{float(x):.2f}".rstrip("0").rstrip(".")


class STVElection(Election):
    @classmethod
    def method_name(cls) -> str:
        return N_("Single Transferable Vote / Instant Runoff")

    @classmethod
    def method_description(cls, method_params: dict[str, str]) -> str:
        if method_params[NUMBER_OF_WINNERS] == "1":
            return _("Instant Runoff")
        else:
            seats = method_params[NUMBER_OF_WINNERS]
            # The count may not be a valid number yet during setup.
            return ngettext(
                "Single Transferable Vote for {seats} seat",
                "Single Transferable Vote for {seats} seats",
                int(seats) if seats.isdigit() else 2,
            ).format(seats=seats)

    @classmethod
    def method_param_names(cls) -> list[str]:
        return [NUMBER_OF_WINNERS]

    @classmethod
    def default_method_params(self):
        return {NUMBER_OF_WINNERS: "1"}

    @classmethod
    def method_param_choices(
        cls, param: str, candidates: list[str]
    ) -> list[str] | None:
        return [str(n) for n in range(1, max(len(candidates), 1) + 1)]

    @classmethod
    def validate_method_params(
        cls, params: dict[str, str], candidates: list[str]
    ) -> str | None:
        winners_str = params.get(NUMBER_OF_WINNERS, "1")
        try:
            n = int(winners_str)
            if n < 1:
                return _("Must choose at least one winner.")
            if n > len(candidates):
                return _("Number of winners cannot be more than the number of candidates.")
        except ValueError:
            return _("Number of winners must be an integer.")
        return None

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        desired_winners = int(self.method_params[NUMBER_OF_WINNERS])
        active_candidates = set(self.candidates)
        elected_candidates: list[str] = []
        lines: list[str] = []

        aggregated_ballots: dict[tuple[str, ...], Fraction] = {}
        for ballot in ballots:
            ranking_tuple = tuple(ballot.ranking)
            aggregated_ballots[ranking_tuple] = aggregated_ballots.get(
                ranking_tuple, 0
            ) + Fraction(1)

        round_num = 1
        exhausted = Fraction(0)

        while True:
            lines.append(_("**Round {round}:**").format(round=round_num))
            lines.append(
                _("Active candidates: {candidates}").format(
                    candidates=", ".join(sorted(active_candidates))
                )
            )

            counts = {c: 0 for c in active_candidates}
            total_active = Fraction(0)
            for ranking, weight in aggregated_ballots.items():
                counts[ranking[0]] = counts.get(ranking[0], 0) + weight
                total_active += weight

            quota = total_active / Fraction(
                desired_winners - len(elected_candidates) + 1
            )

            lines.append(
                _("Active ballots: {active}, exhausted: {exhausted}").format(
                    active=_votes(total_active), exhausted=_votes(exhausted)
                )
            )

            sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            if total_active > 0:
                lines.append(_("Current first-preference counts:"))
                for c, v in sorted_candidates:
                    lines.append(
                        f" - {c}: {_votes(v)} ({float(v / total_active):.2%})"
                    )

            max_count = sorted_candidates[0][1]
            min_count = sorted_candidates[-1][1]

            if max_count > quota:
                winners = [c for c, v in sorted_candidates if v == max_count]
                winner = random.choice(winners)
                if len(winners) > 1:
                    lines.append(
                        _(
                            "Multiple winners with equal votes. Randomly selected "
                            "**{candidate}**."
                        ).format(candidate=winner)
                    )
                lines.append(
                    _(
                        "Candidate **{candidate}** exceeded {percent:.2%} "
                        "({votes} votes) and is elected."
                    ).format(
                        candidate=winner,
                        percent=float(quota / total_active),
                        votes=_votes(quota),
                    )
                )
                elected_candidates.append(winner)

                elim = winner
                quota_fraction = quota / max_count
            else:
                losers = [c for c, v in sorted_candidates if v == min_count]
                loser = random.choice(losers)
                if len(losers) > 1:
                    lines.append(
                        _(
                            "Multiple candidates tied for last place. Randomly "
                            "selected **{candidate}** to eliminate."
                        ).format(candidate=loser)
                    )
                lines.append(
                    _("Candidate **{candidate}** is eliminated.").format(candidate=loser)
                )
                elim = loser
                quota_fraction = 0

            active_candidates.remove(elim)

            if len(active_candidates) <= desired_winners - len(elected_candidates):
                for candidate in active_candidates:
                    lines.append(
                        _("Candidate **{candidate}** is elected.").format(
                            candidate=candidate
                        )
                    )
                elected_candidates.extend(active_candidates)
                active_candidates.clear()
                break

            if len(elected_candidates) >= desired_winners:
                break

            if quota_fraction > 0:
                lines.append(
                    _(
                        "Redistributing surplus of {votes} votes from {candidate}."
                    ).format(votes=_votes(max_count - quota), candidate=elim)
                )

            new_aggregated: dict[tuple[str, ...], float] = {}
            for ranking, weight in aggregated_ballots.items():
                if ranking[0] == elim:
                    weight *= 1 - quota_fraction
                new_ranking = tuple(c for c in ranking if c != elim)
                if new_ranking:
                    new_aggregated[new_ranking] = (
                        new_aggregated.get(new_ranking, 0) + weight
                    )
                else:
                    exhausted += weight

            aggregated_ballots = new_aggregated

            round_num += 1

        return list(elected_candidates), "\n".join(lines)
