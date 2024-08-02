import os

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pydantic_mongo import AbstractRepository

from app.model.configuration import AppConfiguration
from app.model.constraint import Constraint
from app.model.fittedConstraint import FittedConstraint
from app.model.violation import Violation


class ConstraintRepository(AbstractRepository[Constraint]):
    class Meta:
        collection_name = "bestpractices"


class FittedConstraintRepository(AbstractRepository[FittedConstraint]):
    class Meta:
        collection_name = "fittedconstraints"


class ViolationRepository(AbstractRepository[Violation]):
    class Meta:
        collection_name = "violations"


class AppConfigurationRepository(AbstractRepository[AppConfiguration]):
    class Meta:
        collection_name = "configurations"


def get_all_constraints(client):
    constraint_repository = ConstraintRepository(database=client.get_database("bestPracticeData"))
    queried_constraints = list(constraint_repository.find_by({"support": {"$gte": 1}}))
    return queried_constraints


def get_base_config(client):
    configuration_repository = AppConfigurationRepository(database=client.get_database("bestPracticeData"))
    tmp = list(configuration_repository.find_by({"id": "base"}))
    if len(tmp) > 0:
        return tmp[0]
    constraints = get_all_constraints(client)
    constraint_levels = list(set([c.level for c in constraints]))
    constraint_types = list(set([c.constraint_type for c in constraints]))
    base_config = AppConfiguration(
        id="base",
        min_support=1,
        constraint_levels=constraint_levels,
        constraint_types=constraint_types,
        unary=True,
        binary=True
    )
    configuration_repository.save(base_config)
    return base_config


def get_db_client(uri):
    # Create a new client and connect to the server
    client = MongoClient(uri, server_api=ServerApi('1'))
    # Send a ping to confirm a successful connection
    try:
        client.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)
    return client


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    client = get_db_client(os.environ.get('DB_URI'))
    # delete fitted constraints and violations
    fitted_constraint_repository = FittedConstraintRepository(database=client.get_database("bestPracticeData"))
    fitted_constraint_repository.get_collection().delete_many({})
    violation_repository = ViolationRepository(database=client.get_database("bestPracticeData"))
    violation_repository.get_collection().delete_many({})
    # query all fitted constraints
    fitted_constraints = list(fitted_constraint_repository.find_by({}))
    print(len(fitted_constraints), "fitted constraints found")
    # query all violations
    violations = list(violation_repository.find_by({}))
    print(len(violations), "violations found")
