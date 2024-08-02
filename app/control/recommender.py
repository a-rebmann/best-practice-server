from semconstmining.declare.enums import Template
from semconstmining.log.loginfo import LogInfo
from semconstmining.selection.instantiation.recommendation_config import RecommendationConfig

import logging

from app.model.fittedConstraint import FittedConstraint

_logger = logging.getLogger(__name__)


class Recommender:

    def __init__(self, config, recommender_config: RecommendationConfig, log_info: LogInfo):
        self.config = config
        self.recommender_config = recommender_config
        self.log_info = log_info
        self.activation_based_on = {
            Template.ABSENCE.templ_str: [],
            Template.EXISTENCE.templ_str: [],
            Template.EXACTLY.templ_str: [],
            Template.INIT.templ_str: [],
            Template.END.templ_str: [],
            Template.CHOICE.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.EXCLUSIVE_CHOICE.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.RESPONDED_EXISTENCE.templ_str: [self.config.LEFT_OPERAND],
            Template.RESPONSE.templ_str: [self.config.LEFT_OPERAND],
            Template.ALTERNATE_RESPONSE.templ_str: [self.config.LEFT_OPERAND],
            Template.CHAIN_RESPONSE.templ_str: [self.config.LEFT_OPERAND],
            Template.PRECEDENCE.templ_str: [self.config.RIGHT_OPERAND],
            Template.ALTERNATE_PRECEDENCE.templ_str: [self.config.RIGHT_OPERAND],
            Template.CHAIN_PRECEDENCE.templ_str: [self.config.RIGHT_OPERAND],
            Template.SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.ALTERNATE_SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.CHAIN_SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.CO_EXISTENCE.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],

            Template.NOT_RESPONDED_EXISTENCE: [self.config.LEFT_OPERAND],
            Template.NOT_RESPONSE.templ_str: [self.config.LEFT_OPERAND],
            Template.NOT_CHAIN_RESPONSE.templ_str: [self.config.LEFT_OPERAND],
            Template.NOT_PRECEDENCE.templ_str: [self.config.RIGHT_OPERAND],
            Template.NOT_CHAIN_PRECEDENCE.templ_str: [self.config.RIGHT_OPERAND],
            Template.NOT_SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.NOT_ALTERNATE_SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
            Template.NOT_CHAIN_SUCCESSION.templ_str: [self.config.LEFT_OPERAND, self.config.RIGHT_OPERAND],
        }

    def recommend_by_activation(self, constraints):
        """
        Recommends constraints based on the activation of the constraint.
        :return: A dataframe with the recommended constraints.
        """
        if len(constraints) == 0:
            return constraints
        activated_constraints = [constraint for constraint in constraints if self._compute_activation(constraint)]
        return activated_constraints

    def _compute_activation(self, fitted_constraint: FittedConstraint):
        """
        Computes the activation of a constraint.
        :param row: The row of a constraint.
        :return: True if the constraint should be activated, False otherwise.
        """
        if fitted_constraint.constraint.constraint_type not in self.activation_based_on:
            return 0
        if len(self.activation_based_on[fitted_constraint.constraint.constraint_type]) == 0:
            return 1
        res = []
        for column in self.activation_based_on[fitted_constraint.constraint.constraint_type]:
            if column == self.config.LEFT_OPERAND:
                if fitted_constraint.left_operand is None or fitted_constraint.left_operand == "":
                    res.append(0)
                elif fitted_constraint.constraint.level == self.config.MULTI_OBJECT and fitted_constraint.left_operand in self.log_info.objects:
                    res.append(1)
                elif fitted_constraint.constraint.level == self.config.OBJECT and fitted_constraint.left_operand in self.log_info.actions:
                    res.append(1)
                elif fitted_constraint.constraint.level == self.config.ACTIVITY and fitted_constraint.left_operand in self.log_info.labels:
                    res.append(1)
                else:
                    res.append(0)
            elif column == self.config.RIGHT_OPERAND:
                if fitted_constraint.right_operand is None or fitted_constraint.right_operand == "":
                    res.append(0)
                elif fitted_constraint.constraint.level == self.config.MULTI_OBJECT and fitted_constraint.right_operand in self.log_info.objects:
                    res.append(1)
                elif fitted_constraint.constraint.level == self.config.OBJECT and fitted_constraint.right_operand in self.log_info.actions:
                    res.append(1)
                elif fitted_constraint.constraint.level == self.config.ACTIVITY and fitted_constraint.right_operand in self.log_info.labels:
                    res.append(1)
                else:
                    res.append(0)
        return 1 if (len(res) > 0 and any(res)) or (len(res) == 0) else 0

    def recommend(self, constraints):
        if len(constraints) == 0:
            return constraints

        act_consts_support = [fitted_constraint.constraint.support for fitted_constraint in constraints
                              if fitted_constraint.constraint.level == self.config.ACTIVITY]
        max_support_act = max(act_consts_support) if len(act_consts_support) > 0 else 0
        obj_consts_support = [fitted_constraint.constraint.support for fitted_constraint in constraints
                                if fitted_constraint.constraint.level == self.config.OBJECT]
        max_support_obj = max(obj_consts_support) if len(obj_consts_support) > 0 else 0
        multi_obj_consts_support = [fitted_constraint.constraint.support for fitted_constraint in constraints
                                    if fitted_constraint.constraint.level == self.config.MULTI_OBJECT]
        max_support_multi_obj = max(multi_obj_consts_support) if len(multi_obj_consts_support) > 0 else 0
        res_consts_support = [fitted_constraint.constraint.support for fitted_constraint in constraints
                                if fitted_constraint.constraint.level == self.config.RESOURCE]
        max_support_res = max(res_consts_support) if len(res_consts_support) > 0 else 0
        max_support_per_level = {
            self.config.ACTIVITY: max_support_act,
            self.config.OBJECT: max_support_obj,
            self.config.MULTI_OBJECT: max_support_multi_obj,
            self.config.RESOURCE: max_support_res
        }
        for fitted_constraint in constraints:
            sim_score = self.get_sim_score(fitted_constraint)
            fitted_constraint.relevance = (1 - self.recommender_config.semantic_weight) * (
                    fitted_constraint.constraint.support / max_support_per_level[fitted_constraint.constraint.level]) + \
                                          self.recommender_config.semantic_weight * sim_score \
                if fitted_constraint.constraint.support > 0 else 0

        _logger.info("Computed relevance scores.")
        constraints = [constraint for constraint in constraints if
                       constraint.relevance >= self.recommender_config.relevance_thresh]
        _logger.info("Recommended {} constraints".format(len(constraints)))
        return constraints

    def get_sim_score(self, fitted_constraint: FittedConstraint):
        if (fitted_constraint.constraint.level == self.config.OBJECT and fitted_constraint.object_type in
                fitted_constraint.similarity):
            return fitted_constraint.similarity[fitted_constraint.object_type]
        elif (fitted_constraint.left_operand in fitted_constraint.similarity and fitted_constraint.right_operand in
              fitted_constraint.similarity):
            return (fitted_constraint.similarity[fitted_constraint.left_operand] +
                    fitted_constraint.similarity[fitted_constraint.right_operand]) / 2
        elif fitted_constraint.left_operand in fitted_constraint.similarity:
            return fitted_constraint.similarity[fitted_constraint.left_operand]
        elif fitted_constraint.right_operand in fitted_constraint.similarity:
            return fitted_constraint.similarity[fitted_constraint.right_operand]
