from typing import List
from collections import Counter
import pm4py
from pm4py.objects.log.obj import EventLog, Trace, Event
from pandas import DataFrame

from app.model.fittedConstraint import FittedConstraint
from semconstmining.mining.model.parsed_label import get_dummy
from semconstmining.declare.declare import Declare
from semconstmining.declare.parsers import parse_decl
from uuid import uuid4

from app.model.violation import Violation


def verify_violations(tmp_res, log):
    counts = Counter(const for vals in tmp_res.values() for const in vals)
    res = {key: {val for val in vals if counts[val] <= 0.9 * len(log)} for key, vals in tmp_res.items()}
    return res


def get_violations_to_cases(violations):
    violation_to_cases = {}
    for case, case_violations in violations.items():
        if len(case_violations) > 0:
            for violation in case_violations:
                if violation not in violation_to_cases:
                    violation_to_cases[violation] = []
                violation_to_cases[violation].append(case)
    return violation_to_cases


def get_filtered_traces(config, log: DataFrame, parsed_tasks=None, with_resources=False):
    if parsed_tasks is not None:
        if with_resources:
            res = {trace_id: [(parsed_tasks[event[config.XES_NAME]], event[config.XES_ROLE]) if event[config.XES_NAME] in parsed_tasks else get_dummy(config, event[config.XES_NAME], config.EN)
                              for event_index, event in
                              trace.iterrows()] for trace_id, trace in log.groupby(config.XES_CASE)}
            return res
        else:
            res = {trace_id: [parsed_tasks[event[config.XES_NAME]] if event[config.XES_NAME] in parsed_tasks else get_dummy(config, event[config.XES_NAME], config.EN)
                              for event_index, event in
                              trace.iterrows()] for trace_id, trace in log.groupby(config.XES_CASE)}
            return res
    else:
        res = {trace_id: [event[config.XES_NAME] for event_idx, event in trace.iterrows()] for trace_id, trace
               in
               log.groupby(config.XES_CASE)}
        return res


def object_action_log_projection(obj, traces, config):
    """
    Return for each trace a time-ordered list of the actions for a given object type.

    Returns
    -------
    projection
        traces containing only actions applied to the same obj.
    """
    projection = EventLog()
    if traces is None:
        raise RuntimeError("You must load a log before.")
    for trace_id, trace in traces.items():
        tmp_trace = Trace()
        tmp_trace.attributes[config.XES_NAME] = trace_id
        for parsed in trace:
            if parsed.main_object == obj:
                if parsed.main_action != "":
                    event = Event({config.XES_NAME: parsed.main_action})
                    tmp_trace.append(event)
        if len(tmp_trace) > 0:
            projection.append(tmp_trace)
    return projection


def object_log_projection(traces, config):
    """
    Return for each trace a time-ordered list of the actions for a given object type.

    Returns
    -------
    projection
        traces containing only actions applied to the same obj.
    """
    projection = EventLog()
    if traces is None:
        raise RuntimeError("You must load a log before.")
    for trace_id, trace in traces.items():
        tmp_trace = Trace()
        tmp_trace.attributes[config.XES_NAME] = trace_id
        last = ""
        for parsed in trace:
            if parsed.main_object not in config.TERMS_FOR_MISSING and parsed.main_object != last:
                event = Event({config.XES_NAME: parsed.main_object})
                tmp_trace.append(event)
            last = parsed.main_object
        projection.append(tmp_trace)
    return projection


def clean_log_projection(traces, config, with_resources=False):
    """
    Same log, just with clean labels.
    """
    projection = EventLog()
    if traces is None:
        raise RuntimeError("You must load a log before.")
    for trace_id, trace in traces.items():
        tmp_trace = Trace()
        tmp_trace.attributes[config.XES_NAME] = trace_id
        if with_resources:
            for parsed, res in trace:
                if parsed.label not in config.TERMS_FOR_MISSING:
                    event = Event({config.XES_NAME: parsed.label})
                    event[config.XES_ROLE] = res.replace(" and ", " & ") if type(
                        res) == str else "unknown"
                    tmp_trace.append(event)
        else:
            for parsed in trace:
                if parsed.label not in config.TERMS_FOR_MISSING:
                    event = Event({config.XES_NAME: parsed.label})
                    tmp_trace.append(event)
        if len(tmp_trace) > 0:
            projection.append(tmp_trace)
    return projection


