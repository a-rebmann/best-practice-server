import json
import os
import shutil
from pathlib import Path
from typing import Union, List
from uuid import uuid4

from pydantic import BaseModel
from pydantic_settings import BaseSettings
from fastapi import FastAPI, Body, Request, Response, File, UploadFile, HTTPException
from dotenv import load_dotenv

from app.boundary.ImageGenerator import ImageGenerator
from app.boundary.SignavioAuthenticator import SignavioAuthenticator
from app.boundary.configuremiddlewares import configure_middlewares
from app.boundary.constraintmining import get_constraints_for_log_new
from app.boundary.dbconnect import ConstraintRepository, FittedConstraintRepository, MatchingRepository, ViolationRepository, get_base_config
from app.boundary.dbconnect import get_db_client
from app.control.log_handling import get_variants, get_violated_variants
from app.model.configuration import AppConfiguration
from app.model.constraint import Constraint
from app.control.constraint_checking import check_constraints

from semconstmining.parsing.label_parser.nlp_helper import NlpHelper
from semconstmining.main import get_resource_handler, get_log_and_info
from semconstmining.config import Config
from semconstmining.selection.instantiation.recommendation_config import RecommendationConfig

from app.model.fittedConstraint import FittedConstraint
from app.model.variant import Variant
from app.model.violatedVariant import ViolatedVariant
from app.model.violation import Violation
from app.util.fileutils import check_data_directories_on_start

import logging

_logger = logging.getLogger(__name__)
load_dotenv()


class Settings(BaseSettings):
    """
    App configuration. Fields are automatically populated from environment variables.
    """
    # ## Uvicorn configuration
    # Host name to run under
    host: str = os.environ.get('HOST', '0.0.0.0')
    # Port to run app on
    port: int = int(os.environ.get('PORT', 8000))
    # Root path under which the app is accessed
    root_path: str = os.environ.get('ROOT_PATH', '')
    # SSL key file
    ssl_keyfile: str = os.environ.get('SSL_KEYFILE', '')
    # SSL certificate file
    ssl_certfile: str = os.environ.get('SSL_CERTFILE', '')
    develop: bool = os.environ.get('DEVELOPMENT', 'false').lower() == 'true'
    n_workers: int = 1
    cors_origins: Union[str, None] = "*"
    # Define the user and password
    user: str = os.environ.get('DB_USER', '')
    password: str = os.environ.get('DB_PASSWORD', '')
    # Define the connection string
    db_uri: str = os.environ.get('DB_URI', '')

    # Signavio stuff
    signavio_user: str = os.environ.get('SIGNAVIO_USER', '')
    signavio_password: str = os.environ.get('SIGNAVIO_PASSWORD', '')
    signavio_url: str = os.environ.get('SIGNAVIO_URL', '')
    signavio_workspace: str = os.environ.get('SIGNAVIO_WORKSPACE', '')

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
        check_data_directories_on_start(cls.miningconfig)
        cls.nlp_helper = NlpHelper(cls.miningconfig)
        cls.resource_handler = get_resource_handler(cls.miningconfig, cls.nlp_helper)
        cls.signavio_auth = SignavioAuthenticator(settings.signavio_url, settings.signavio_user,
                                                  settings.signavio_password, settings.signavio_workspace)
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


