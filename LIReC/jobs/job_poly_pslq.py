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
from itertools import combinations, product
from logging import getLogger
from logging.config import fileConfig
from os import getpid
from sqlalchemy import or_
from sqlalchemy.sql.expression import func
from time import time
from traceback import format_exc
from LIReC.db import models, access
from LIReC.lib.pslq_utils import *

EXECUTE_NEEDS_ARGS = True
DEBUG_PRINT_CONSTANTS = True

ALGORITHM_NAME = 'POLYNOMIAL_PSLQ'
LOGGER_NAME = 'job_logger'
BULK_SIZE = 500
BULK_TYPES = {'PcfCanonical'}
SUPPORTED_TYPES = ['Named', 'PcfCanonical']
DEFAULT_CONST_COUNT = 1
DEFAULT_DEGREE = 2
DEFAULT_ORDER = 1

FILTERS = [
        models.Constant.precision.isnot(None)
        #or_(models.Cf.scanned_algo == None, ~models.Cf.scanned_algo.has_key(ALGORITHM_NAME)) # TODO USE scan_history TABLE!!!
        ]

def get_filters(filters, const_type):
    filter_list = list(FILTERS) # copy!
    if 'global' in filters:
        global_filters = filters['global']
        if 'min_precision' in global_filters:
            filter_list += [models.Constant.precision >= global_filters['min_precision']]
    if const_type == 'PcfCanonical':
        filter_list += [models.PcfCanonicalConstant.convergence != models.PcfConvergence.RATIONAL.value]
        if filters['PcfCanonical'].get('balanced_only', False):
            filter_list += [func.cardinality(models.PcfCanonicalConstant.P) == func.cardinality(models.PcfCanonicalConstant.Q)]

    return filter_list 

def get_const_class(const_type):
    name = const_type + 'Constant'
    if name not in models.__dict__:
        raise ValueError(f'Unknown constant type {const_type}')
    return models.__dict__[name]

def get_consts_from_query(const_type, query_data):
    const_type = get_const_class(const_type)
    return query_data[[i for i in range(len(query_data)) if isinstance(query_data[i][0], const_type)][0]]

def get_consts(const_type, db, filters):
    if const_type == 'Named': # Constant first intentionally! don't need extra details, but want to filter still
        return db.session.query(models.Constant).join(models.NamedConstant).order_by(models.NamedConstant.const_id).filter(*get_filters(filters, const_type))    

def run_query(filters=None, degree=None, bulk=None):
    fileConfig('LIReC/logging.config', defaults={'log_filename': 'pslq_const_manager'})
    if not filters:
        return []
    bulk_types = set(filters.keys()) & BULK_TYPES
    if not bulk_types:
        return []
    bulk = bulk if bulk else BULK_SIZE
    getLogger(LOGGER_NAME).debug(f'Starting to check relations, using bulk size {bulk}')
    db = access.LIReC_DB()
    results = [db.session.query(models.Constant).join(get_const_class(const_type)).filter(*get_filters(filters, const_type)).order_by(func.random()).limit(bulk).all() for const_type in bulk_types]
    # apparently postgresql is really slow with the order_by(random) part,
    # but on 1000 CFs it only takes 1 second, which imo is worth it since
    # that allows us more variety in testing the CFs...
    # TODO what to do if results is unintentionally empty?
    db.session.close()
    getLogger(LOGGER_NAME).info(f'size of batch is {len(results) * bulk}')
    return results

def execute_job(query_data, filters=None, degree=None, order=None, bulk=None, manual=False):
    try: # whole thing must be wrapped so it gets logged
        fileConfig('LIReC/logging.config', defaults={'log_filename': 'analyze_pcfs' if manual else f'pslq_const_worker_{getpid()}'})
        global_filters = filters.get('global', {})
        filters.pop('global', 0) # instead of del so we can silently dispose of global even if it doesn't exist
        if not filters:
            getLogger(LOGGER_NAME).error('No filters found! Aborting...')
            return 0 # this shouldn't happen unless pool_handler changes, so just in case...
        keys = filters.keys()
        for const_type in keys:
            if const_type not in SUPPORTED_TYPES:
                msg = f'Unsupported filter type {const_type} will be ignored! Must be one of {SUPPORTED_TYPES}.'
                print(msg)
                getLogger(LOGGER_NAME).warn(msg)
                del filters[const_type]
            elif 'count' not in filters[const_type]:
                filters[const_type]['count'] = DEFAULT_CONST_COUNT
        total_consts = sum(c['count'] for c in filters.values())
        degree = degree if degree else DEFAULT_DEGREE
        order = order if order else DEFAULT_ORDER
        getLogger(LOGGER_NAME).info(f'checking against {total_consts} constants at a time, subdivided into {({k : filters[k]["count"] for k in filters})}, using degree-{degree} relations')
        if degree > total_consts * order:
            degree = total_consts * order
            getLogger(LOGGER_NAME).info(f'redundant degree detected! reducing to {degree}')
        
        db = access.LIReC_DB()
        subsets = [combinations(get_consts_from_query(const_type, query_data) if const_type in BULK_TYPES else get_consts(const_type, db, {**filters, 'global':global_filters}), filters[const_type]['count']) for const_type in filters]
        exponents = get_exponents(degree, order, total_consts)
        
        old_relations = db.session.query(models.Relation).all()
        orig_size = len(old_relations)
        # even if the commented code were to be uncommented and implemented for
        # the scan_history table, this loop still can't be turned into list comprehension
        # because finding new relations depends on the new relations we found so far!
        for consts in product(*subsets):
            consts = [c for t in consts for c in t] # need to flatten...
            if relation_is_new(consts, degree, order, old_relations):
                if DEBUG_PRINT_CONSTANTS:
                    getLogger(LOGGER_NAME).debug(f'checking consts: {[c.const_id for c in consts]}')
                new_relations = check_consts(consts, exponents, degree, order)
                if new_relations:
                    getLogger(LOGGER_NAME).info(f'Found relation(s) on constants {[c.const_id for c in consts]}!')
                    try_count = 1
                    while try_count < 3:
                        try:
                            db.session.add_all(new_relations)
                            db.session.commit()
                            old_relations += new_relations
                        except:
                            db.session.rollback()
                            #db.session.close()
                            #db = access.LIReC_DB()
                            if try_count == 1:
                                getLogger(LOGGER_NAME).warn('Failed to commit once, trying again.')
                            else:
                                getLogger(LOGGER_NAME).error(f'Could not commit relation(s): {format_exc()}')
                        try_count += 1
            #for cf in consts:
            #    if not cf.scanned_algo:
            #        cf.scanned_algo = dict()
            #    cf.scanned_algo[ALGORITHM_NAME] = int(time())
            #db.session.add_all(consts)
        getLogger(LOGGER_NAME).info(f'finished - found {len(old_relations) - orig_size} results')
        db.session.close()
        
        getLogger(LOGGER_NAME).info('Commit done')
        
        return len(new_relations)
    except:
        getLogger(LOGGER_NAME).error(f'Exception in execute job: {format_exc()}')
        # not returning anything so summarize_results can see the error

def summarize_results(results):
    if not all(results):
        getLogger(LOGGER_NAME).info(f'At least one of the workers had an exception! Check logs')
    getLogger(LOGGER_NAME).info(f'In total found {sum(r for r in results if r)} relations')
