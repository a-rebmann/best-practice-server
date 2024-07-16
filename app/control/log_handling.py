from pandas import DataFrame
from semconstmining.config import Config
import numpy as np
from uuid import uuid4

from app.model.variant import Variant


def get_variants(log, event_log: DataFrame, config: Config):
    cases = event_log[config.XES_CASE].to_numpy()
    activities = event_log[config.XES_NAME].to_numpy()
    c_unq, c_ind, c_counts = np.unique(cases, return_index=True, return_counts=True)
    variant_to_case = {}
    for i in range(len(c_ind)):
        si = c_ind[i]
        ei = si + c_counts[i]
        acts = tuple(activities[si:ei])
        if acts not in variant_to_case:
            variant_to_case[acts] = []
        variant_to_case[acts].append(c_unq[i])
    variants = []
    for variant, cases in variant_to_case.items():
        variants.append(Variant(id=str(uuid4()), log=log, activities=list(variant), frequency=len(cases), cases=cases))
    return variants

