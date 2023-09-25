'''
Finds polynomial relations between constants in LIReC, using PSLQ.

Configured as such:
'degree' + 'order':
    Two integers. All relations are structured like multivariate polynomials over the constants and CFs,
    of degree 'degree' with a maximum exponent of 'order'. For example, a 2-variable polynomial of
    degree 2 and order 1 will be of the form a+bx+cy+dxy (note the lack of x^2 and y^2), and
    a 4-variable polynomial of degree (3,1) will be of the form:
        a + bx+cy+dz+ew + fxy+gxz+hxw+iyz+jyw+kzw + lxyz+mxyw+nxzw+oyzw
    Note here the lack of any single variable with an exponent greater than 1, and also the lack of xyzw.
'min_precision':
    Only use constants with this much digital precision (everything else is ignored).
'testing_precision' + 'min_roi':
    Parameters passed to our modified PSLQ, see pslq_utils.poly_check for more information.
    (if testing_precision is absent, min_precision is used instead)
'bulk':
    If present, instead of testing all constants at once in the query phase,
    only 'bulk' constants are added at a time to test for relations.
'filters':
    A dictionary that specifies which kinds of constants to use to look for relations.
    If present, no anti-relation logging can happen. Currently supported:
    'PcfCanonical': 'balanced_only' filters to only PCFs of balanced degrees if set to True.
'''
import mpmath as mp
from itertools import combinations, groupby, product
from logging import getLogger
from logging.config import fileConfig
from os import getpid
from sqlalchemy import or_
from sqlalchemy.sql.expression import func
from time import time
from traceback import format_exc
from typing import List, Dict
from LIReC.db.access import db
from LIReC.db import models
from LIReC.lib.pslq_utils import *

EXECUTE_NEEDS_ARGS = True

DEBUG_PRINT_CONSTANTS = True

ALGORITHM_NAME = 'POLYNOMIAL_PSLQ'
UNRELATION_NAME = 'NO_PSLQ'
LOGGER_NAME = 'job_logger'
MIN_PRECISION_RATIO = 0.8
MAX_PREC = 99999
EXTENSION_TYPES = ['PowerOf', 'Derived', 'PcfCanonical', 'Named'] # ordered by increasing priority
BULK_TYPES = {'PcfCanonical'}
SUPPORTED_TYPES = ['Named', 'PcfCanonical']
DEFAULT_CONST_COUNT = 1

# need to keep hold of the original db constant, but pslq_utils doesn't care for that so this is separate here
class DualConstant(PreciseConstant):
    orig: models.Constant
    
    def __init__(self, value, precision, orig, symbol=None):
        self.orig = orig
        super().__init__(value, precision, symbol)
    
    @staticmethod
    def from_db(const: models.Constant):
        return DualConstant(const.value, const.precision, const, f'C_{const.const_id}')

def get_const_class(const_type):
    name = const_type + 'Constant'
    if name not in models.__dict__:
        raise ValueError(f'Unknown constant type {const_type}')
    return models.__dict__[name]

def is_workable(x, prec, roi):
    return x and roi * abs(mp.log10(x)) < prec # first testing if x is zero to avoid computing log10(x)

def lowest_priority(consts: List[DualConstant], priorities: Dict[str, int]):
    return sorted(consts, key=lambda c: (-priorities[c.orig.const_id], c.orig.time_added))[-1]

def to_db_format(relation: PolyPSLQRelation) -> models.Relation:
    res = models.Relation()
    res.relation_type = ALGORITHM_NAME
    res.precision = relation.precision
    res.details = [relation.degree, relation.order] + relation.coeffs
    res.constants = [c.orig for c in relation.constants] # inner constants need to be DualConstant, else this fails
    return res

def from_db_format(relation: models.Relation, consts: List[DualConstant]) -> PolyPSLQRelation:
    # the symbols don't matter much, just gonna keep them unique within the relation itself
    # the orig.const_id will decide anyway
    return PolyPSLQRelation(consts, relation.details[0], relation.details[1], relation.details[2:])

