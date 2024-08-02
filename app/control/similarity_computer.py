import itertools
import logging
from uuid import uuid4

from app.control.util import ok
from app.model.constraint import Constraint
from app.model.fittedConstraint import FittedConstraint

_logger = logging.getLogger(__name__)


class SimilarityComputer:

    def __init__(self, config, nlp_helper, log_info):
        self.config = config
        self.nlp_helper = nlp_helper
        self.sims = {}
        self.log_info = log_info
        self.counter = 0

    def compute_similarities(self, log_info, act_constraints, obj_constraints, multi_obj_constraints, res_constraints,
                             objects, labels, resources, pre_compute=False):
        if pre_compute:
            self.nlp_helper.pre_compute_embeddings(sentences=self.log_info.labels + self.log_info.names +
                                                             list(self.log_info.resources_to_tasks.keys()) +
                                                             self.log_info.objects + self.log_info.actions)
        self.sims = self.precompute_sims(objects, labels, resources)
        fitted_constraints = [FittedConstraint(id=str(uuid4()),
                                               log=log_info.log_id,
                                               left_operand=constraint.left_operand,
                                               right_operand=constraint.right_operand,
                                               object_type=constraint.object_type,
                                               constraint_str=constraint.constraint_str,
                                               similarity=self._compute_similarities(constraint),
                                               relevance=0,
                                               constraint=constraint)
                              for constraint in act_constraints +
                              obj_constraints + multi_obj_constraints + res_constraints]
        self.nlp_helper.store_sims()
        return fitted_constraints

    def _compute_similarities(self, constraint: Constraint):
        self.counter += 1
        if self.counter % 500 == 0:
            _logger.info(f"Computing relevance for constraint number {self.counter}")
        if constraint.level == self.config.OBJECT:
            return self.get_similarities_for_object_constraint(constraint)
        elif constraint.level == self.config.MULTI_OBJECT:
            return self.get_similarities_for_multi_object_constraint(constraint)
        elif constraint.level == self.config.ACTIVITY:
            return self.get_similarities_for_activity_constraint(constraint)
        elif constraint.level == self.config.RESOURCE:
            return self.get_similarities_for_resource_constraint(constraint)

    def get_similarities_for_object_constraint(self, constraint: Constraint):
        object_sims = {self.config.OBJECT: {}, self.config.ACTION: {}}
        for ext in self.log_info.objects:
            combi = [(constraint.object_type, ext)]
            object_sims[self.config.OBJECT][ext] = self.nlp_helper.get_sims(combi)[0]
        for ext in self.log_info.actions:
            synonyms = self.nlp_helper.get_synonyms(ext)
            similar_actions = self.nlp_helper.get_similar_actions(ext)
            if ok(self.config, constraint.left_operand):
                if constraint.left_operand in synonyms or constraint.left_operand in similar_actions:
                    object_sims[self.config.ACTION][constraint.left_operand] = ext
            if ok(self.config, constraint.right_operand):
                if constraint.right_operand in synonyms or constraint.right_operand in similar_actions:
                    object_sims[self.config.ACTION][constraint.right_operand] = ext
        return object_sims

    def get_similarities_for_multi_object_constraint(self, constraint: Constraint):
        object_sims = {}
        if ok(self.config, constraint.left_operand):
            object_sims[self.config.LEFT_OPERAND] = {}
        if ok(self.config, constraint.right_operand):
            object_sims[self.config.RIGHT_OPERAND] = {}
        for ext in self.log_info.objects:
            if self.config.LEFT_OPERAND in object_sims:
                combi = [(constraint.left_operand, ext)]
                object_sims[self.config.LEFT_OPERAND][ext] = self.nlp_helper.get_sims(combi)[0]
            if self.config.RIGHT_OPERAND in object_sims:
                combi = [(constraint.left_operand, ext)]
                object_sims[self.config.RIGHT_OPERAND][ext] = self.nlp_helper.get_sims(combi)[0]
        return object_sims

    def get_similarities_for_activity_constraint(self, constraint: Constraint):
        label_sims = {}
        if ok(self.config, constraint.left_operand):
            label_sims[self.config.LEFT_OPERAND] = {}
        if ok(self.config, constraint.right_operand):
            label_sims[self.config.RIGHT_OPERAND] = {}
        for ext in self.log_info.labels:
            if self.config.LEFT_OPERAND in label_sims:
                combi = [(constraint.left_operand, ext)]
                label_sims[self.config.LEFT_OPERAND][ext] = self.nlp_helper.get_sims(combi)[0]
            if self.config.RIGHT_OPERAND in label_sims:
                combi = [(constraint.right_operand, ext)]
                label_sims[self.config.RIGHT_OPERAND][ext] = self.nlp_helper.get_sims(combi)[0]
        return label_sims

    def get_similarities_for_resource_constraint(self, constraint: Constraint):
        label_sims = {self.config.LEFT_OPERAND: {}, self.config.RESOURCE: {}}
        if ok(self.config, constraint.left_operand):
            label_sims[self.config.LEFT_OPERAND] = {}
        for ext in self.log_info.labels:
            if self.config.LEFT_OPERAND in label_sims:
                combi = [(constraint.left_operand, ext)]
                label_sims[self.config.LEFT_OPERAND][ext] = self.nlp_helper.get_sims(combi)[0]
        for ext in self.log_info.resources_to_tasks:
            combi = [(constraint.object_type, ext)]
            label_sims[self.config.RESOURCE][ext] = self.nlp_helper.get_sims(combi)[0]
        return label_sims

    def get_max_scores(self, fitted_constraint: FittedConstraint):
        score = 0.0
        if (self.config.OBJECT in fitted_constraint.similarity and
                len(fitted_constraint.similarity[self.config.OBJECT]) > 0):
            score = max(fitted_constraint.similarity[self.config.OBJECT].values())
        if (self.config.LEFT_OPERAND in fitted_constraint.similarity and
                len(fitted_constraint.similarity[self.config.LEFT_OPERAND]) > 0):
            score = max(fitted_constraint.similarity[self.config.LEFT_OPERAND].values())
        if (self.config.RIGHT_OPERAND in fitted_constraint.similarity and
                len(fitted_constraint.similarity[self.config.RIGHT_OPERAND]) > 0):
            new_score = max(fitted_constraint.similarity[self.config.RIGHT_OPERAND].values())
            if new_score > score:
                score = new_score
        return score

    def precompute_sims(self, objects, labels, resources):
        object_combis = [(x, y) for x, y in itertools.product(objects, self.log_info.objects) if x != y]
        label_combis = [(x, y) for x, y in itertools.product(labels, self.log_info.labels) if x != y]
        resource_combis = [(x, y) for x, y in itertools.product(resources, self.log_info.resources_to_tasks) if x != y]
        _logger.info(
            "Precomputing similarities for {} object combinations, {} label combinations and {} resource combinations".format(
                len(object_combis), len(label_combis), len(resource_combis)))
        sims = self.nlp_helper.get_sims(object_combis)
        sims += self.nlp_helper.get_sims(label_combis)
        sims += self.nlp_helper.get_sims(resource_combis)
        return {x: y for x, y in zip(object_combis + label_combis + resource_combis, sims)}
