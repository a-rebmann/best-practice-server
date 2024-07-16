import json
import os
from pathlib import Path
from typing import Union, List

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from fastapi import FastAPI, Request, Body

from app.boundary.configuremiddlewares import configure_middlewares
from app.boundary.constraintmining import get_constraints_for_log
from app.boundary.dbconnect import ConstraintRepository, FittedConstraintRepository, ViolationRepository
from app.boundary.dbconnect import get_db_client
from app.control.log_handling import get_variants
from app.model.constraint import Constraint
from app.control.constraint_checking import check_constraints

from semconstmining.parsing.label_parser.nlp_helper import NlpHelper
from semconstmining.main import get_resource_handler, get_or_mine_constraints, get_log_and_info
from semconstmining.config import Config

from app.model.fittedConstraint import FittedConstraint
from app.model.variant import Variant
from app.model.violation import Violation


class Settings(BaseSettings):
    """
    App configuration. Fields are automatically populated from environment variables.
    """
    # ## Uvicorn configuration
    # Host name to run under
    host: str = "0.0.0.0"
    # Port to run app on
    port: int = 8000
    # Root path under which the app is accessed
    root_path: str = "/api"
    develop: bool = False
    n_workers: int = 1
    cors_origins: Union[str, None] = "*"

    # Define the user and password TODO read from dotenv
    user: str = "rebmann"
    password: str = "adhps3zv2LnMt06y"

    # Define the connection string
    db_uri: str = f"mongodb+srv://{user}:{password}@bpapp.6xuzdhw.mongodb.net/?retryWrites=true&w=majority&appName=BPApp"

    log_path: str = "./data/logs/"

    log_level: str = os.environ.get('LOG_LEVEL', 'info')
    log_format: str = os.environ.get(
        'LOG_FORMAT',
        '[%(asctime)s] [%(name)s] [%(process)d] [%(levelname)s] %(message)s')
    max_number_of_constraints: int = 1000


class State(BaseModel):
    """
    Global app state like database connections.
    Is initialized from `Settings` once the app is created.
    """

    @classmethod
    def from_settings(cls, settings: Settings):
        cls.db_client = get_db_client(settings.db_uri)
        cls.log_path = settings.log_path
        cls.miningconfig = Config(Path(__file__).parents[1].resolve(), "semantic_sap_sam_filtered")
        cls.nlp_helper = NlpHelper(cls.miningconfig)
        cls.resource_handler = get_resource_handler(cls.miningconfig, cls.nlp_helper)
        cls.constraints = get_or_mine_constraints(cls.miningconfig, cls.resource_handler, min_support=1)
        cls.log_cache = {}
        return cls()


class VariantCollection(BaseModel):
    variants: list[Variant]


class ConstraintCollection(BaseModel):
    constraints: list[Constraint]


class FittedConstraintCollection(BaseModel):
    constraints: list[FittedConstraint]


class ViolationCollection(BaseModel):
    violations: list[Violation]


class CheckingResult(BaseModel):
    object_level_violations: list[Violation]
    multi_object_violations: list[Violation]
    activity_level_violations: list[Violation]
    resource_level_violations: list[Violation]


def create_app(settings: Settings) -> FastAPI:
    """
    Create a new FastAPI app from configuration in `settings`. This makes it easy to
    configure the app as well as create new instances for testing.
    """
    app = FastAPI()
    state = State.from_settings(settings)
    configure_middlewares(app, settings)

    @app.on_event("startup")
    def on_startup():
        app.state.state = state

    @app.get("/health")
    def health():
        return "OK"

    @app.get("/logs")
    def get_all_logs():
        return json.dumps({"logs": os.listdir(app.state.state.log_path)})

    @app.get("/constraints")
    def get_all_constraints():
        constraint_repository = ConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        res = ConstraintCollection(constraints=list(constraint_repository.find_by({"support": {"$gte": 2}})))
        # convert to json
        return res.model_dump_json()

    @app.post("/constraints/log")
    def get_all_constraints_log(log: str = Body()):
        print(log)
        if log not in os.listdir(app.state.state.log_path):
            return json.dumps({"constraints": []})
        # load the log from disk into cache
        if log not in app.state.state.log_cache:
            app.state.state.log_cache[log] = get_log_and_info(conf=app.state.state.miningconfig,
                                                              nlp_helper=app.state.state.nlp_helper, process=log)
        constraint_repository = FittedConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        res = FittedConstraintCollection(constraints=list(constraint_repository.find_by({"log": log, "relevance": {"$gte": 0.8}})))
        if len(res.constraints) == 0:
            get_constraints_for_log(client=app.state.state.db_client, conf=app.state.state.miningconfig,
                                    nlp_helper=app.state.state.nlp_helper, constraints=app.state.state.constraints,
                                    log=log)
            res = FittedConstraintCollection(constraints=list(constraint_repository.find_by({"log": log})))
        return res.model_dump_json()

    @app.post("/violations")
    def get_violations(constraint_ids: List[str] = Body()):
        print(constraint_ids)
        constraint_repository = FittedConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        constraintsToCheck = list(constraint_repository.find_by({"id": {"$in": constraint_ids}}))
        if len(constraintsToCheck) == 0:
            return ViolationCollection(violations=[]).model_dump_json()
        log = constraintsToCheck[0].log
        # get violations for constraints from database that are already stored
        violation_repository = ViolationRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        stored_violations = list(violation_repository.find_by({"constraint_id": {"$in": constraint_ids}}))
        # remove constraint ids for which we already have violations
        constraint_ids = [c for c in constraint_ids if c not in [v.constraint_id for v in stored_violations]]
        constraintsToCheck = [c for c in constraintsToCheck if c.id in constraint_ids]
        all_violations = stored_violations
        if len(constraintsToCheck) > 0:
            if log not in app.state.state.log_cache:
                app.state.state.log_cache[log] = get_log_and_info(conf=app.state.state.miningconfig,
                                                                  nlp_helper=app.state.state.nlp_helper, process=log)
            res = check_constraints(constraintsToCheck, app.state.state.miningconfig, log, app.state.state.log_cache[log][0],
                                    app.state.state.nlp_helper)
            new_violations = []
            for level, violations in res.items():
                new_violations.extend(violations)
            # store violations in database
            violation_repository.save_many(new_violations)
            all_violations += new_violations
        return ViolationCollection(violations=all_violations).model_dump_json()

    @app.post("/logs/variants")
    def get_log_variants(log: str = Body()):
        if log not in os.listdir(app.state.state.log_path):
            return json.dumps({"variants": []})
        return VariantCollection(variants=get_variants(log, app.state.state.log_cache[log][0], app.state.state.miningconfig)).model_dump_json()
    return app


# Default settings and app instance used to run uvicorn
SETTINGS = Settings()
APP = create_app(SETTINGS)
