from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pydantic_mongo import AbstractRepository

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


def get_all_constraints(client):
    constraint_repository = ConstraintRepository(database=client.get_database("bestPracticeData"))
    queried_constraints = list(constraint_repository.find_by({"support": {"$gte": 1}}))
    return queried_constraints


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
