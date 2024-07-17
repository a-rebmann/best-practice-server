import os
from pathlib import Path

import pandas as pd

from app.model.constraint import Constraint
from semconstmining.main import get_or_mine_constraints, get_log_and_info, recommend_constraints_for_log, \
    get_parts_of_constraints, compute_relevance_for_log
from semconstmining.selection.instantiation.recommendation_config import RecommendationConfig

from app.boundary.dbconnect import ConstraintRepository, FittedConstraintRepository, get_db_client
from app.model.fittedConstraint import FittedConstraint


def check_status_and_populate_db(client, conf, resource_handler):
    constraint_repository = ConstraintRepository(database=client.get_database("bestPracticeData"))
    constraint_repository.get_collection().delete_many({"support": {"$gte": 1}})
    constraints = get_or_mine_constraints(conf, resource_handler, min_support=1)
    print(len(constraints), "constraints found")
    constraint_objects = []
    for idx, constraint in constraints.iterrows():
        new_constraint = Constraint(id=constraint[conf.RECORD_ID],
                                    constraint_type=constraint[conf.TEMPLATE],
                                    constraint_str=constraint[conf.CONSTRAINT_STR],
                                    arity=constraint[conf.OPERATOR_TYPE],
                                    level=constraint[conf.LEVEL],
                                    left_operand=constraint[conf.LEFT_OPERAND],
                                    right_operand="" if pd.isna(constraint[conf.RIGHT_OPERAND]) else constraint[
                                        conf.RIGHT_OPERAND],
                                    object_type="" if pd.isna(constraint[conf.OBJECT]) else constraint[conf.OBJECT],
                                    processmodel_id=constraint[conf.MODEL_ID],
                                    support=constraint[conf.SUPPORT])
        constraint_objects.append(new_constraint)
    constraint_repository.save_many(constraint_objects)


def get_constraints_for_log(client, conf, nlp_helper, constraints, log: str):
    constraint_repository = ConstraintRepository(database=client.get_database("bestPracticeData"))
    fitted_constraint_repository = FittedConstraintRepository(database=client.get_database("bestPracticeData"))
    nlp_helper.pre_compute_embeddings(sentences=get_parts_of_constraints(conf, constraints))
    rec_config = RecommendationConfig(conf, semantic_weight=0.9, top_k=250)
    event_log, log_info = get_log_and_info(conf, nlp_helper, log)
    precomputed = compute_relevance_for_log(conf, constraints, nlp_helper, log, pd_log=event_log, precompute=True)
    recommended_constraints = recommend_constraints_for_log(conf, rec_config, precomputed, nlp_helper, log,
                                                            pd_log=event_log)
    recommended_constraints[conf.RECORD_ID] = recommended_constraints[conf.FITTED_RECORD_ID].apply(lambda x: x.split("_")[0])
    print(len(recommended_constraints), "constraints recommended")
    constraint_objects = []
    for idx, constraint in recommended_constraints.iterrows():
        new_constraint = FittedConstraint(id=constraint[conf.FITTED_RECORD_ID],
                                          log=log,
                                          left_operand=constraint[conf.LEFT_OPERAND],
                                          right_operand="" if pd.isna(constraint[conf.RIGHT_OPERAND]) else constraint[
                                              conf.RIGHT_OPERAND],
                                          object_type="" if pd.isna(constraint[conf.OBJECT]) else constraint[conf.OBJECT],
                                          similarity=constraint[conf.INDIVIDUAL_RELEVANCE_SCORES],
                                          relevance=constraint[conf.RELEVANCE_SCORE],
                                          constraint=list(constraint_repository.find_by({"id": constraint[conf.RECORD_ID]}))[0]
                                          )
        constraint_objects.append(new_constraint)
    fitted_constraint_repository.save_many(constraint_objects)
    return list(fitted_constraint_repository.find_by({"log": log}))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    from semconstmining.parsing.label_parser.nlp_helper import NlpHelper
    from semconstmining.main import get_resource_handler, get_or_mine_constraints
    from semconstmining.config import Config
    conf = Config(Path(__file__).parents[2].resolve(), "semantic_sap_sam_filtered")
    nlp_helper = NlpHelper(conf)
    resource_handler = get_resource_handler(conf, nlp_helper=nlp_helper)
    client = get_db_client(os.environ.get('DB_URI'))
    check_status_and_populate_db(client, conf, resource_handler)