def check_and_add_violations(d4py, constraint_strings_to_constraint, log):
    violations = []
    d4py.model = parse_decl(constraint_strings_to_constraint.keys())
    tmp_res = d4py.conformance_checking(consider_vacuity=True)
    res = verify_violations(tmp_res, d4py.log)
    violations_to_cases = get_violations_to_cases(res)
    for key, val in violations_to_cases.items():
        violations.append(Violation(id=str(uuid4()), log=log, constraint=constraint_strings_to_constraint[key], cases=val,
                                    frequency=len(val)))
    return violations


def check_object_level_constraints(object_level_constraints, filtered_traces, config, log):
    bos = set([x.main_object for trace in filtered_traces.values() for x in trace if
               x.main_object not in config.TERMS_FOR_MISSING])
    violations = []
    for bo in bos:
        d4py = Declare(config)
        d4py.log = object_action_log_projection(bo, filtered_traces, config)
        constraint_strings_to_constraint = {c.constraint.constraint_str: c for c in object_level_constraints if c.constraint.object_type == bo}
        violations.extend(check_and_add_violations(d4py, constraint_strings_to_constraint, log))
    return violations


def check_multi_object_constraints(multi_object_constraints, filtered_traces, config, log):
    d4py = Declare(config)
    d4py.log = object_log_projection(filtered_traces, config)
    constraint_strings_to_constraint = {c.constraint.constraint_str: c for c in multi_object_constraints}
    return check_and_add_violations(d4py, constraint_strings_to_constraint, log)


def check_activity_level_constraints(activity_level_constraints, filtered_traces, config, log):
    d4py = Declare(config)
    d4py.log = clean_log_projection(filtered_traces, config)
    constraint_strings_to_constraint = {c.constraint.constraint_str: c for c in activity_level_constraints}
    return check_and_add_violations(d4py, constraint_strings_to_constraint, log)


def check_resource_level_constraints(resource_level_constraints, filtered_traces, config, log):
    d4py = Declare(config)
    d4py.log = clean_log_projection(filtered_traces, config, with_resources=True)
    constraint_strings_to_constraint = {c.constraint.constraint_str: c for c in resource_level_constraints}
    return check_and_add_violations(d4py, constraint_strings_to_constraint, log)


def check_constraints(constraints: List[FittedConstraint], config, log, event_log, nlp_helper):
    activities = pm4py.get_event_attribute_values(event_log, config.XES_NAME, case_id_key=config.XES_CASE)
    activities_to_parsed = {activity: nlp_helper.parse_label(activity) for activity in activities}
    filtered_traces = get_filtered_traces(config, event_log, parsed_tasks=activities_to_parsed)
    object_level_constraints = [c for c in constraints if c.constraint.level == config.OBJECT]
    multi_object_constraints = [c for c in constraints if c.constraint.level == config.MULTI_OBJECT]
    activity_level_constraints = [c for c in constraints if c.constraint.level == config.ACTIVITY]
    resource_level_constraints = [c for c in constraints if c.constraint.level == config.RESOURCE]
    res = {
        # First we check the object-level constraints
        config.OBJECT: check_object_level_constraints(object_level_constraints, filtered_traces, config, log),
        # Then we check the multi-object constraints,
        config.MULTI_OBJECT: check_multi_object_constraints(multi_object_constraints, filtered_traces, config, log)
        # Then we check the activity-level constraints
        , config.ACTIVITY: check_activity_level_constraints(activity_level_constraints, filtered_traces, config, log)
        # Then we check the resource constraints
        , config.RESOURCE: check_resource_level_constraints(resource_level_constraints, filtered_traces, config, log)
        if config.XES_ROLE in event_log.columns else {}
    }
    return res
