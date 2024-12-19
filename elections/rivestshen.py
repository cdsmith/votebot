from election import Election
from ballots.ranked import RankedBallot
import numpy as np
from scipy.optimize import minimize, LinearConstraint
import random
from ballot import Ballot
from typing import Iterable


class RivestShenGTElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Rivest-Shen GT"

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        if not self.candidates:
            return [], "No candidates were found."

        m = len(self.candidates)
        M = [[0] * m for _ in range(m)]

        for i in range(m):
            for j in range(m):
                if i == j:
                    M[i][j] = 0
                else:
                    i_pref_j = 0
                    j_pref_i = 0
                    for ballot in ballots:
                        ranking = ballot.ranking
                        try:
                            i_pos = ranking.index(self.candidates[i])
                        except ValueError:
                            i_pos = len(ranking)
                        try:
                            j_pos = ranking.index(self.candidates[j])
                        except ValueError:
                            j_pos = len(ranking)

                        if i_pos < j_pos:
                            i_pref_j += 1
                        elif j_pos < i_pos:
                            j_pref_i += 1
                    M[i][j] = i_pref_j - j_pref_i

        w = 1 - min(min(row) for row in M)
        M_prime = np.array(M, dtype=float) + w
        sum_p = 1.0 / w

        A = M_prime.T
        b = np.ones(m)

        def objective(p):
            return np.sum(p ** 2)

        def grad_objective(p):
            return 2 * p

        A_eq_sum = np.ones((1, m))
        b_eq_sum = np.array([sum_p])
        eq_constraint = LinearConstraint(A_eq_sum, b_eq_sum, b_eq_sum)

        ineq_constraint = LinearConstraint(A, b, np.full(m, np.inf))
        bounds = [(0, None)] * m

        qp_res = minimize(
            objective,
            x0=np.full(m, sum_p / m),
            jac=grad_objective,
            constraints=[eq_constraint, ineq_constraint],
            bounds=bounds,
            method="trust-constr",
            options={"verbose": 0},
        )

        if not qp_res.success:
            return [], "No optimal solution found for the Rivest-Shen GT equilibrium."

        p = qp_res.x
        p_star = p * w

        total = sum(p_star)
        if total > 0:
            p_dist = [x / total for x in p_star]

        winner = random.choices(self.candidates, weights=p_dist, k=1)[0]

        lines = []
        lines.append("**Margin Matrix M:**")
        lines.append("```")
        for i, c1 in enumerate(self.candidates):
            row_str = []
            for j, c2 in enumerate(self.candidates):
                row_str.append(f"{M[i][j]:+d}")
            lines.append(f"{c1}: " + " ".join(row_str))
        lines.append("```")

        lines.append("")
        lines.append("**GTO equilibrium win probabilities:**")
        for c, val in zip(self.candidates, p_dist):
            lines.append(f"{c}: {val:.2%}")

        lines.append("")
        lines.append(f"**Winner:** {winner}")

        return [winner], "\n".join(lines)