def all_relations() -> List[PolyPSLQRelation]:
    # faster to query everything at once!
    consts = {c.const_id:DualConstant.from_db(c) for c in db.session.query(models.Constant) if c.value}
    rels = {r.relation_id:r for r in db.session.query(models.Relation)}
    return [from_db_format(rels[relation_id], [consts[p[0]] for p in g]) for relation_id, g in groupby(db.session.query(models.constant_in_relation_table), lambda p:p[1])]

def run_query(degree=2, order=1, min_precision=50, min_roi=2, testing_precision=15, bulk=10, filters=None):
    fileConfig('LIReC/logging.config', defaults={'log_filename': 'pslq_const_manager'})
    testing_precision = testing_precision if testing_precision else min_precision
    consts = [[c] for c in db.session.query(models.Constant).filter(models.Constant.precision >= min_precision).order_by(models.Constant.const_id)]
    for i, const_type in enumerate(EXTENSION_TYPES):
        const_class = get_const_class(const_type)
        exts = db.session.query(const_class)
        if const_type == 'PcfCanonical': # no rationals please
            exts = exts.filter(models.PcfCanonicalConstant.convergence != models.PcfConvergence.RATIONAL.value)
        exts = exts.all() # evaluate once then reuse
        consts = [c + [e for e in exts if e.const_id == c[0].const_id] for c in consts]
        if filters and filters.get(const_type, {}):
            if const_type == 'PcfCanonical' and filters[const_type].get('balanced_only', False):
                consts = [c for c in consts if len(c[-1].P) == len(c[-1].Q)]
        consts = [([c[0], i] if isinstance(c[-1], const_class) else c) for c in consts] # don't need the extension data after filtering, and only need the top priority extension type
    
    # enforce constants that have extensions! also enforce "workable numbers" which are not "too large" nor "too small" (in particular nonzero)
    # also don't really care about symbolic representation for the constants here, just need them to be unique
    priorities = {c[0].const_id : c[1] for c in consts if len(c) > 1}
    consts = [DualConstant.from_db(c[0]) for c in consts if len(c) > 1 and is_workable(c[0].value, testing_precision, min_roi)]
    testing_consts = []
    refill = True
    relations = []
    
    # TODO query existing relations and use them to remove constants that have been connected already
    
    getLogger(LOGGER_NAME).debug(f'Starting to check relations, using bulk size {bulk}')
    while not (refill and not consts): # keep going until you want to refill but can't
        if refill:
            testing_consts += consts[:bulk]
            consts = consts[bulk:]
            refill = False
        new_rels = check_consts(testing_consts, None, degree, order, testing_precision, min_roi)
        if new_rels:
            relations += new_rels
            testing_consts = list(set(testing_consts) - {lowest_priority(r.constants, priorities) for r in new_rels})
        else:
            refill = True
    
    # TODO log unrelation
    
    db.session.add_all([to_db_format(r) for r in relations])
    db.session.commit()
    return relations
    # TODO investigate randomness! on catalan+22 pcfs, sometimes finds 57 relations, sometimes finds 59

def execute_job(query_data, degree=2, order=1, min_precision=50, min_roi=2, testing_precision=None, bulk=None, filters=None, manual=False):
    # actually faster to manually query everything at once!
    testing_precision = testing_precision if testing_precision else min_precision
    relations = all_relations()
    new_relations = []
    for i, (r1, r2) in enumerate(product(query_data, relations)):
        dummy_rel = PolyPSLQRelation(r1.constants + [c for c in r2.constants if c.orig.const_id not in [c.orig.const_id for c in r1.constants]],
                                     max(r1.degree, r2.degree), max(r1.order, r2.order), []) # coeffs don't matter!
        new_relations += [r for r in check_subrelations(dummy_rel, min(r1.precision, r2.precision), testing_precision, min_roi, relations + new_relations) if r.coeffs]
    return new_relations

def summarize_results(results):
    relations = all_relations()
    new_relations = []
    for result in results:
        new_relations += [r for r in result if not combination_is_old(r.constants, r.degree, r.order, relations+new_relations)] 
    db.session.add_all([to_db_format(r) for r in new_relations])
    db.session.commit()
    getLogger(LOGGER_NAME).info(f'In total found {len(new_relations)} relations in all subjobs')
