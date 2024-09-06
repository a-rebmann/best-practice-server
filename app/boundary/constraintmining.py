from datetime import datetime

from uuid import uuid4
from app.control.recommender import Recommender
from app.control.constraint_fitter import FittedConstraintGenerator
from app.control.similarity_computer import SimilarityComputer
from app.control.util import ok


from app.boundary.dbconnect import ConstraintRepository, FittedConstraintRepository, MatchingRepository
from app.model.fittedConstraint import FittedConstraint
from app.model.matching import Matching





def get_constraint_components(config, obj_constraints, multi_obj_constraints, act_constraints, res_constraints):
    objects = list(set(constraint.object_type for constraint in obj_constraints if ok(config, constraint.object_type)))
    objects += list(
        set(constraint.right_operand for constraint in multi_obj_constraints if ok(config, constraint.right_operand)))
    objects += list(
        set(constraint.left_operand for constraint in multi_obj_constraints if ok(config, constraint.left_operand)))
    labels = list(constraint.left_operand for constraint in act_constraints if ok(config, constraint.left_operand))
    labels += list(constraint.right_operand for constraint in act_constraints if ok(config, constraint.right_operand))
    labels += list(constraint.left_operand for constraint in res_constraints if ok(config, constraint.left_operand))
    resources = list(constraint.object_type for constraint in res_constraints if ok(config, constraint.object_type))
    return objects, labels, resources


def compute_relevance(config, nlp, obj_constraints, multi_obj_constraints, act_constraints, res_constraints,
                      objects, labels, resources, log_info, precompute=True) -> list[FittedConstraint]:
    sim_computer = SimilarityComputer(config, nlp, log_info)
    constraints = sim_computer.compute_similarities(log_info, obj_constraints, multi_obj_constraints, act_constraints,
                                                    res_constraints, objects, labels, resources,
                                                    pre_compute=precompute)
    nlp.store_sims()
    return constraints


def recommend_constraints(config, rec_config, constraints, log_info):
    constraint_fitter = FittedConstraintGenerator(config, log_info)
    fitted_constraints = constraint_fitter.fit_constraints(constraints)
    recommender = Recommender(config, rec_config, log_info)
    selected_constraints = recommender.recommend_by_activation(fitted_constraints)
    recommended_constraints = recommender.recommend(selected_constraints)
    return recommended_constraints


def get_constraints_for_log_new(db_client, config, nlp_helper, log_info, query, rec_config):
    constraint_repository = ConstraintRepository(database=db_client.get_database("bestPracticeData"))
    obj_query = query.copy()
    obj_query["level"] = config.OBJECT
    obj_constraints = list(constraint_repository.find_by(obj_query))

    multi_obj_query = query.copy()
    multi_obj_query["level"] = config.MULTI_OBJECT
    multi_obj_constraints = list(constraint_repository.find_by(multi_obj_query))

    act_query = query.copy()
    act_query["level"] = config.ACTIVITY
    act_constraints = list(constraint_repository.find_by(act_query))

    res_query = query.copy()
    res_query["level"] = config.RESOURCE
    res_constraints = list(constraint_repository.find_by(res_query))
    objects, labels, resources = get_constraint_components(config, obj_constraints, multi_obj_constraints,
                                                           act_constraints, res_constraints)
    nlp_helper.pre_compute_embeddings(sentences=objects + labels + resources)
    constraints_with_similarity = compute_relevance(config, nlp_helper, obj_constraints, multi_obj_constraints,
                                                    act_constraints, res_constraints, objects, labels, resources,
                                                    log_info, precompute=True)
    matching_repository = MatchingRepository(database=db_client.get_database("bestPracticeData"))
    considered_consts = obj_constraints + multi_obj_constraints + act_constraints + res_constraints
    cons_ids = [constraint.id for constraint in considered_consts]
    const_ids = cons_ids + query["id"]["$nin"]
    matching_repository.save(Matching(id=str(uuid4()), 
                                        log_id=log_info.log_id, 
                                        considered_constraints=const_ids,
                                        time_of_matching=datetime.now()
                                        ))
    recommended_constraints = recommend_constraints(config, rec_config, constraints_with_similarity, log_info)
    fitted_constraint_repository = FittedConstraintRepository(database=db_client.get_database("bestPracticeData"))
    fitted_constraint_repository.save_many(recommended_constraints)
    return list(fitted_constraint_repository.find_by({"log": log_info.log_id}))