class ViolatedVariantCollection(BaseModel):
    violated_variants: list[ViolatedVariant]


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
        return json.dumps({"logs": [file for file in os.listdir(app.state.state.log_path) if file.endswith(".xes")]})

    @app.get("/constraints/{model_id}", responses={200: {"content": {"image/png": {}}}}, response_class=Response)
    def get_constraint_models(model_id: str):
        model_json = app.state.state.resource_handler.bpmn_models.loc[model_id, 'model_json']
        gen = ImageGenerator(app.state.state.signavio_auth)
        image_bytes = gen.generate_image("", model_json, app.state.state.miningconfig.BPMN2_NAMESPACE)
        return Response(content=image_bytes, media_type="image/png")

    @app.get("/constraints/{constraint_id}/models")
    def get_constraint_model(constraint_id: str):
        constraint_repository = ConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        constraint = list(constraint_repository.find_by({"id": constraint_id}))
        if len(constraint) == 0:
            return json.dumps({"models": []})
        constraint = constraint[0]
        # get model from resource handler
        model_ids = constraint.processmodel_id.split(" | ")
        return json.dumps({"models": model_ids})

    @app.get("/constraints")
    def get_constraints():
        constraint_repository = ConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        res = ConstraintCollection(constraints=list(constraint_repository.find_by({"support": {"$gte": 2}})))
        # convert to json
        return res.model_dump_json()

    @app.post("/constraints/new")
    def create_new_constraint(constraint: Constraint):
        print(constraint.model_dump())
        # TODO prepare constraint for saving
        constraint.id = str(uuid4())
        if constraint.right_operand == "":
            constraint.arity = "Unary"
            constraint.constraint_str = f"{constraint.constraint_type} [{constraint.left_operand}] | | |"
        else:
            constraint.arity = "Binary"
            constraint.constraint_str = f"{constraint.constraint_type} [{constraint.left_operand}, {constraint.right_operand}] | | |"
        constraint.provider = "user"
        constraint.provision_type = "maually created"
        constraint_repository = ConstraintRepository(
              database=app.state.state.db_client.get_database("bestPracticeData"))
        constraint_repository.save(constraint)
        return constraint.model_dump_json()

    class LogConf(BaseModel):
        log: str
        min_relevance: float
        min_support: float
        unary: bool
        binary: bool
        constraint_levels: List[str]


    @app.put("/constraints/log")
    def get_all_constraints_log(log_conf: LogConf):
        if log_conf.log not in os.listdir(app.state.state.log_path):
            return json.dumps({"constraints": []})
        # load the log from disk into cache
        if log_conf.log not in app.state.state.log_cache:
            try:
                event_log, log_info = get_log_and_info(conf=app.state.state.miningconfig,
                                                                           nlp_helper=app.state.state.nlp_helper,
                                                                           process=log_conf.log)
                log_info.log_id = log_conf.log
                app.state.state.log_cache[log_conf.log] = (event_log, log_info)
            except IndexError as e:
                _logger.error(f"Error while loading log {log_conf.log}: {e}")
                raise HTTPException(status_code=422, detail=f"Log {log_conf.log} not processable")
        arities = []
        if log_conf.unary:
            arities.append(app.state.state.miningconfig.UNARY)
        if log_conf.binary:
            arities.append(app.state.state.miningconfig.BINARY)

        matching_repository = MatchingRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        matchings=list(matching_repository.find_by({"log_id": log_conf.log}, sort=[("time_of_matching", -1)]))
        if len(matchings) > 0:
            matching = matchings[0]
            print("Matched on ", matching.time_of_matching)
            already_fitted = matching.considered_constraints
        else:
            already_fitted = []

        query = {"level": {"$in": log_conf.constraint_levels},
                "support": {"$gte": log_conf.min_support},
                "arity": {"$in": arities},
                "support": {"$gte": log_conf.min_support},
                "id": {"$nin": already_fitted}}    
        print(len(already_fitted), "constraints already fitted")
        rec_config = RecommendationConfig(app.state.state.miningconfig, semantic_weight=log_conf.min_relevance, top_k=250)
        get_constraints_for_log_new(db_client=app.state.state.db_client,
                                    config=app.state.state.miningconfig,
                                    nlp_helper=app.state.state.nlp_helper,
                                    log_info=app.state.state.log_cache[log_conf.log][1],
                                    query=query,
                                    rec_config=rec_config)
        
        fitted_constraint_repository = FittedConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        
        query = {"log": log_conf.log,
                "relevance": {"$gte": log_conf.min_relevance},
                "constraint.level": {"$in": log_conf.constraint_levels},
                "constraint.support": {"$gte": log_conf.min_support},
                "constraint.arity": {"$in": arities},
                "constraint.support": {"$gte": log_conf.min_support},
                "id": {"$nin": already_fitted}}
        res = FittedConstraintCollection(
            constraints=list(fitted_constraint_repository.find_by(query)))
        return res.model_dump_json()

    @app.post("/violations")
    def get_violations(constraint_ids: List[str] = Body()):
        constraint_repository = FittedConstraintRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        constraintsToCheck = list(constraint_repository.find_by({"id": {"$in": constraint_ids}}))
        if len(constraintsToCheck) == 0:
            return ViolationCollection(violations=[]).model_dump_json()
        log = constraintsToCheck[0].log
        # get violations for constraints from database that are already stored
        violation_repository = ViolationRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        stored_violations = list(violation_repository.find_by({"constraint.id": {"$in": constraint_ids},
                                                               "log": log}))
        # remove constraint ids for which we already have violations
        constraint_ids = [c for c in constraint_ids if c not in [v.constraint.id for v in stored_violations]]
        constraintsToCheck = [c for c in constraintsToCheck if c.id in constraint_ids]
        all_violations = stored_violations
        if len(constraintsToCheck) > 0:
            if log not in app.state.state.log_cache:
                app.state.state.log_cache[log] = get_log_and_info(conf=app.state.state.miningconfig,
                                                                  nlp_helper=app.state.state.nlp_helper, process=log)
            res = check_constraints(constraintsToCheck, app.state.state.miningconfig, log,
                                    app.state.state.log_cache[log][0],
                                    app.state.state.nlp_helper)
            new_violations = []
            for level, violations in res.items():
                new_violations.extend(violations)
            # store violations in database
            violation_repository.save_many(new_violations)
            all_violations += new_violations
        return ViolationCollection(violations=all_violations).model_dump_json()

    @app.post("/violations/variants")
    def get_violated_log_variants(violation_ids: List[str] = Body()):
        violation_repository = ViolationRepository(
            database=app.state.state.db_client.get_database("bestPracticeData"))
        stored_violations = list(violation_repository.find_by({"id": {"$in": violation_ids}}))
        print(len(stored_violations), "violations found")
        if len(stored_violations) == 0:
            return VariantCollection(variants=[]).model_dump_json()
        log = stored_violations[0].log
        log_info = app.state.state.log_cache[log][1]
        variants = get_variants(log, app.state.state.log_cache[log][0], app.state.state.miningconfig)
        violated_variants = get_violated_variants(variants, log_info, stored_violations, app.state.state.miningconfig)
        if len(violated_variants) > 100:
            # sort descending by frequency
            violated_variants = sorted(violated_variants, key=lambda x: x.variant.frequency, reverse=True)
        return ViolatedVariantCollection(violated_variants=violated_variants[:10]).model_dump_json()

    @app.post("/logs/variants")
    def get_log_variants(log: str = Body()):
        if log not in os.listdir(app.state.state.log_path):
            return json.dumps({"variants": []})
        return VariantCollection(
            variants=get_variants(log, app.state.state.log_cache[log][0], app.state.state.miningconfig)[
                     :10]).model_dump_json()

    @app.get("/config")
    def get_config(request: Request):
        print(request.headers)
        return get_base_config(app.state.state.db_client)

    @app.post("/config")
    def set_config(request: Request, config: AppConfiguration):
        print(config)
        print(request)
        return config

    @app.post("/logs")
    async def upload_file(file: UploadFile = File(...)):
        file_path = os.path.join(app.state.state.log_path, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return json.dumps({"logs": [file for file in os.listdir(app.state.state.log_path) if file.endswith(".xes")]})

    return app


# Default settings and app instance used to run uvicorn
SETTINGS = Settings()
APP = create_app(SETTINGS)
