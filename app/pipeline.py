from app.modules.m1_intake.service import intake
from app.modules.m2_locate.service import locate
from app.modules.m3_zones.service import zones
from app.modules.m4_fit.service import fit
from app.modules.m5_changeovers.service import changeovers
from app.modules.m6_ledger.service import ledger
from app.modules.m7_slips.receipts import receipts


def plan_batch(sources, kerf, stop=None):
    result = {}
    imported = result["intake"] = intake(sources)
    if stop == "intake":
        return result
    located = result["locate"] = locate(imported)
    if stop == "locate":
        return result
    union = result["zones"] = zones(imported["rolls"]["accepted"], located)
    if stop == "zones":
        return result
    fit_result, options = fit(union["rolls"], imported["orders"]["accepted"], kerf)
    result["fit"] = fit_result
    if stop == "fit":
        return result
    planning = result["changeovers"] = changeovers(union["rolls"], fit_result, options)
    if stop == "changeovers":
        return result
    books = result["ledger"] = ledger(union["rolls"], fit_result, planning, imported, located)
    if stop == "ledger":
        return result
    result["slips"] = receipts(union["rolls"], planning, books)
    return result
