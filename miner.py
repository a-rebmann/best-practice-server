import os
from pathlib import Path

import pandas as pd
from app.boundary.dbconnect import AppConfigurationRepository, ConstraintRepository, get_base_config, get_db_client
from app.model.constraint import Constraint


BPMN_MINED = "mined from BPMN"
PLAYOUT_DECLARE_MINER = "Declare constraints mined from played-out model"

def check_status_and_populate_db(client, conf, resource_handler):
    constraint_repository = ConstraintRepository(database=client.get_database("bestPracticeData"))
    constraint_repository.get_collection().delete_many({})
    constraints = get_or_mine_constraints(conf, resource_handler, min_support=1)
    print(len(constraints), "constraints found")
    constraint_objects = []
    cnt = 0
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
                                    support=constraint[conf.SUPPORT],
                                    provision_type=BPMN_MINED,
                                    provider=PLAYOUT_DECLARE_MINER)
        constraint_objects.append(new_constraint)
        cnt += 1
        if cnt % 1000 == 0:
            constraint_repository.save_many(constraint_objects)
            constraint_objects = []
    if len(constraint_objects) > 0:
        constraint_repository.save_many(constraint_objects)
    configuration_repository = AppConfigurationRepository(database=client.get_database("bestPracticeData"))
    base_config = get_base_config(client)
    configuration_repository.save(base_config)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    from semconstmining.parsing.label_parser.nlp_helper import NlpHelper
    from semconstmining.main import get_resource_handler, get_or_mine_constraints
    from semconstmining.config import Config

    conf = Config(Path(__file__).parents[0].resolve(), "semantic_sap_sam_filtered")
    nlp_helper = NlpHelper(conf)
    resource_handler = get_resource_handler(conf, nlp_helper=nlp_helper)
    client = get_db_client(os.environ.get('DB_URI'))
    check_status_and_populate_db(client, conf, resource_handler)
