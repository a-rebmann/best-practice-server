from copy import deepcopy

from app.model.fittedConstraint import FittedConstraint


class FittedConstraintGenerator:

    def __init__(self, config, log_info):
        self.config = config
        self.log_info = log_info

    def fit_constraints(self, constraints, sim_threshold=0.5):
        fitted_constraint_lists = [self.fit_constraint(constraint, sim_threshold) for constraint in constraints]
        fitted_constraints = [self.update_sims(fitted_constraint) for fitted_constraints in fitted_constraint_lists
                              for fitted_constraint in fitted_constraints if fitted_constraint is not None]
        return fitted_constraints

    def fit_constraint(self, fitted_constraint: FittedConstraint, sim_threshold):
        fitted_constraints = []
        if fitted_constraint.constraint.level == self.config.OBJECT:
            fitted_constraints.extend(self.fit_object_constraint(fitted_constraint, sim_threshold))
        elif (fitted_constraint.constraint.level == self.config.MULTI_OBJECT or
              fitted_constraint.constraint.level == self.config.ACTIVITY):
            fitted_constraints.extend(self.fit_multi_object_or_activity_constraint(fitted_constraint, sim_threshold))
        elif fitted_constraint.constraint.level == self.config.RESOURCE:
            fitted_constraints.extend(self.fit_resource_constraint(fitted_constraint, sim_threshold))
        return fitted_constraints

    def instantiate_obj_const(self, fitted_constraint_template: FittedConstraint, obj, act_l, act_r=None):
        fitted_constraint = deepcopy(fitted_constraint_template)
        fitted_constraint.object_type = obj
        fitted_constraint.constraint_str = fitted_constraint.constraint_str.replace(
            fitted_constraint.constraint.object_type, obj)
        fitted_constraint.id = fitted_constraint.id + "_" + self.config.OBJECT + "_" + obj
        if act_l == act_r:
            return None
        if act_l is not None:
            fitted_constraint.left_operand = act_l
            fitted_constraint.constraint_str = fitted_constraint.constraint_str.replace(
                fitted_constraint.constraint.left_operand, act_l)
        if act_r is not None:
            fitted_constraint.right_operand = act_r
            fitted_constraint.constraint_str = fitted_constraint.constraint_str.replace(
                fitted_constraint.constraint.right_operand, act_r)
        return fitted_constraint

    def fit_object_constraint(self, fitted_constraint_template: FittedConstraint, sim_threshold):
        sim_dict = fitted_constraint_template.similarity
        fitted_constraints = []
        if self.config.OBJECT in sim_dict:
            obj_sim = sim_dict[self.config.OBJECT]
            for obj, sim in obj_sim.items():
                if sim >= sim_threshold:
                    a_l = fitted_constraint_template.constraint.left_operand
                    a_r = fitted_constraint_template.constraint.right_operand
                    act_l = sim_dict[self.config.ACTION][a_l] if a_l and a_l in sim_dict[self.config.ACTION] else None
                    act_r = sim_dict[self.config.ACTION][a_r] if a_r and a_r in sim_dict[self.config.ACTION] else None
                    fitted_constraint = self.instantiate_obj_const(fitted_constraint_template, obj, act_l, act_r)
                    if fitted_constraint is not None:
                        fitted_constraints.append(fitted_constraint)
        return fitted_constraints

    def instantiate_multi_obj_or_act_constraint(self, fitted_constraint_template: FittedConstraint, l_obj=None, r_obj=None):
        fitted_constraint = deepcopy(fitted_constraint_template)
        if l_obj is not None:
            fitted_constraint.left_operand = l_obj
            fitted_constraint.constraint_str = fitted_constraint.constraint_str.replace(
                fitted_constraint.constraint.left_operand, l_obj)
            fitted_constraint.id = fitted_constraint.id + "_" + self.config.OBJECT + "_" + l_obj
        if r_obj is not None:
            fitted_constraint.right_operand = r_obj
            fitted_constraint.constraint_str = fitted_constraint.constraint_str.replace(
                fitted_constraint.constraint.right_operand, r_obj)
            fitted_constraint.id = fitted_constraint.id + "_" + self.config.OBJECT + "_" + r_obj
        if fitted_constraint.left_operand == fitted_constraint.right_operand:
            return None
        return fitted_constraint

    def fit_multi_object_or_activity_constraint(self, fitted_constraint_template: FittedConstraint, sim_threshold):
        sim_dict = fitted_constraint_template.similarity
        fitted_constraints = []
        if self.config.LEFT_OPERAND in sim_dict and self.config.RIGHT_OPERAND in sim_dict:
            obj_sim_l = sim_dict[self.config.LEFT_OPERAND]
            obj_sim_r = sim_dict[self.config.RIGHT_OPERAND]
            for obj_l, sim_l in obj_sim_l.items():
                if sim_l >= sim_threshold:
                    for obj_r, sim_r in obj_sim_r.items():
                        if sim_r >= sim_threshold and obj_l != obj_r:
                            fitted_constraint = self.instantiate_multi_obj_or_act_constraint(fitted_constraint_template, obj_l, obj_r)
                            if fitted_constraint is not None:
                                fitted_constraints.append(fitted_constraint)
        return fitted_constraints

    def instantiate_resource_constraint(self, fitted_constraint_template: FittedConstraint, act, res):
        fitted_constraint = deepcopy(fitted_constraint_template)
        fitted_constraint = self.instantiate_multi_obj_or_act_constraint(fitted_constraint, act, None)
        fitted_constraint.constraint_str = fitted_constraint.constraint.constraint_str.replace(
            fitted_constraint.constraint.object_type, res)
        fitted_constraint.id = fitted_constraint.constraint.id + "_" + self.config.RESOURCE + act + "_" + res
        return fitted_constraint

    def fit_resource_constraint(self, fitted_constraint_template: FittedConstraint, sim_threshold):
        fitted_constraints = []
        if self.config.LEFT_OPERAND in fitted_constraint_template.similarity:
            act_sim = fitted_constraint_template.similarity[self.config.LEFT_OPERAND]
            for act, sim in act_sim.items():
                if sim >= sim_threshold and self.config.RESOURCE in fitted_constraint_template.similarity:
                    for res, sim_res in fitted_constraint_template.similarity[self.config.RESOURCE].items():
                        if sim_res >= sim_threshold:
                            fitted_constraint = self.instantiate_resource_constraint(fitted_constraint_template, act, res)
                            if fitted_constraint is not None:
                                fitted_constraints.append(fitted_constraint)
        return fitted_constraints

    def update_sims(self, fitted_constraint: FittedConstraint):
        sim_map = {}
        # check which similarities actually matter and only keep them in the sim map.
        # for activity constraints we only need the object that is in config.LEFT_OPERAND and config.RIGHT_OPERAND
        # for multi-object constraints we only neet the object that is in config.OBJECT
        # for object-level constraints we only need the object that is in config.LEFT_OPERAND and config.RIGHT_OPERAND
        # for resource constraints we only need the object that is in config.LEFT_OPERAND
        if (fitted_constraint.constraint.level == self.config.ACTIVITY or
                fitted_constraint.constraint.level == self.config.MULTI_OBJECT):
            if self.config.LEFT_OPERAND in fitted_constraint.similarity:
                sim_map[fitted_constraint.left_operand] = fitted_constraint.similarity[self.config.LEFT_OPERAND][fitted_constraint.left_operand]
            if self.config.RIGHT_OPERAND in fitted_constraint.similarity:
                sim_map[fitted_constraint.right_operand] = fitted_constraint.similarity[self.config.RIGHT_OPERAND][fitted_constraint.right_operand]
        elif fitted_constraint.constraint.level == self.config.OBJECT:
            if self.config.OBJECT in fitted_constraint.similarity:
                sim_map[fitted_constraint.object_type] = fitted_constraint.similarity[self.config.OBJECT][fitted_constraint.object_type]
        elif fitted_constraint.constraint.level == self.config.RESOURCE:
            if self.config.LEFT_OPERAND in fitted_constraint.similarity:
                sim_map[fitted_constraint.left_operand] = fitted_constraint.similarity[self.config.LEFT_OPERAND][fitted_constraint.left_operand]
        fitted_constraint.similarity = sim_map
        return fitted_constraint

