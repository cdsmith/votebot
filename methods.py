from elections.plurality import PluralityElection
from elections.approval import ApprovalElection
from elections.copeland import CopelandElection
from elections.score import ScoreElection
from elections.star import STARElection
from elections.irv import IRVElection
from elections.ranked_pairs import RankedPairsElection
from elections.rivestshen import RivestShenGTElection
from elections.tideman_alt import TidemanAlternativeElection
from elections.borda import BordaElection
from elections.kemeny_young import KemenyYoungElection
from elections.stv import STVElection

METHOD_CLASSES: list[type] = [
    ApprovalElection,
    BordaElection,
    CopelandElection,
    IRVElection,
    KemenyYoungElection,
    PluralityElection,
    RankedPairsElection,
    RivestShenGTElection,
    ScoreElection,
    STARElection,
    STVElection,
    TidemanAlternativeElection,
]

NAMED_METHODS: dict[str, type] = {cls.method_name(): cls for cls in METHOD_CLASSES}
