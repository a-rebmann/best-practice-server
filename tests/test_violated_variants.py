from pathlib import Path
from uuid import uuid4

from semconstmining.parsing.label_parser.nlp_helper import NlpHelper
from semconstmining.main import get_resource_handler, get_or_mine_constraints, get_log_and_info
from semconstmining.config import Config

from app.app import VariantCollection
from app.boundary.dbconnect import get_db_client, ViolationRepository
from app.control.log_handling import get_variants
from app.model.violatedVariant import ViolatedVariant


def test_violated_variants():
    user: str = "rebmann"
    password: str = "adhps3zv2LnMt06y"
    conf = Config(Path(__file__).parents[1].resolve(), "semantic_sap_sam_filtered")
    nlp_helper = NlpHelper(conf)
    resource_handler = get_resource_handler(conf, nlp_helper=nlp_helper)
    # Define the connection string
    db_uri: str = f"mongodb+srv://{user}:{password}@bpapp.6xuzdhw.mongodb.net/?retryWrites=true&w=majority&appName=BPApp"
    db_client = get_db_client(db_uri)
    violation_repository = ViolationRepository(database=db_client.get_database("bestPracticeData"))
    stored_violations = list(violation_repository.find_by({"frequency": {"$gte": 1}}))
    print(len(stored_violations), "violations found")
    if len(stored_violations) == 0:
        return VariantCollection(variants=[]).model_dump_json()
    log = stored_violations[0].log
    event_log, log_info = get_log_and_info(conf=conf, nlp_helper=nlp_helper, process=log)
    variants = get_variants(log, event_log, conf)
    violated_variants = []
    # we check per violation for which variants
    for variant in variants:
        any_violation = False
        activity_to_violations = {}
        for violation in stored_violations:
            if any([c in variant.cases for c in violation.cases]):
                any_violation = True
                print("Violation found")
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
    return VariantCollection(variants=violated_variants).model_dump_json()


test_violated_variants()