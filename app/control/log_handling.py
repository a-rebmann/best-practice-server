from pandas import DataFrame
from semconstmining.config import Config
import numpy as np
from uuid import uuid4

from app.model.variant import Variant
from app.model.violatedVariant import ViolatedVariant


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


def get_violated_variants(variants, log_info, violations, conf):
    violated_variants = []
    # we check per violation for which variants
    for variant in variants:
        any_violation = False
        activity_to_violations = {}
        for violation in violations:
            if set(violation.cases).intersection(variant.cases):
                any_violation = True
                for activity in variant.activities:
                    if activity not in activity_to_violations:
                        activity_to_violations[activity] = []
                    # first standard activity level and role constraints
                    if (violation.constraint.left_operand in log_info.label_to_original_label and
                            activity in log_info.label_to_original_label[violation.constraint.left_operand]):
                        activity_to_violations[activity].append(violation.constraint.id)
                    elif (violation.constraint.right_operand in log_info.label_to_original_label and
                          activity in log_info.label_to_original_label[violation.constraint.right_operand]):
                        activity_to_violations[activity].append(violation.constraint.id)

                    # then object level constraints
                    elif (violation.constraint.object_type in log_info.object_to_original_labels and
                          activity in log_info.object_to_original_labels[violation.constraint.object_type]):
                        if violation.constraint.left_operand in log_info.action_to_original_labels and \
                                activity in log_info.action_to_original_labels[violation.constraint.left_operand]:
                            activity_to_violations[activity].append(violation.constraint.id)
                        elif violation.constraint.right_operand in log_info.action_to_original_labels and \
                                activity in log_info.action_to_original_labels[violation.constraint.right_operand]:
                            activity_to_violations[activity].append(violation.constraint.id)

                    # then multi object constraints
                    elif (violation.constraint.constraint.level == conf.MULTI_OBJECT and
                          violation.constraint.object_type in log_info.object_to_original_labels and
                          activity in log_info.object_to_original_labels[violation.constraint.object_type]):
                        activity_to_violations[activity].append(violation.constraint.id)
        if any_violation:
            violated_variants.append(ViolatedVariant(id=str(uuid4()), variant=variant,
                                                     activities=activity_to_violations))
    return violated_variants

